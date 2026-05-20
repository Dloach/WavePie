"""ActionExecutor — 动作执行器。

支持的 action_type:
  - key:       单个按键（enter, volume_up, volume_mute ...）
  - key_combo: 组合键（ctrl+z, win+shift+s ...）
  - macro:     多行按键序列
  - script:    执行外部脚本
  - log:       仅打印日志
"""

import asyncio
import subprocess
import time
import os

# 虚拟键码映射（Windows）
VK = {
    # 字母
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59,
    "z": 0x5A,
    # 数字
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    # 修饰键
    "ctrl":   0x11, "control":  0x11,
    "alt":    0x12,
    "shift":  0x10,
    "win":    0x5B, "windows": 0x5B, "meta": 0x5B,
    # 功能键
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    # 导航
    "enter":     0x0D, "return":   0x0D,
    "tab":       0x09,
    "space":     0x20,
    "backspace": 0x08,
    "delete":    0x2E, "del":    0x2E,
    "escape":    0x1B, "esc":    0x1B,
    "up":        0x26, "down":   0x28,
    "left":      0x25, "right":  0x27,
    "home":      0x24, "end":    0x23,
    "pageup":    0x21, "pagedown": 0x22,
    # 多媒体
    "volume_up":     0xAF,
    "volume_down":   0xAE,
    "volume_mute":   0xAD,
    "next_track":    0xB0,
    "prev_track":    0xB1,
    "play_pause":    0xB3,
    "prtsc":         0x2C, "printscreen": 0x2C,
    "screenshot":    0x2C,
    # 符号
    "+": 0xBB, "-": 0xBD, "*": 0x6A, ".": 0xBE, ",": 0xBC,
    "/": 0xBF, ";": 0xBA, "'": 0xDE, "`": 0xC0,
    "[": 0xDB, "]": 0xDD, "\\": 0xDC,
}


class ActionExecutor:
    """执行动作。所有方法同步阻塞，外部调用用 asyncio.run() 或线程。"""

    async def execute(self, action_type: str, payload: str) -> dict:
        try:
            if action_type == "key":
                self._exec_key(payload)
            elif action_type == "key_combo":
                self._exec_key_combo(payload)
            elif action_type == "macro":
                self._exec_macro(payload)
            elif action_type == "script":
                await self._exec_script(payload)
            else:  # log / 其他
                print(f"[Exec] 📝 {payload}")
            return {"ok": True, "detail": f"{action_type}: {payload}"}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    # ── Key: 单个按键 ──

    def _exec_key(self, key: str):
        key = key.strip().lower()
        vk = VK.get(key)
        if vk is None:
            raise ValueError(f"未知按键: {key}")
        self._keybd_send(vk)
        print(f"[Exec] ⌨️  {key}")

    # ── Key Combo: 组合键 ──

    def _exec_key_combo(self, combo: str):
        parts = combo.lower().split("+")
        mods = [VK[p] for p in parts[:-1] if p in VK]
        key = parts[-1]
        vk = VK.get(key)
        if vk is None:
            raise ValueError(f"未知按键: {key}")
        self._keybd_combo(mods, vk)
        print(f"[Exec] ⌨️  {combo}")

    def _keybd_combo(self, mods: list, vk: int):
        import ctypes
        user32 = ctypes.windll.user32
        for m in mods:
            user32.keybd_event(m, 0, 0, 0)
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(vk, 0, 2, 0)
        for m in reversed(mods):
            user32.keybd_event(m, 0, 2, 0)

    def _keybd_send(self, vk: int):
        import ctypes
        user32 = ctypes.windll.user32
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(vk, 0, 2, 0)

    # ── Macro: 多行按键序列 ──

    def _exec_macro(self, text: str):
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            delay = 0
            if line.startswith("delay "):
                try:
                    delay = int(line.split()[1])
                except Exception:
                    pass
                time.sleep(delay / 1000.0)
                continue
            if "+" in line:
                self._exec_key_combo(line)
            else:
                self._exec_key(line)
            time.sleep(0.05)

    # ── Script: 执行外部脚本 ──

    async def _exec_script(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"脚本不存在: {path}")
        proc = await asyncio.create_subprocess_exec(
            path, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode().strip())
        print(f"[Exec] 📜 {path}")
