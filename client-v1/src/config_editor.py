"""WavePie 配置编辑器 — 图形界面编辑 config.yaml。

功能：
  - 编辑径向菜单项（标签、命令类型、参数）
  - 参数面板根据命令类型动态切换
    · key_combo → 文本框 + 录制按钮
    · macro     → 多行文本编辑弹窗
    · script    → 文件选择器
    · log       → 文本输入
  - 编辑副键直接动作、滚轮映射、手势参数
  - 保存到 config.yaml
"""

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config, save_config, AppConfig


# ── 颜色 ──
BG = "#1A1A2E"
FG = "#FFFFFF"
CARD = "#2D2D44"
ACCENT = "#4A90D9"
DIM = "#888899"
INPUT_BG = "#3D3D5C"


# ============================================================
# 键盘录制对话框
# ============================================================

class KeyRecorderDialog:
    """模态对话框，用户按下组合键，捕获并显示。"""

    def __init__(self, parent):
        self._result: Optional[str] = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("录制组合键")
        self.dialog.geometry("420x200")
        self.dialog.configure(bg=BG)
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 着色
        tk.Label(
            self.dialog, text="请按下你想录制的组合键…",
            font=("Segoe UI", 12), bg=BG, fg=FG,
        ).pack(pady=(24, 8))

        self._display_var = tk.StringVar(value="（等待按键…）")
        self._display = tk.Label(
            self.dialog, textvariable=self._display_var,
            font=("Segoe UI", 18, "bold"), bg=BG, fg=ACCENT,
        )
        self._display.pack(pady=12)

        hint = tk.Label(
            self.dialog,
            text="支持 Ctrl / Alt / Shift / Win + 任意键\n录制完成后点击下方确认",
            font=("Segoe UI", 9), bg=BG, fg=DIM, justify=tk.CENTER,
        )
        hint.pack(pady=(4, 12))

        btn_frame = tk.Frame(self.dialog, bg=BG)
        btn_frame.pack(pady=8)
        tk.Button(
            btn_frame, text="✅ 确认", font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg="white", bd=0, padx=20, pady=4,
            cursor="hand2", command=self._confirm,
        ).pack(side=tk.LEFT, padx=6)
        tk.Button(
            btn_frame, text="❌ 取消", font=("Segoe UI", 10),
            bg=CARD, fg=FG, bd=0, padx=20, pady=4,
            cursor="hand2", command=self._cancel,
        ).pack(side=tk.LEFT, padx=6)

        # 键盘监听状态
        self._recording = True
        self._mods = set()
        self._main_key = None
        self._start_listener()

        # 窗口关闭处理
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)

    def _start_listener(self):
        """在后台线程启动 pynput 键盘监听。"""
        from pynput import keyboard

        # 虚拟键码 → 键名（硬件键，不受 Ctrl/Shift 影响）
        VK_MAP = {
            0x30: '0', 0x31: '1', 0x32: '2', 0x33: '3', 0x34: '4',
            0x35: '5', 0x36: '6', 0x37: '7', 0x38: '8', 0x39: '9',
            0x41: 'a', 0x42: 'b', 0x43: 'c', 0x44: 'd', 0x45: 'e',
            0x46: 'f', 0x47: 'g', 0x48: 'h', 0x49: 'i', 0x4A: 'j',
            0x4B: 'k', 0x4C: 'l', 0x4D: 'm', 0x4E: 'n', 0x4F: 'o',
            0x50: 'p', 0x51: 'q', 0x52: 'r', 0x53: 's', 0x54: 't',
            0x55: 'u', 0x56: 'v', 0x57: 'w', 0x58: 'x', 0x59: 'y',
            0x5A: 'z',
            0x70: 'f1', 0x71: 'f2', 0x72: 'f3', 0x73: 'f4',
            0x74: 'f5', 0x75: 'f6', 0x76: 'f7', 0x77: 'f8',
            0x78: 'f9', 0x79: 'f10', 0x7A: 'f11', 0x7B: 'f12',
            0x1B: 'esc', 0x09: 'tab', 0x20: 'space', 0x0D: 'enter',
            0x08: 'backspace', 0x2E: 'delete', 0x24: 'home', 0x23: 'end',
            0x21: 'pageup', 0x22: 'pagedown',
            0x26: 'up', 0x28: 'down', 0x25: 'left', 0x27: 'right',
            0x2D: 'insert', 0x13: 'pause', 0x2C: 'printscreen',
        }

        def on_press(key):
            if not self._recording:
                return
            try:
                # ── 修饰键 ──
                if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                    self._mods.add("ctrl")
                elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
                    self._mods.add("alt")
                elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                    self._mods.add("shift")
                elif key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                    self._mods.add("win")
                else:
                    # ── 主键：用虚拟键码 vk 识别硬件键 ──
                    vk = getattr(key, 'vk', None)
                    if vk and vk in VK_MAP:
                        self._main_key = VK_MAP[vk]
                    elif hasattr(key, 'char') and key.char and key.char.isprintable():
                        # 可打印字符（无 vk 或 vk 不在映射中时的后备）
                        self._main_key = key.char.lower()
                    else:
                        # Key 枚举（F1、Space 等特殊键）
                        name = str(key).replace("Key.", "")
                        name_map = {
                            "space": "space", "enter": "enter", "tab": "tab",
                            "backspace": "backspace", "escape": "esc",
                            "up": "up", "down": "down", "left": "left", "right": "right",
                            "delete": "delete", "home": "home", "end": "end",
                            "page_up": "pageup", "page_down": "pagedown",
                            "insert": "insert", "pause": "pause",
                            "print_screen": "printscreen", "menu": "menu",
                        }
                        self._main_key = name_map.get(name, name)
                        # f1-f12 也在这里处理
                        if name.startswith("f") and name[1:].isdigit():
                            self._main_key = name

                self._update_display()
                if self._main_key:
                    self._recording = False
                    return False
            except Exception:
                pass

        def on_release(key):
            try:
                if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                    self._mods.discard("ctrl")
                elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
                    self._mods.discard("alt")
                elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                    self._mods.discard("shift")
                elif key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                    self._mods.discard("win")
            except Exception:
                pass

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()

    def _update_display(self):
        parts = sorted(self._mods, key=lambda m: {"ctrl": 0, "alt": 1, "shift": 2, "win": 3}.get(m, 9))
        if self._main_key:
            parts.append(self._main_key.upper())
        text = " + ".join(parts) if parts else "（等待按键…）"
        self._display_var.set(text)

    def _confirm(self):
        parts = sorted(self._mods, key=lambda m: {"ctrl": 0, "alt": 1, "shift": 2, "win": 3}.get(m, 9))
        if self._main_key:
            parts.append(self._main_key.lower())
        self._result = "+".join(parts) if parts else ""
        self._cleanup()

    def _cancel(self):
        self._result = None
        self._cleanup()

    def _cleanup(self):
        self._recording = False
        try:
            if self._listener:
                self._listener.stop()
        except Exception:
            pass
        try:
            self.dialog.destroy()
        except Exception:
            pass

    def show(self) -> Optional[str]:
        """显示对话框，返回组合键字符串（如 'ctrl+z'），取消返回 None。"""
        self.dialog.wait_window()
        return self._result


# ============================================================
# 手柄触发键录制对话框
# ============================================================

class GamepadTriggerRecorder:
    """模态对话框，按下手柄按键，捕获并显示。"""

    def __init__(self, parent):
        self._result: Optional[str] = None  # 如 "gamepad:3"

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("录制手柄触发键")
        self.dialog.geometry("400x180")
        self.dialog.configure(bg=BG)
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        tk.Label(
            self.dialog, text="按下手柄上你想用作触发的按键…",
            font=("Segoe UI", 12), bg=BG, fg=FG,
        ).pack(pady=(24, 8))

        self._display_var = tk.StringVar(value="（等待按键…）")
        tk.Label(
            self.dialog, textvariable=self._display_var,
            font=("Segoe UI", 18, "bold"), bg=BG, fg=ACCENT,
        ).pack(pady=12)

        btn_frame = tk.Frame(self.dialog, bg=BG)
        btn_frame.pack(pady=12)
        tk.Button(
            btn_frame, text="✅ 确认", font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg="white", bd=0, padx=20, pady=4,
            cursor="hand2", command=self._confirm,
        ).pack(side=tk.LEFT, padx=6)
        tk.Button(
            btn_frame, text="❌ 取消", font=("Segoe UI", 10),
            bg=CARD, fg=FG, bd=0, padx=20, pady=4,
            cursor="hand2", command=self._cancel,
        ).pack(side=tk.LEFT, padx=6)

        self._recording = True
        self._captured = None
        self._start_polling()

        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)

    def _start_polling(self):
        """在后台线程轮询手柄按键。"""
        import threading
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def _poll_loop(self):
        import pygame
        try:
            pygame.init()
            pygame.joystick.init()
            count = pygame.joystick.get_count()
            if count == 0:
                self._display_var.set("❌ 未检测到手柄")
                return
            j = pygame.joystick.Joystick(0)
            j.init()
            name = j.get_name()
            num_buttons = j.get_numbuttons()
            self._display_var.set(f"已连接: {name}")

            while self._recording:
                pygame.event.pump()
                for k in range(num_buttons):
                    if j.get_button(k):
                        self._captured = k
                        self._display_var.set(
                            f"🎮 按钮 {k} — {name}"
                        )
                        self._recording = False
                        break
                time.sleep(0.05)
        except Exception as e:
            self._display_var.set(f"❌ 错误: {e}")

    def _confirm(self):
        if self._captured is not None:
            self._result = f"gamepad:{self._captured}"
        self._cleanup()

    def _cancel(self):
        self._result = None
        self._cleanup()

    def _cleanup(self):
        self._recording = False
        try:
            self.dialog.destroy()
        except Exception:
            pass

    def show(self) -> Optional[str]:
        """显示对话框，返回触发键标识（如 'gamepad:3'），取消返回 None。"""
        self.dialog.wait_window()
        return self._result


# ============================================================
# 宏编辑对话框
# ============================================================

class MacroEditorDialog:
    """模态对话框，多行文本编辑宏命令内容。"""

    def __init__(self, parent, initial: str = ""):
        self._result: Optional[str] = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("编辑宏命令")
        self.dialog.geometry("500x350")
        self.dialog.configure(bg=BG)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        tk.Label(
            self.dialog, text="宏命令内容（每行一条命令）",
            font=("Segoe UI", 11, "bold"), bg=BG, fg=FG,
        ).pack(pady=(12, 4))

        # 多行文本
        text_frame = tk.Frame(self.dialog, bg=CARD)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        self._text = tk.Text(
            text_frame, bg=INPUT_BG, fg=FG,
            font=("Consolas", 10), bd=0,
            insertbackground=FG, padx=8, pady=8,
            wrap=tk.WORD,
        )
        self._text.insert("1.0", initial)
        self._text.focus_set()

        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self._text.yview)
        self._text.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 按钮
        btn_frame = tk.Frame(self.dialog, bg=BG)
        btn_frame.pack(pady=12)

        tk.Label(
            btn_frame, text="提示：支持基础的按键操作，如 type:hello, press:enter 等",
            font=("Segoe UI", 8), bg=BG, fg=DIM,
        ).pack()

        btn_row = tk.Frame(btn_frame, bg=BG)
        btn_row.pack(pady=4)
        tk.Button(
            btn_row, text="✅ 确认", font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg="white", bd=0, padx=20, pady=4,
            cursor="hand2", command=self._confirm,
        ).pack(side=tk.LEFT, padx=6)
        tk.Button(
            btn_row, text="❌ 取消", font=("Segoe UI", 10),
            bg=CARD, fg=FG, bd=0, padx=20, pady=4,
            cursor="hand2", command=self._cancel,
        ).pack(side=tk.LEFT, padx=6)

        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)

    def _confirm(self):
        content = self._text.get("1.0", tk.END).strip()
        self._result = content
        self.dialog.destroy()

    def _cancel(self):
        self._result = None
        self.dialog.destroy()

    def show(self) -> Optional[str]:
        self.dialog.wait_window()
        return self._result


# ============================================================
# 动态参数面板（根据命令类型切换）
# ============================================================

class ActionParamFrame(tk.Frame):
    """根据 action_type 动态显示不同的参数编辑控件。"""

    def __init__(self, parent, action_type: str = "log", payload: str = "",
                 on_change: callable = None):
        super().__init__(parent, bg=BG)
        self._current_type = action_type
        self._on_change = on_change
        self._payload_var = tk.StringVar(value=payload)

        self._widget = None
        self._build()

    def _build(self):
        # 清除旧控件
        for w in self.winfo_children():
            w.destroy()

        t = self._current_type

        if t == "key_combo":
            self._build_key_combo()
        elif t == "macro":
            self._build_macro()
        elif t == "script":
            self._build_script()
        elif t == "key":
            self._build_key()
        else:  # log / 其他
            self._build_text()

    def _build_key_combo(self):
        """组合键：文本框 + 录制按钮"""
        row = tk.Frame(self, bg=BG)
        row.pack(fill=tk.X)

        self._payload_var = tk.StringVar(value=self._payload_var.get())
        entry = tk.Entry(
            row, textvariable=self._payload_var, width=28,
            bg=INPUT_BG, fg=FG, bd=0, font=("Segoe UI", 10),
        )
        entry.pack(side=tk.LEFT, padx=(0, 6), ipady=2)

        tk.Button(
            row, text="🎬 录制", font=("Segoe UI", 9),
            bg=ACCENT, fg="white", bd=0, padx=10, pady=2,
            cursor="hand2", command=self._record_key,
        ).pack(side=tk.LEFT)

        self._widget = entry
        entry.bind("<KeyRelease>", lambda e: self._fire_change())

    def _record_key(self):
        result = KeyRecorderDialog(self.winfo_toplevel()).show()
        if result:
            self._payload_var.set(result)
            self._fire_change()

    def _build_macro(self):
        """宏命令：显示简略信息 + 编辑按钮"""
        row = tk.Frame(self, bg=BG)
        row.pack(fill=tk.X)

        preview = self._payload_var.get()[:40]
        self._preview_label = tk.Label(
            row, text=f"📝 {preview}…" if preview else "📝 （空）",
            font=("Segoe UI", 9), bg=CARD, fg=DIM,
            anchor="w", padx=8,
        )
        self._preview_label.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

        tk.Button(
            row, text="编辑", font=("Segoe UI", 9),
            bg=ACCENT, fg="white", bd=0, padx=10, pady=2,
            cursor="hand2", command=self._edit_macro,
        ).pack(side=tk.RIGHT, padx=(6, 0))

    def _edit_macro(self):
        result = MacroEditorDialog(
            self.winfo_toplevel(),
            initial=self._payload_var.get(),
        ).show()
        if result is not None:
            self._payload_var.set(result)
            preview = result[:40]
            self._preview_label.configure(
                text=f"📝 {preview}…" if preview else "📝 （空）"
            )
            self._fire_change()

    def _build_script(self):
        """脚本：文件路径 + 选择按钮"""
        row = tk.Frame(self, bg=BG)
        row.pack(fill=tk.X)

        # 显示文件名（不含路径）
        path = self._payload_var.get()
        fname = os.path.basename(path) if path else "（未选择）"
        self._path_label = tk.Label(
            row, text=f"📂 {fname}", font=("Segoe UI", 9),
            bg=CARD, fg=FG, anchor="w", padx=8,
        )
        self._path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

        tk.Button(
            row, text="浏览…", font=("Segoe UI", 9),
            bg=ACCENT, fg="white", bd=0, padx=10, pady=2,
            cursor="hand2", command=self._pick_script,
        ).pack(side=tk.RIGHT, padx=(6, 0))

    def _pick_script(self):
        path = filedialog.askopenfilename(
            title="选择脚本文件",
            filetypes=[
                ("脚本文件", "*.bat;*.ps1;*.py;*.vbs;*.cmd"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self._payload_var.set(path)
            fname = os.path.basename(path)
            self._path_label.configure(text=f"📂 {fname}")
            self._fire_change()

    def _build_key(self):
        """单键输入：简单文本框，直接写按键名（a / enter / f5）。"""
        row = tk.Frame(self, bg=BG)
        row.pack(fill=tk.X)
        entry = tk.Entry(
            row, textvariable=self._payload_var, width=12,
            bg=INPUT_BG, fg=FG, bd=0, font=("Segoe UI", 10),
        )
        entry.pack(side=tk.LEFT, padx=(0, 6), ipady=2)
        tk.Label(
            row, text="单个按键（a / enter / f5）",
            font=("Segoe UI", 8), bg=BG, fg=DIM,
        ).pack(side=tk.LEFT)
        self._widget = entry
        entry.bind("<KeyRelease>", lambda e: self._fire_change())

    def _build_text(self):
        """纯文本输入（用于 log 等类型）。"""
        entry = tk.Entry(
            self, textvariable=self._payload_var, width=40,
            bg=INPUT_BG, fg=FG, bd=0, font=("Segoe UI", 10),
        )
        entry.pack(fill=tk.X, ipady=2)
        self._widget = entry
        entry.bind("<KeyRelease>", lambda e: self._fire_change())

    def _fire_change(self):
        if self._on_change:
            self._on_change()

    def get_payload(self) -> str:
        return self._payload_var.get()

    def set_payload(self, value: str):
        self._payload_var.set(value)

    def switch_type(self, new_type: str, payload: str = ""):
        """切换命令类型并重建参数面板。"""
        self._current_type = new_type
        self._payload_var = tk.StringVar(value=payload)
        self._build()
        self._fire_change()


# ============================================================
# 手柄信号实时检测对话框
# ============================================================

class GamepadMonitor:
    """实时显示手柄所有按键的按下状态。"""

    def __init__(self, parent):
        self._running = True

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("🎮 手柄信号检测")
        self.dialog.geometry("400x420")
        self.dialog.configure(bg=BG)
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        tk.Label(
            self.dialog, text="手柄按键实时状态（按下按钮看变化）",
            font=("Segoe UI", 12, "bold"), bg=BG, fg=FG,
        ).pack(pady=(16, 4))

        self._status_var = tk.StringVar(value="正在连接手柄…")
        tk.Label(
            self.dialog, textvariable=self._status_var,
            font=("Segoe UI", 10), bg=BG, fg=DIM,
        ).pack()

        # 按键状态网格
        self._btn_labels = []
        grid = tk.Frame(self.dialog, bg=BG)
        grid.pack(pady=12, padx=20)

        for i in range(16):
            lbl = tk.Label(
                grid, text=f"{i}", width=4,
                font=("Consolas", 11, "bold"),
                bg=CARD, fg=DIM, bd=1, relief=tk.RIDGE,
            )
            lbl.grid(row=i // 4, column=i % 4, padx=4, pady=4, ipady=4)
            self._btn_labels.append(lbl)

        tk.Button(
            self.dialog, text="关闭", font=("Segoe UI", 10),
            bg=ACCENT, fg="white", bd=0, padx=20, pady=4,
            cursor="hand2", command=self._close,
        ).pack(pady=8)

        self.dialog.protocol("WM_DELETE_WINDOW", self._close)
        self._start_polling()

    def _start_polling(self):
        import threading
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def _poll_loop(self):
        import pygame
        import time
        try:
            pygame.init()
            pygame.joystick.init()
            count = pygame.joystick.get_count()
            if count == 0:
                self._status_var.set("❌ 未检测到手柄")
                return

            j = pygame.joystick.Joystick(0)
            j.init()
            num_btns = j.get_numbuttons()
            self._status_var.set(f"✅ 已连接: {j.get_name()}  ({num_btns} 个按键)")

            while self._running:
                pygame.event.pump()
                for k in range(min(num_btns, 16)):
                    pressed = j.get_button(k)
                    if k < len(self._btn_labels):
                        lbl = self._btn_labels[k]
                        if pressed:
                            self.dialog.after(
                                0, lambda l=lbl, k=k: l.configure(
                                    bg="#4A90D9", fg="white",
                                    text=f"● {k}"))
                        else:
                            self.dialog.after(
                                0, lambda l=lbl, k=k: l.configure(
                                    bg=CARD, fg=DIM,
                                    text=f"{k}"))
                time.sleep(0.05)
        except Exception as e:
            self._status_var.set(f"❌ 错误: {e}")

    def _close(self):
        self._running = False
        try:
            self.dialog.destroy()
        except Exception:
            pass


# ============================================================
# 配置编辑器主窗口
# ============================================================

class ConfigEditor:
    """配置编辑器主窗口。"""

    def __init__(self, config_path: str = None, master: tk.Tk = None,
                 on_close: callable = None, on_save: callable = None):
        self._config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml",
        )
        self._on_close_callback = on_close
        self._on_save_callback = on_save
        self.config: AppConfig = load_config(self._config_path)

        if master:
            self.root = tk.Toplevel(master)
        else:
            self.root = tk.Tk()
        self.root.title("WavePie 配置编辑器")
        self.root.geometry("920x620")
        self.root.configure(bg=BG)
        self.root.minsize(720, 480)
        self.root.transient(master) if master else None

        # ESC 不关闭窗口
        self.root.bind("<Escape>", lambda e: None)

        self._build_ui()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI 构建 ──

    def _build_ui(self):
        paned = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, bg=BG,
            sashwidth=2, sashrelief=tk.RAISED,
        )
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ── 左侧导航 ──
        nav_frame = tk.Frame(paned, bg=BG, width=180)
        paned.add(nav_frame, minsize=150, width=180)

        tk.Label(
            nav_frame, text="WavePie", font=("Segoe UI", 16, "bold"),
            bg=BG, fg=ACCENT,
        ).pack(anchor="nw", padx=12, pady=(12, 4))

        tk.Label(
            nav_frame, text="配置编辑器", font=("Segoe UI", 9),
            bg=BG, fg=DIM,
        ).pack(anchor="nw", padx=12, pady=(0, 16))

        self._nav_btns = []
        sections = [
            ("menu", "菜单项"),
            ("direct", "直接动作"),
            ("gesture", "手势参数"),
            ("ui", "UI 外观"),
        ]
        self._active_section = tk.StringVar(value="menu")

        for key, label in sections:
            btn = tk.Button(
                nav_frame, text=label,
                font=("Segoe UI", 10),
                bg=BG, fg=FG,
                activebackground=ACCENT, activeforeground=FG,
                bd=0, anchor="w", padx=12, pady=6,
                cursor="hand2",
                command=lambda k=key: self._switch_section(k),
            )
            btn.pack(fill=tk.X, padx=4, pady=1)
            self._nav_btns.append((btn, key))

        tk.Button(
            nav_frame, text="💾 保存配置",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg="white",
            activebackground="#5BA3E6", activeforeground="white",
            bd=0, padx=12, pady=8, cursor="hand2",
            command=self._save_config,
        ).pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=12)

        # ── 右侧内容 ──
        self._content = tk.Frame(paned, bg=BG)
        paned.add(self._content, minsize=400)

        self._switch_section("menu")

    def _switch_section(self, key: str):
        self._active_section.set(key)
        for btn, k in self._nav_btns:
            btn.configure(bg=ACCENT if k == key else BG)
        for w in self._content.winfo_children():
            w.destroy()
        if key == "menu":
            self._render_menu_items()
        elif key == "direct":
            self._render_direct_actions()
        elif key == "scroll":
            self._render_scroll()
        elif key == "gesture":
            self._render_gesture()
        elif key == "ui":
            self._render_ui()

    # ── 菜单项 ──

    def _render_menu_items(self):
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(
            frame, text="径向菜单项（12 项）",
            font=("Segoe UI", 14, "bold"), bg=BG, fg=FG,
        ).pack(anchor="nw")

        tk.Label(
            frame, text="修改后点击左侧「💾 保存配置」生效",
            font=("Segoe UI", 9), bg=BG, fg=DIM,
        ).pack(anchor="nw", pady=(0, 12))

        btn0 = None
        for b in self.config.buttons:
            if b.button_id == 0:
                btn0 = b
                break
        if not btn0 or not btn0.menu_items:
            tk.Label(frame, text="未找到菜单项配置", bg=BG, fg="red").pack()
            return

        canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._menu_widgets = []
        for idx, item in enumerate(btn0.menu_items):
            w = self._create_menu_item_row(scroll_frame, idx, item)

    def _create_menu_item_row(self, parent, idx, item):
        """创建一行菜单项编辑器。"""
        card = tk.Frame(parent, bg=CARD, bd=0)
        card.pack(fill=tk.X, pady=3, ipady=4)

        row = tk.Frame(card, bg=CARD)
        row.pack(fill=tk.X, padx=8, pady=2)

        # 序号
        tk.Label(
            row, text=f"{idx+1}.", font=("Segoe UI", 9, "bold"),
            bg=CARD, fg=ACCENT, width=2,
        ).pack(side=tk.LEFT)

        # 标签输入框
        label_var = tk.StringVar(value=item.label)
        label_entry = tk.Entry(
            row, textvariable=label_var, width=14,
            bg=INPUT_BG, fg=FG, bd=0, font=("Segoe UI", 10),
        )
        label_entry.pack(side=tk.LEFT, padx=(0, 6), ipady=2)

        # 命令类型下拉（先打包，获得固有宽度）
        type_var = tk.StringVar(value=item.action_type)
        type_combo = ttk.Combobox(
            row, textvariable=type_var,
            values=["log", "key", "key_combo", "macro", "script"],
            width=10, state="readonly",
        )
        type_combo.pack(side=tk.LEFT)

        # 参数面板（后打包，expand 占满剩余空间）
        param_frame = tk.Frame(row, bg=BG)
        param_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

        action_param = ActionParamFrame(
            param_frame,
            action_type=item.action_type,
            payload=item.action_payload,
        )
        action_param.pack(fill=tk.X)

        # 类型切换时重建参数面板（tv 用默认参数固定当前迭代的 type_var）
        def cb_type_change(*args, tv=type_var, ap=action_param, tf=param_frame):
            new_type = tv.get()
            old_payload = ap.get_payload()
            for w in tf.winfo_children():
                w.destroy()
            new_ap = ActionParamFrame(
                tf, action_type=new_type, payload=old_payload,
            )
            new_ap.pack(fill=tk.X)
            for i, md in enumerate(self._menu_widgets):
                if md["idx"] == idx:
                    self._menu_widgets[i]["param"] = new_ap
                    break

        type_combo.bind("<<ComboboxSelected>>", cb_type_change)

        self._menu_widgets.append({
            "idx": idx,
            "item": item,
            "label_var": label_var,
            "type_var": type_var,
            "param": action_param,
        })

    # ── 直接动作 ──

    def _get_gamepad_buttons(self) -> int:
        """尝试连接手柄并返回按键数量；未检测到返回 0。"""
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()
            count = pygame.joystick.get_count()
            if count == 0:
                return 0
            j = pygame.joystick.Joystick(0)
            j.init()
            return j.get_numbuttons()
        except Exception:
            return 0

    def _render_direct_actions(self):
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        header = tk.Frame(frame, bg=BG)
        header.pack(fill=tk.X, anchor="nw")
        tk.Label(
            header, text="直接动作（手柄按键一键触发）",
            font=("Segoe UI", 14, "bold"), bg=BG, fg=FG,
        ).pack(side=tk.LEFT)
        tk.Button(
            header, text="🔄 手柄测试", font=("Segoe UI", 8),
            bg=ACCENT, fg="white", bd=0, padx=8, pady=2,
            cursor="hand2",
            command=lambda: GamepadMonitor(self.root),
        ).pack(side=tk.LEFT, padx=(12, 0))

        num_btns = self._get_gamepad_buttons()
        if num_btns == 0:
            tk.Label(
                frame, text="⚠️ 未检测到手柄，连接手柄后刷新页面",
                font=("Segoe UI", 9), bg=BG, fg="#FF6B6B",
            ).pack(anchor="nw", pady=(0, 8))

        btn_values = [f"gamepad:{i}" for i in range(num_btns)] if num_btns > 0 else []

        self._direct_widgets = []
        for b in self.config.buttons:
            if b.button_id == 0:
                continue
            card = tk.Frame(frame, bg=CARD, bd=0)
            card.pack(fill=tk.X, pady=4, ipady=6)

            row = tk.Frame(card, bg=CARD)
            row.pack(fill=tk.X, padx=10, pady=2)

            # ── 触发键选择 ──
            trigger_var = tk.StringVar(value=b.trigger)
            tk.Label(
                row, text="🎮 按键:", font=("Segoe UI", 9, "bold"),
                bg=CARD, fg=ACCENT,
            ).pack(side=tk.LEFT)

            trigger_combo = ttk.Combobox(
                row, textvariable=trigger_var,
                values=btn_values,
                width=12, state="readonly" if btn_values else "disabled",
            )
            trigger_combo.pack(side=tk.LEFT, padx=(4, 8))

            if not btn_values:
                trigger_combo.set("（无手柄）")

            # ── 命令类型 ──
            type_var = tk.StringVar(value=b.action_type)
            type_combo = ttk.Combobox(
                row, textvariable=type_var,
                values=["log", "key", "key_combo", "macro", "script"],
                width=10, state="readonly",
            )
            type_combo.pack(side=tk.LEFT, padx=4)

            # ── 参数面板 ──
            param_frame = tk.Frame(row, bg=BG)
            param_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

            action_param = ActionParamFrame(
                param_frame,
                action_type=b.action_type,
                payload=b.action_payload,
            )
            action_param.pack(fill=tk.X, expand=True)

            # 类型切换联动（tv 用默认参数固定当前迭代的 type_var）
            def cb_type_change(*args, tv=type_var, ap=action_param, tf=param_frame):
                new_type = tv.get()
                old_payload = ap.get_payload()
                for child in tf.winfo_children():
                    child.destroy()
                new_ap = ActionParamFrame(
                    tf, action_type=new_type, payload=old_payload,
                )
                new_ap.pack(fill=tk.X, expand=True)
                for dw in self._direct_widgets:
                    if dw["param"] is ap:
                        dw["param"] = new_ap
                        break

            type_combo.bind("<<ComboboxSelected>>", cb_type_change)

            self._direct_widgets.append({
                "button": b,
                "trigger_var": trigger_var,
                "type_var": type_var,
                "param": action_param,
            })

        if not self._direct_widgets:
            tk.Label(
                frame, text="（未配置副键直接动作）",
                bg=BG, fg=DIM, font=("Segoe UI", 10),
            ).pack(pady=20)

    # ── 滚轮 ──

    def _render_scroll(self):
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(
            frame, text="滚轮映射",
            font=("Segoe UI", 14, "bold"), bg=BG, fg=FG,
        ).pack(anchor="nw")

        # 上滚
        card_up = tk.Frame(frame, bg=CARD, bd=0)
        card_up.pack(fill=tk.X, pady=4, ipady=6)
        r_up = tk.Frame(card_up, bg=CARD)
        r_up.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(
            r_up, text="⬆  上滚", font=("Segoe UI", 10, "bold"),
            bg=CARD, fg=FG, width=8,
        ).pack(side=tk.LEFT)
        self._scroll_up_type = tk.StringVar(value=self.config.scroll.up_action_type)
        ttk.Combobox(
            r_up, textvariable=self._scroll_up_type,
            values=["log", "key", "key_combo", "macro", "script"],
            width=10, state="readonly",
        ).pack(side=tk.LEFT, padx=4)

        pf_up = tk.Frame(r_up, bg=BG)
        pf_up.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        self._scroll_up_param = ActionParamFrame(
            pf_up,
            action_type=self.config.scroll.up_action_type,
            payload=self.config.scroll.up_payload,
        )
        self._scroll_up_param.pack(fill=tk.X, expand=True)

        # 下滚
        card_down = tk.Frame(frame, bg=CARD, bd=0)
        card_down.pack(fill=tk.X, pady=4, ipady=6)
        r_down = tk.Frame(card_down, bg=CARD)
        r_down.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(
            r_down, text="⬇  下滚", font=("Segoe UI", 10, "bold"),
            bg=CARD, fg=FG, width=8,
        ).pack(side=tk.LEFT)
        self._scroll_down_type = tk.StringVar(value=self.config.scroll.down_action_type)
        ttk.Combobox(
            r_down, textvariable=self._scroll_down_type,
            values=["log", "key", "key_combo", "macro", "script"],
            width=10, state="readonly",
        ).pack(side=tk.LEFT, padx=4)

        pf_down = tk.Frame(r_down, bg=BG)
        pf_down.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        self._scroll_down_param = ActionParamFrame(
            pf_down,
            action_type=self.config.scroll.down_action_type,
            payload=self.config.scroll.down_payload,
        )
        self._scroll_down_param.pack(fill=tk.X, expand=True)

    # ── 手势 ──

    def _render_gesture(self):
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(
            frame, text="手势引擎参数",
            font=("Segoe UI", 14, "bold"), bg=BG, fg=FG,
        ).pack(anchor="nw")

        card = tk.Frame(frame, bg=CARD, bd=0)
        card.pack(fill=tk.X, pady=8, ipady=16)

        self._gesture_entries = {}
        fields = [
            ("死区 (dead_zone)", "dead_zone", 0.05),
            ("灵敏度 (sensitivity)", "sensitivity", 1.2),
        ]
        for label, key, default in fields:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill=tk.X, padx=10, pady=4)
            tk.Label(
                row, text=label, font=("Segoe UI", 10),
                bg=CARD, fg=FG, width=22, anchor="w",
            ).pack(side=tk.LEFT)
            val = getattr(self.config.gesture, key, default)
            var = tk.StringVar(value=str(val))
            entry = tk.Entry(
                row, textvariable=var, width=12,
                bg=INPUT_BG, fg=FG, bd=0, font=("Segoe UI", 10),
                justify=tk.CENTER,
            )
            entry.pack(side=tk.LEFT, padx=4, ipady=2)
            self._gesture_entries[key] = var

        tk.Label(
            card, text="提示：死区越大越不易误触，灵敏度越大光标移动越快",
            font=("Segoe UI", 8), bg=CARD, fg=DIM,
        ).pack(padx=10, pady=(8, 0))

    # ── UI ──

    def _render_ui(self):
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(
            frame, text="UI 外观", font=("Segoe UI", 14, "bold"),
            bg=BG, fg=FG,
        ).pack(anchor="nw")
        tk.Label(
            frame, text="（目前仅支持代码修改，后续版本可配置）",
            font=("Segoe UI", 9), bg=BG, fg=DIM,
        ).pack(anchor="nw", pady=(4, 12))

        info = [
            f"覆盖层透明度: {self.config.ui.overlay_opacity}",
            f"字体大小: {self.config.ui.font_size}",
            f"高亮色: {self.config.ui.highlight_color}",
        ]
        for line in info:
            tk.Label(
                frame, text=line, font=("Segoe UI", 10),
                bg=BG, fg=FG,
            ).pack(anchor="nw", pady=2)

    # ── 保存 ──

    def _save_config(self):
        try:
            # 1. 菜单项
            if hasattr(self, "_menu_widgets"):
                btn0 = None
                for b in self.config.buttons:
                    if b.button_id == 0:
                        btn0 = b
                        break
                if btn0 and btn0.menu_items:
                    for w in self._menu_widgets:
                        idx = w["idx"]
                        item = btn0.menu_items[idx]
                        item.label = w["label_var"].get()
                        item.action_type = w["type_var"].get()
                        item.action_payload = w["param"].get_payload()

            # 2. 直接动作
            if hasattr(self, "_direct_widgets"):
                for w in self._direct_widgets:
                    b = w["button"]
                    b.trigger = w["trigger_var"].get()
                    b.action_type = w["type_var"].get()
                    b.action_payload = w["param"].get_payload()

            # 3. 滚轮
            if hasattr(self, "_scroll_up_param"):
                self.config.scroll.up_action_type = self._scroll_up_type.get()
                self.config.scroll.up_payload = self._scroll_up_param.get_payload()
                self.config.scroll.down_action_type = self._scroll_down_type.get()
                self.config.scroll.down_payload = self._scroll_down_param.get_payload()

            # 4. 手势参数
            if hasattr(self, "_gesture_entries"):
                try:
                    self.config.gesture.dead_zone = float(
                        self._gesture_entries["dead_zone"].get()
                    )
                    self.config.gesture.sensitivity = float(
                        self._gesture_entries["sensitivity"].get()
                    )
                except ValueError:
                    messagebox.showwarning("参数错误", "死区和灵敏度必须为数字")
                    return

            save_config(self.config, self._config_path)
            # 通知 app 直接更新内存中的配置
            if self._on_save_callback:
                self._on_save_callback(self.config)

            # 自动消失的 toast 后关闭窗口
            self._toast("✅ 已保存")
            self.root.after(400, self._on_close)

        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _toast(self, message: str, duration_ms: int = 1200):
        """显示一个自动消失的提示（不打断用户操作）。"""
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg="#2D2D44")

        tk.Label(
            toast, text=message,
            font=("Segoe UI", 12), bg="#2D2D44", fg="#FFFFFF",
            padx=24, pady=12,
        ).pack()

        toast.update_idletasks()
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        tw, th = toast.winfo_width(), toast.winfo_height()
        toast.geometry(f"+{px + (pw - tw) // 2}+{py + ph - th - 40}")

        toast.after(duration_ms, toast.destroy)

    def _on_close(self):
        self.root.destroy()
        if self._on_close_callback:
            self._on_close_callback()


if __name__ == "__main__":
    editor = ConfigEditor()
    editor.root.mainloop()
