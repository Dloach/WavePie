"""ActionExecutor — 动作执行器。

将动作定义（type + payload）解析并执行：
- key_combo: 模拟键盘快捷键
- macro: 执行预定义宏
- script: 运行外部脚本

Phase 1 使用 platform-specific 方法模拟键盘。
"""

import subprocess
import sys
import time


# Windows 虚拟键码表
VK = {
    "ctrl": 0x11, "control": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "win": 0x5B, "meta": 0x5B,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59,
    "z": 0x5A,
    "enter": 0x0D, "esc": 0x1B, "tab": 0x09,
    "space": 0x20, "backspace": 0x08,
    "delete": 0x2E, "insert": 0x2D,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "volume_mute": 0xAD, "volume_down": 0xAE, "volume_up": 0xAF,
}


class ActionExecutor:
    """跨平台动作执行器。"""

    def __init__(self, config):
        self._config = config
        self._last_action_time = 0.0

    async def execute(self, action_type: str, payload: str) -> dict:
        """执行一个动作。返回执行结果 {'ok': bool, 'detail': str}。"""
        self._last_action_time = time.monotonic()

        try:
            if action_type == "log":
                print(f"[Log] {payload}")
                return {"ok": True, "detail": payload}
            elif action_type == "key":
                return self._execute_key(payload)
            elif action_type == "key_combo":
                return self._execute_key_combo(payload)
            elif action_type == "macro":
                return self._execute_macro(payload)
            elif action_type == "script":
                return self._execute_script(payload)
            else:
                return {"ok": False, "detail": f"未知动作类型: {action_type}"}
        except Exception as e:
            return {"ok": False, "detail": f"执行失败: {e}"}

    def _execute_key(self, key: str) -> dict:
        """发送单个按键（无修饰键）。"""
        return self._keybd_send(key)

    def _keybd_send(self, key: str) -> dict:
        """底层的 keybd_event 发送（单键按下+松开）。"""
        key = key.lower().strip()
        vk = VK.get(key)
        if vk is None and len(key) == 1 and 'a' <= key <= 'z':
            vk = ord(key.upper())
        if vk is None:
            return {"ok": False, "detail": f"未知按键: {key}"}
        import ctypes
        try:
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
            return {"ok": True, "detail": f"按键: {key}"}
        except Exception as e:
            return {"ok": False, "detail": f"keybd_event 失败: {e}"}

    def _execute_key_combo(self, combo: str) -> dict:
        """模拟键盘快捷键。

        支持的格式:
          "ctrl+c"       → 复制
          "win+shift+s"  → Windows 截图
          "volume_mute"  → 静音（系统音量键）
          "volume_up"    → 音量+
          "volume_down"  → 音量-
        """
        combo = combo.lower().strip()
        platform = sys.platform

        if platform == "win32":
            return self._key_combo_windows(combo)
        elif platform == "darwin":
            return self._key_combo_macos(combo)
        else:
            return self._key_combo_linux(combo)

    def _key_combo_windows(self, combo: str) -> dict:
        """Windows — 用 keybd_event + WM_APPCOMMAND，零进程开销。"""
        # ── 系统音量 / 媒体键 ──
        system_keys = {
            "volume_mute":  0xAD,
            "volume_down":  0xAE,
            "volume_up":    0xAF,
            "next_track":   0xB0,
            "prev_track":   0xB1,
            "play_pause":   0xB3,
        }
        if combo in system_keys:
            try:
                import ctypes
                vk = system_keys[combo]
                # 双保险：WM_APPCOMMAND 广播 + keybd_event
                appcmd_map = {
                    "volume_mute": 0x080000, "volume_down": 0x090000,
                    "volume_up": 0x0A0000,
                }
                lparam = appcmd_map.get(combo, 0)
                if lparam:
                    ctypes.windll.user32.PostMessageW(
                        0xFFFF, 0x0319, 0, lparam
                    )
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
                return {"ok": True, "detail": f"系统键: {combo}"}
            except Exception as e:
                return {"ok": False, "detail": f"系统键失败: {e}"}

        # ── 普通快捷键 ──
        import ctypes
        parts = combo.lower().split("+")
        mods = []
        main_vk = None

        for p in parts:
            p = p.strip()
            if p in ("ctrl", "control", "shift", "alt", "win", "meta"):
                mods.append(VK.get(p, 0x11))
            else:
                main_vk = VK.get(p)
                if main_vk is None and len(p) == 1 and 'a' <= p <= 'z':
                    main_vk = ord(p.upper())

        if main_vk is None:
            main_vk = 0x43  # fallback 'c'

        try:
            # 按下修饰键
            for mod in mods:
                ctypes.windll.user32.keybd_event(mod, 0, 0, 0)
            # 按下+松开主键
            ctypes.windll.user32.keybd_event(main_vk, 0, 0, 0)
            ctypes.windll.user32.keybd_event(main_vk, 0, 2, 0)
            # 松开修饰键（反向顺序）
            for mod in reversed(mods):
                ctypes.windll.user32.keybd_event(mod, 0, 2, 0)

            return {"ok": True, "detail": f"按键: {combo}"}
        except Exception as e:
            return {"ok": False, "detail": f"keybd_event 失败: {e}"}

    def _key_combo_macos(self, combo: str) -> dict:
        """macOS 键盘模拟 — 使用 osascript。"""
        # 解析修饰键
        parts = combo.split("+")
        key = parts[-1]
        mods = parts[:-1]

        modifier_map = {
            "ctrl": "command down", "control": "command down",
            "cmd": "command down", "command": "command down",
            "shift": "shift down",
            "alt": "option down", "option": "option down",
        }

        keystroke_parts = []
        for m in mods:
            m = m.strip()
            if m in modifier_map:
                keystroke_parts.append(modifier_map[m])

        keystroke = f'keystroke "{key}"'
        if keystroke_parts:
            keystroke += f' using {{{", ".join(keystroke_parts)}}}'

        script = f'tell application "System Events" to {keystroke}'
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5
            )
            return {"ok": True, "detail": f"模拟按键: {combo}"}
        except Exception as e:
            return {"ok": False, "detail": f"osascript 执行失败: {e}"}

    def _key_combo_linux(self, combo: str) -> dict:
        """Linux 键盘模拟 — 使用 xdotool。"""
        try:
            subprocess.run(
                ["xdotool", "key", combo],
                capture_output=True, timeout=5
            )
            return {"ok": True, "detail": f"模拟按键: {combo}"}
        except Exception as e:
            return {"ok": False, "detail": f"xdotool 执行失败: {e}"}

    def _execute_macro(self, macro_name: str) -> dict:
        """执行预定义宏。"""
        # Phase 1 只内置少量宏，后续可扩展为加载外部宏文件
        macros = {
            "paste_markdown": self._macro_paste_markdown,
        }
        fn = macros.get(macro_name)
        if fn:
            return fn()
        return {"ok": False, "detail": f"未找到宏: {macro_name}"}

    def _macro_paste_markdown(self) -> dict:
        """示例宏：粘贴为纯 Markdown。"""
        # 先 ctrl+c 复制，然后... (占位逻辑)
        return {"ok": True, "detail": "宏执行: paste_markdown (占位)"}

    def _execute_script(self, script_path: str) -> dict:
        """执行外部脚本。"""
        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True, timeout=30
            )
            return {
                "ok": result.returncode == 0,
                "detail": result.stdout.decode() if result.returncode == 0
                          else result.stderr.decode(),
            }
        except Exception as e:
            return {"ok": False, "detail": f"脚本执行失败: {e}"}


# 系统快捷键映射
_SYSTEM_HOTKEYS = {
    "volume_mute": "volume_mute",
    "volume_up": "volume_up",
    "volume_down": "volume_down",
    "play_pause": "play_pause",
    "next_track": "next_track",
    "prev_track": "prev_track",
}
