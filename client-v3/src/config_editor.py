"""WavePie V3 配置编辑器 —— 全新 UI。

设计理念：
  - 卡片式垂直布局，每个菜单项一张独立卡片
  - 清晰的信息层次：标签 → 类型 → 参数 → 预览
  - 上下按钮拖拽排序
  - 状态栏实时反馈
  - 鼠标滚轮滚动支持
"""

import os
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable
import yaml

# ═══════════════════════════════════════════════════
#  调色板
# ═══════════════════════════════════════════════════
BG       = "#1E1E2E"   # 主背景
SURFACE  = "#282840"   # 卡片 / 面板
BORDER   = "#3A3A55"   # 边框
FG       = "#E0E0F0"   # 主文字
DIM      = "#8888AA"   # 次级文字
ACCENT   = "#5B9BD5"   # 主题蓝
ACCENT2  = "#7C6FF0"   # 主题紫（辅助）
GREEN    = "#4CAF84"   # 成功
RED      = "#E0556A"   # 危险
WARN     = "#E0A850"   # 警告
HOVER    = "#353560"   # 悬停高亮

# 类型颜色徽章
TYPE_COLORS = {
    "log":       "#8888AA",
    "key":       "#56B6C2",
    "key_combo": "#C678DD",
    "macro":     "#E0A850",
    "script":    "#98C379",
}

# 类型中文名
TYPE_NAMES = {
    "log":       "日志",
    "key":       "单键",
    "key_combo": "组合键",
    "macro":     "宏",
    "script":    "脚本",
}

# 按键显示名映射
KEY_DISPLAY = {
    "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win",
    "enter": "Enter", "tab": "Tab", "space": "Space",
    "backspace": "Backspace", "delete": "Delete", "escape": "Esc",
    "up": "↑", "down": "↓", "left": "←", "right": "→",
    "volume_up": "音量+", "volume_down": "音量-", "volume_mute": "静音",
    "prtsc": "PrtSc", "printscreen": "PrtSc",
    "next_track": "下一曲", "prev_track": "上一曲", "play_pause": "播放/暂停",
    "f1":"F1","f2":"F2","f3":"F3","f4":"F4","f5":"F5","f6":"F6",
    "f7":"F7","f8":"F8","f9":"F9","f10":"F10","f11":"F11","f12":"F12",
    "home": "Home", "end": "End", "pageup": "PgUp", "pagedown": "PgDn",
}


# ═══════════════════════════════════════════════════
#  按键录制弹窗（保留原实现，小幅 UI 优化）
# ═══════════════════════════════════════════════════

class KeyRecorderDialog:
    """按键录制弹窗。"""
    def __init__(self, parent):
        self._result: Optional[str] = None
        self._keys = []  # 有序列表，保持按键顺序
        self._listening = True
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("录制快捷键")
        self.dialog.geometry("400x200")
        self.dialog.configure(bg=SURFACE)
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 居中弹窗
        self.dialog.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        dw, dh = 400, 200
        self.dialog.geometry(f"{dw}x{dh}+{px+(pw-dw)//2}+{py+(ph-dh)//2}")

        tk.Label(self.dialog, text="🎹 录制快捷键",
                 font=("Segoe UI", 13, "bold"), bg=SURFACE, fg=FG).pack(pady=(16, 4))
        tk.Label(self.dialog, text="按下你想录制的组合键…",
                 font=("Segoe UI", 10), bg=SURFACE, fg=DIM).pack()

        self._display = tk.Label(self.dialog, text="等待按键…",
                                 font=("Segoe UI", 20, "bold"),
                                 bg=SURFACE, fg=ACCENT)
        self._display.pack(pady=(8, 12))

        btn_frame = tk.Frame(self.dialog, bg=SURFACE)
        btn_frame.pack()
        tk.Button(btn_frame, text="✅ 确认", font=("Segoe UI", 10, "bold"),
                  bg=ACCENT, fg="white", bd=0, padx=20, pady=5, cursor="hand2",
                  activebackground="#4A8BC5",
                  command=self._confirm).pack(side="left", padx=6)
        tk.Button(btn_frame, text="取消", font=("Segoe UI", 10),
                  bg=BORDER, fg=FG, bd=0, padx=20, pady=5, cursor="hand2",
                  activebackground="#4A4A65",
                  command=self._cancel).pack(side="left", padx=6)

        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)
        self._start_listener()

    def _start_listener(self):
        import threading
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        from pynput import keyboard
        def on_press(key):
            if not self._listening:
                return False
            try:
                k = key.char.lower()
            except AttributeError:
                k = key.name.lower() if hasattr(key, 'name') else str(key)
            # 跨平台按键名 → Windows 命名
            k = {"cmd":"win","cmd_l":"win","cmd_r":"win","cmd_r":"win",
                 "ctrl_l":"ctrl","ctrl_r":"ctrl","alt_l":"alt","alt_r":"alt",
                 "shift_l":"shift","shift_r":"shift"}.get(k, k)
            if k not in self._keys:
                self._keys.append(k)
            display = " + ".join(self._keys)
            self.dialog.after(0, lambda t=display: self._display.config(text=t or "等待按键…"))
        def on_release(key):
            if key == keyboard.Key.esc:
                self.dialog.after(0, self._cancel)
                return False
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

    def _confirm(self):
        if self._keys:
            self._result = "+".join(self._keys)
        self._cleanup()

    def _cancel(self):
        self._result = None
        self._cleanup()

    def _cleanup(self):
        self._listening = False
        try:
            self.dialog.destroy()
        except Exception:
            pass

    def show(self) -> Optional[str]:
        self.dialog.wait_window()
        return self._result


# ═══════════════════════════════════════════════════
#  宏编辑器（全新：表格化步骤编辑）
# ═══════════════════════════════════════════════════

class MacroEditorDialog:
    """宏步骤编辑器 —— 表格化逐行编辑，而非原始文本框。"""
    def __init__(self, parent, raw_text: str):
        self._result: Optional[str] = None
        self._steps: list = []
        # 解析现有宏
        for line in raw_text.strip().splitlines():
            line = line.strip()
            if line:
                self._steps.append(line)

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("编辑宏序列")
        self.dialog.geometry("520x440")
        self.dialog.configure(bg=BG)
        self.dialog.resizable(True, True)
        self.dialog.minsize(400, 300)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 居中
        self.dialog.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        dw, dh = 520, 440
        self.dialog.geometry(f"{dw}x{dh}+{px+(pw-dw)//2}+{py+(ph-dh)//2}")

        self._build()

    def _build(self):
        # 标题
        header = tk.Frame(self.dialog, bg=BG)
        header.pack(fill="x", padx=16, pady=(16, 8))
        tk.Label(header, text="📋 宏步骤编辑器",
                 font=("Segoe UI", 13, "bold"), bg=BG, fg=FG).pack(side="left")
        tk.Label(header, text=f"{len(self._steps)} 步",
                 font=("Segoe UI", 10), bg=BG, fg=DIM).pack(side="left", padx=8)

        # 说明
        tk.Label(self.dialog,
                 text="每行一个按键或组合键。以 delay 开头表示延迟（毫秒）。",
                 font=("Segoe UI", 9), bg=BG, fg=DIM).pack(anchor="w", padx=16)

        # 步骤列表（可滚动）
        list_frame = tk.Frame(self.dialog, bg=SURFACE)
        list_frame.pack(fill="both", expand=True, padx=16, pady=8)

        self._canvas = tk.Canvas(list_frame, bg=SURFACE, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=SURFACE)
        self._inner.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 鼠标滚轮
        self._canvas.bind("<Enter>", lambda e: self._canvas.bind_all(
            "<MouseWheel>", lambda e: self._canvas.yview_scroll(-1 * (e.delta // 120), "units")))
        self._canvas.bind("<Leave>", lambda e: self._canvas.unbind_all("<MouseWheel>"))

        self._step_vars = []
        self._step_frames = []
        self._render_steps()

        # 底部按钮
        btn_frame = tk.Frame(self.dialog, bg=BG)
        btn_frame.pack(fill="x", padx=16, pady=(4, 12))
        tk.Button(btn_frame, text="➕ 添加步骤", font=("Segoe UI", 9),
                  bg=SURFACE, fg=ACCENT, bd=0, padx=12, pady=4, cursor="hand2",
                  activebackground=HOVER,
                  command=self._add_step).pack(side="left")
        tk.Button(btn_frame, text="💾 保存宏", font=("Segoe UI", 10, "bold"),
                  bg=ACCENT, fg="white", bd=0, padx=18, pady=5, cursor="hand2",
                  activebackground="#4A8BC5",
                  command=self._save).pack(side="right", padx=(4, 0))
        tk.Button(btn_frame, text="取消", font=("Segoe UI", 10),
                  bg=BORDER, fg=FG, bd=0, padx=16, pady=5, cursor="hand2",
                  activebackground="#4A4A65",
                  command=self.dialog.destroy).pack(side="right")

        self.dialog.bind("<Control-s>", lambda e: self._save())
        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())

    def _render_steps(self):
        for f in self._step_frames:
            f.destroy()
        self._step_vars.clear()
        self._step_frames.clear()

        for i, step in enumerate(self._steps):
            self._render_one_step(i, step)

        if not self._steps:
            # 空状态
            tk.Label(self._inner, text="暂无步骤，点击「添加步骤」开始",
                     font=("Segoe UI", 10), bg=SURFACE, fg=DIM,
                     pady=20).pack()

    def _render_one_step(self, i: int, value: str):
        row = tk.Frame(self._inner, bg=SURFACE)
        row.pack(fill="x", pady=2, padx=4)

        # 序号
        tk.Label(row, text=f"#{i+1}", font=("Consolas", 9, "bold"),
                 bg=SURFACE, fg=ACCENT, width=4, anchor="e").pack(side="left", padx=(4, 6))

        # 输入框
        var = tk.StringVar(value=value)
        entry = tk.Entry(row, textvariable=var,
                         font=("Consolas", 10), bg=BG, fg=FG,
                         bd=0, insertbackground=FG,
                         relief="flat")
        entry.pack(side="left", fill="x", expand=True, ipady=3, padx=(0, 4))

        # 删除
        def make_del(idx=i):
            return lambda: self._delete_step(idx)
        tk.Button(row, text="✕", font=("Segoe UI", 9, "bold"),
                  bg=SURFACE, fg=RED, bd=0, padx=6, cursor="hand2",
                  activebackground=HOVER,
                  command=make_del()).pack(side="right")

        self._step_vars.append(var)
        self._step_frames.append(row)

    def _add_step(self):
        self._steps.append("")
        self._render_steps()

    def _delete_step(self, idx: int):
        if 0 <= idx < len(self._steps):
            self._steps.pop(idx)
            self._render_steps()

    def _save(self):
        # 收集所有步骤
        steps = []
        for var in self._step_vars:
            text = var.get().strip()
            if text:
                steps.append(text)
        self._result = "\n".join(steps)
        self.dialog.destroy()

    def show(self) -> Optional[str]:
        self.dialog.wait_window()
        return self._result


# ═══════════════════════════════════════════════════
#  参数面板（动态切换，全宽布局）
# ═══════════════════════════════════════════════════

class ActionParamPanel(tk.Frame):
    """根据 action_type 动态切换的参数输入区。"""
    def __init__(self, parent, action_type="log", payload="", on_change=None):
        super().__init__(parent, bg=SURFACE)
        self._current_type = action_type
        self._payload_var = tk.StringVar(value=payload)
        self._on_change = on_change
        self._build()

    def get_payload(self) -> str:
        if self._current_type == "key_combo" and hasattr(self, '_combo_var'):
            return self._combo_var.get()
        return self._payload_var.get()

    def get_preview(self) -> str:
        """生成人类可读的预览文本。"""
        payload = self.get_payload().strip()
        t = self._current_type
        if not payload:
            return "（未配置）"
        if t == "log":
            return f"输出日志: {payload[:40]}"
        elif t == "key":
            display = KEY_DISPLAY.get(payload.lower(), payload)
            return f"按下按键: {display}"
        elif t == "key_combo":
            parts = payload.lower().split("+")
            pretty = " + ".join(KEY_DISPLAY.get(p.strip(), p.strip()) for p in parts)
            return f"按下组合键: {pretty}"
        elif t == "macro":
            lines = [l.strip() for l in payload.splitlines() if l.strip()]
            return f"执行 {len(lines)} 步宏序列"
        elif t == "script":
            fname = os.path.basename(payload) if payload else ""
            return f"运行脚本: {fname}" if fname else "（未选择脚本）"
        return payload[:40]

    def switch_type(self, new_type: str):
        self._current_type = new_type
        self._build()

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()
        # 清理上一次 key_combo 的残留属性
        if hasattr(self, '_combo_var'):
            del self._combo_var

    def _build(self):
        self._clear()
        t = self._current_type

        if t == "key":
            self._build_key()
        elif t == "key_combo":
            self._build_key_combo()
        elif t == "macro":
            self._build_macro()
        elif t == "script":
            self._build_script()
        else:
            self._build_log()

    def _build_log(self):
        tk.Label(self, text="消息内容:",
                 font=("Segoe UI", 9), bg=SURFACE, fg=DIM).pack(side="left", padx=(4, 4))
        entry = tk.Entry(self, textvariable=self._payload_var,
                         font=("Segoe UI", 9), bg=BG, fg=FG,
                         bd=0, insertbackground=FG)
        entry.pack(side="left", fill="x", expand=True, ipady=2, padx=(0, 8))

    def _build_key(self):
        tk.Label(self, text="按键名:",
                 font=("Segoe UI", 9), bg=SURFACE, fg=DIM).pack(side="left", padx=(4, 4))
        entry = tk.Entry(self, textvariable=self._payload_var,
                         font=("Segoe UI", 9), bg=BG, fg=FG,
                         bd=0, insertbackground=FG, width=16)
        entry.pack(side="left", ipady=2)
        tk.Label(self, text="例: enter  volume_up  prtsc",
                 font=("Segoe UI", 8), bg=SURFACE, fg=DIM).pack(side="left", padx=6)

    def _build_key_combo(self):
        self._combo_var = tk.StringVar(value=self._payload_var.get())
        tk.Label(self, text="组合键:",
                 font=("Segoe UI", 9), bg=SURFACE, fg=DIM).pack(side="left", padx=(4, 4))
        entry = tk.Entry(self, textvariable=self._combo_var,
                         font=("Consolas", 10, "bold"), bg=BG, fg=ACCENT2,
                         bd=0, insertbackground=FG, width=22)
        entry.pack(side="left", ipady=2)
        tk.Button(self, text="🎬 录制", font=("Segoe UI", 9),
                  bg=ACCENT, fg="white", bd=0, padx=10, pady=2, cursor="hand2",
                  activebackground="#4A8BC5",
                  command=self._record).pack(side="left", padx=6)

    def _record(self):
        result = KeyRecorderDialog(self.winfo_toplevel()).show()
        if result:
            self._combo_var.set(result)
            if self._on_change:
                self._on_change()

    def _build_macro(self):
        tk.Label(self, text=f"宏步骤:",
                 font=("Segoe UI", 9), bg=SURFACE, fg=DIM).pack(side="left", padx=(4, 4))
        # 显示步骤数
        lines = [l.strip() for l in self._payload_var.get().splitlines() if l.strip()]
        step_label = tk.Label(self, text=f"{len(lines)} 步",
                              font=("Segoe UI", 9, "bold"), bg=SURFACE, fg=ACCENT)
        step_label.pack(side="left", padx=(0, 4))
        self._step_label = step_label

        btn = tk.Button(self, text="✏️ 编辑宏", font=("Segoe UI", 9),
                        bg=ACCENT2, fg="white", bd=0, padx=10, pady=2, cursor="hand2",
                        activebackground="#6C5FE0",
                        command=self._edit_macro)
        btn.pack(side="left", padx=4)

    def _edit_macro(self):
        result = MacroEditorDialog(self.winfo_toplevel(),
                                   self._payload_var.get()).show()
        if result is not None:
            self._payload_var.set(result)
            lines = [l.strip() for l in result.splitlines() if l.strip()]
            if hasattr(self, '_step_label'):
                self._step_label.config(text=f"{len(lines)} 步")
            if self._on_change:
                self._on_change()

    def _build_script(self):
        tk.Label(self, text="脚本路径:",
                 font=("Segoe UI", 9), bg=SURFACE, fg=DIM).pack(side="left", padx=(4, 4))
        entry = tk.Entry(self, textvariable=self._payload_var,
                         font=("Segoe UI", 9), bg=BG, fg=FG,
                         bd=0, insertbackground=FG)
        entry.pack(side="left", fill="x", expand=True, ipady=2, padx=(0, 4))
        tk.Button(self, text="📂 浏览…", font=("Segoe UI", 9),
                  bg=SURFACE, fg=ACCENT, bd=0, padx=10, pady=2, cursor="hand2",
                  activebackground=HOVER,
                  command=self._browse).pack(side="left", padx=(0, 4))

    def _browse(self):
        path = filedialog.askopenfilename(
            title="选择脚本", parent=self,
            filetypes=[("可执行脚本", "*.bat;*.ps1;*.py;*.exe"), ("所有文件", "*.*")])
        if path:
            self._payload_var.set(path)
            if self._on_change:
                self._on_change()


# ═══════════════════════════════════════════════════
#  主编辑器窗口
# ═══════════════════════════════════════════════════

class ConfigEditor:
    """WavePie 菜单项配置编辑器。"""

    def __init__(self, config_path: str, master=None,
                 on_close: Callable = None,
                 on_save: Callable = None):
        self._path = config_path
        self._on_close = on_close
        self._on_save = on_save
        self._last_deleted: Optional[dict] = None  # 撤销删除
        self._last_deleted_idx: int = -1

        with open(config_path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

        self.root = tk.Toplevel(master)
        self.root.title("WavePie 菜单项编辑器")
        self.root.geometry("760x620")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(500, 400)
        self.root.transient(master)
        self.root.grab_set()

        # 居中窗口
        self.root.update_idletasks()
        if master:
            mw = master.winfo_width()
            mh = master.winfo_height()
            if mw > 100 and mh > 100:
                # master 窗口足够大，相对于它居中
                mx = master.winfo_rootx()
                my = master.winfo_rooty()
                rw = min(760, mw - 40)
                rh = min(620, mh - 60)
                self.root.geometry(f"{rw}x{rh}+{mx+(mw-rw)//2}+{my+(mh-rh)//2}")
            else:
                # master 太小（如 1×1 的 overlay），屏幕居中
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                rw, rh = 760, 620
                self.root.geometry(f"{rw}x{rh}+{(sw-rw)//2}+{(sh-rh)//2}")

        self._items = self._data.get("menu", {}).get("items", [])
        self._cards = []  # {idx, label_var, type_var, param_panel, frame, preview_label}

        self._build_ui()
        self._render_all_cards()
        self._update_status()

        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.bind("<Control-s>", lambda e: self._save())
        self.root.bind("<Control-z>", lambda e: self._undo_delete())
        self.root.bind("<Escape>", lambda e: self._close())

    # ── UI 构建 ──

    def _build_ui(self):
        """构建整体布局：顶部工具栏 + 滚动卡片区 + 状态栏。"""

        # ── 顶部工具栏 ──
        toolbar = tk.Frame(self.root, bg=SURFACE, height=48)
        toolbar.pack(fill="x", padx=0, pady=0)
        toolbar.pack_propagate(False)

        tk.Label(toolbar, text="⚙ 菜单项编辑器",
                 font=("Segoe UI", 14, "bold"), bg=SURFACE, fg=FG).pack(
            side="left", padx=(16, 8), pady=10)
        self._count_label = tk.Label(toolbar, text="",
                                     font=("Segoe UI", 10), bg=SURFACE, fg=DIM)
        self._count_label.pack(side="left", pady=10)

        # 右侧按钮
        tk.Button(toolbar, text="💾 保存", font=("Segoe UI", 10, "bold"),
                  bg=ACCENT, fg="white", bd=0, padx=16, pady=6, cursor="hand2",
                  activebackground="#4A8BC5",
                  command=self._save).pack(side="right", padx=(4, 16), pady=8)
        tk.Button(toolbar, text="关闭", font=("Segoe UI", 10),
                  bg=BORDER, fg=FG, bd=0, padx=16, pady=6, cursor="hand2",
                  activebackground="#4A4A65",
                  command=self._close).pack(side="right", padx=4, pady=8)

        # ── 分隔线 ──
        sep = tk.Frame(self.root, bg=BORDER, height=1)
        sep.pack(fill="x")

        # ── 滚动卡片区域 ──
        canvas_frame = tk.Frame(self.root, bg=BG)
        canvas_frame.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(canvas_frame, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical",
                                 command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=BG)
        self._inner.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))

        self._canvas.create_window((0, 0), window=self._inner, anchor="nw",
                                   tags="inner")
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._canvas.pack(side="left", fill="both", expand=True, padx=(16, 0), pady=8)
        scrollbar.pack(side="right", fill="y", padx=(0, 16), pady=8)

        # 鼠标滚轮
        def _bind_wheel(e):
            self._canvas.yview_scroll(-1 * (e.delta // 120), "units")
        self._canvas.bind("<Enter>",
            lambda e: self._canvas.bind_all("<MouseWheel>", _bind_wheel))
        self._canvas.bind("<Leave>",
            lambda e: self._canvas.unbind_all("<MouseWheel>"))

        # Canvas 尺寸跟随
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig("inner", width=e.width))

        # ── 状态栏 ──
        status_frame = tk.Frame(self.root, bg=SURFACE, height=28)
        status_frame.pack(fill="x", side="bottom")
        status_frame.pack_propagate(False)
        self._status_label = tk.Label(status_frame, text="",
                                      font=("Segoe UI", 8), bg=SURFACE, fg=DIM)
        self._status_label.pack(side="left", padx=12, pady=4)
        tk.Label(status_frame, text="Ctrl+S 保存 · Esc 关闭 · Ctrl+Z 撤销删除",
                 font=("Segoe UI", 8), bg=SURFACE, fg=DIM).pack(
            side="right", padx=12, pady=4)

    # ── 卡片渲染 ──

    def _render_add_button(self):
        """在卡片区底部渲染添加按钮。"""
        add_frame = tk.Frame(self._inner, bg=BG)
        add_frame.pack(fill="x", pady=(4, 8))
        tk.Button(add_frame, text="＋ 添加菜单项", font=("Segoe UI", 10),
                  bg=SURFACE, fg=ACCENT, bd=0, padx=16, pady=8, cursor="hand2",
                  activebackground=HOVER,
                  command=self._add_item).pack(ipadx=20)
        self._add_btn_frame = add_frame  # 保存引用，用于 before 定位

    def _render_all_cards(self):
        """清空并重建所有卡片，最后追加添加按钮。"""
        for w in self._inner.winfo_children():
            w.destroy()
        self._cards.clear()

        for idx, item in enumerate(self._items):
            self._render_card(idx, item)
        self._render_add_button()

    def _render_card(self, idx: int, item: dict):
        """渲染单张菜单项卡片。"""
        card = tk.Frame(self._inner, bg=SURFACE, bd=0,
                        highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=ACCENT)
        # 确保卡片在添加按钮之前
        pack_kw = {"fill": "x", "pady": 3, "padx": 0, "ipady": 2}
        if hasattr(self, '_add_btn_frame') and self._add_btn_frame.winfo_exists():
            pack_kw["before"] = self._add_btn_frame
        card.pack(**pack_kw)

        # ═══ 第一行：序号 + 标签 + 类型徽章 + 上下移动 + 删除 ═══
        row1 = tk.Frame(card, bg=SURFACE)
        row1.pack(fill="x", padx=8, pady=(6, 2))

        # 序号
        tk.Label(row1, text=f"#{idx+1}",
                 font=("Consolas", 10, "bold"), bg=SURFACE, fg=DIM,
                 width=4, anchor="w").pack(side="left")

        # 标签输入
        label_var = tk.StringVar(value=item.get("label", ""))
        label_entry = tk.Entry(row1, textvariable=label_var,
                               font=("Segoe UI", 10, "bold"), bg=BG, fg=FG,
                               bd=0, insertbackground=FG,
                               relief="flat")
        label_entry.pack(side="left", fill="x", expand=True, ipady=3, padx=(4, 6))

        # 类型选择器
        type_var = tk.StringVar(value=item.get("action_type", "log"))
        type_frame = tk.Frame(row1, bg=SURFACE)
        type_frame.pack(side="left", padx=(0, 4))

        type_combo = ttk.Combobox(type_frame, textvariable=type_var,
            values=["log", "key", "key_combo", "macro", "script"],
            width=9, state="readonly",
            font=("Segoe UI", 9))
        type_combo.pack(side="left")

        # 类型徽章标签
        badge = tk.Label(type_frame, text="",
                         font=("Segoe UI", 8, "bold"),
                         bg=self._type_color(item.get("action_type", "log")),
                         fg="white", padx=6, pady=1)
        badge.pack(side="left", padx=4)

        # 上移 / 下移
        nav_frame = tk.Frame(row1, bg=SURFACE)
        nav_frame.pack(side="left", padx=(4, 2))
        tk.Button(nav_frame, text="▲", font=("Segoe UI", 8),
                  bg=SURFACE, fg=DIM, bd=0, padx=4, pady=0, cursor="hand2",
                  activebackground=HOVER,
                  command=lambda i=idx: self._move_item(i, -1)).pack(side="left")
        tk.Button(nav_frame, text="▼", font=("Segoe UI", 8),
                  bg=SURFACE, fg=DIM, bd=0, padx=4, pady=0, cursor="hand2",
                  activebackground=HOVER,
                  command=lambda i=idx: self._move_item(i, 1)).pack(side="left")

        # 删除
        def make_del(i=idx):
            return lambda: self._delete_item(i)
        tk.Button(row1, text="✕", font=("Segoe UI", 9, "bold"),
                  bg=SURFACE, fg=RED, bd=0, padx=7, cursor="hand2",
                  activebackground=HOVER,
                  command=make_del()).pack(side="right")

        # ═══ 第二行：参数面板 ═══
        param_container = tk.Frame(card, bg=BG)
        param_container.pack(fill="x", padx=12, pady=(2, 4), ipady=3)

        param_panel = ActionParamPanel(param_container,
            action_type=item.get("action_type", "log"),
            payload=item.get("action_payload", ""),
            on_change=lambda c=card: self._update_card_preview(c))
        param_panel.pack(fill="x")

        # ═══ 第三行：预览 ═══
        preview_label = tk.Label(card, text="",
                                 font=("Segoe UI", 8), bg=SURFACE, fg=DIM,
                                 anchor="w")
        preview_label.pack(fill="x", padx=12, pady=(0, 6))

        # 类型切换联动
        def on_type_change(e=None, tv=type_var, ap=param_panel, bl=badge, c=card):
            new_type = tv.get()
            ap.switch_type(new_type)
            bl.config(bg=self._type_color(new_type), text=TYPE_NAMES.get(new_type, ""))
            self._update_card_preview(c)
        type_combo.bind("<<ComboboxSelected>>", on_type_change)

        # 初始化徽章
        badge.config(text=TYPE_NAMES.get(item.get("action_type", "log"), ""))
        self._update_card_preview(card)

        self._cards.append({
            "idx": idx,
            "frame": card,
            "label_var": label_var,
            "type_var": type_var,
            "param_panel": param_panel,
            "preview_label": preview_label,
            "badge": badge,
        })

    def _type_color(self, action_type: str) -> str:
        return TYPE_COLORS.get(action_type, DIM)

    def _update_card_preview(self, card):
        """更新某张卡片的预览文字。"""
        for c in self._cards:
            if c["frame"] is card:
                preview_text = c["param_panel"].get_preview()
                c["preview_label"].config(text=f"预览: {preview_text}")
                break

    # ── 操作 ──

    def _add_item(self):
        """添加新菜单项（最多12项）。"""
        if len(self._items) >= 12:
            messagebox.showwarning("已达上限", "最多12项菜单。", parent=self.root)
            return
        new_item = {"label": "新命令", "action_type": "log", "action_payload": ""}
        self._items.append(new_item)
        self._render_card(len(self._items) - 1, new_item)
        self._update_status()
        # 滚动到底部
        self.root.after(50, lambda: self._canvas.yview_moveto(1.0))

    def _delete_item(self, idx: int):
        """删除菜单项（支持撤销）。"""
        if len(self._items) <= 1:
            messagebox.showwarning("无法删除", "至少保留一项菜单。", parent=self.root)
            return
        self._last_deleted = dict(self._items[idx])
        self._last_deleted_idx = idx
        self._items.pop(idx)
        self._rebuild()
        self._status(f"已删除「{self._last_deleted.get('label', '')}」— Ctrl+Z 撤销")

    def _undo_delete(self):
        """撤销上一次删除。"""
        if self._last_deleted is None or self._last_deleted_idx < 0:
            return
        idx = min(self._last_deleted_idx, len(self._items))
        self._items.insert(idx, self._last_deleted)
        self._last_deleted = None
        self._last_deleted_idx = -1
        self._rebuild()
        self._status("✅ 已撤销删除")

    def _move_item(self, idx: int, direction: int):
        """上移 (-1) 或下移 (+1)。"""
        new_idx = idx + direction
        if 0 <= new_idx < len(self._items):
            self._items[idx], self._items[new_idx] = \
                self._items[new_idx], self._items[idx]
            self._rebuild()
            self._update_status()

    def _rebuild(self):
        """重建卡片（重新编号）。"""
        for w in self._inner.winfo_children():
            w.destroy()
        self._cards.clear()
        for idx, item in enumerate(self._items):
            self._render_card(idx, item)
        self._render_add_button()
        self._update_status()

    # ── 保存 / 关闭 ──

    def _save(self):
        """保存配置。"""
        # 从卡片收集数据
        for card in self._cards:
            i = card["idx"]
            if i < len(self._items):
                self._items[i]["label"] = card["label_var"].get()
                self._items[i]["action_type"] = card["type_var"].get()
                self._items[i]["action_payload"] = card["param_panel"].get_payload()

        self._data["menu"]["items"] = self._items
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False)

        if self._on_save:
            self._on_save(self._data)

        self._status(f"✅ 已保存 {len(self._items)} 个菜单项 — {time.strftime('%H:%M:%S')}")
        # 短暂高亮状态栏
        self._status_label.config(fg=GREEN)
        self.root.after(2000, lambda: self._status_label.config(fg=DIM))

    def _close(self):
        """关闭窗口。"""
        try:
            self.root.destroy()
        except Exception:
            pass
        if self._on_close:
            self._on_close()

    def _update_status(self):
        """更新状态栏计数。"""
        count = len(self._items)
        self._count_label.config(text=f"· {count} 个菜单项")

    def _status(self, text: str):
        """设置状态栏消息。"""
        self._status_label.config(text=text)
