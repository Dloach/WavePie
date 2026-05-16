"""WavePie V3 配置编辑器。"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable
import yaml

BG = "#2B2B2B"
FG = "#FFFFFF"
ACCENT = "#4A90D9"
CARD = "#3C3C3C"
DIM = "#999999"

# VK 映射（来自 executor/actions.py）
VK_DISPLAY = {
    "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win",
    "enter": "Enter", "tab": "Tab", "space": "Space",
    "backspace": "Backspace", "delete": "Delete", "escape": "Esc",
    "up": "↑", "down": "↓", "left": "←", "right": "→",
    "volume_up": "音量+", "volume_down": "音量-", "volume_mute": "静音",
    "prtsc": "PrtSc",
}

class KeyRecorderDialog:
    """按键录制弹窗。"""
    def __init__(self, parent):
        self._result: Optional[str] = None
        self._keys = set()
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("录制快捷键")
        self.dialog.geometry("360x150")
        self.dialog.configure(bg=BG)
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        tk.Label(self.dialog, text="按下你想录制的组合键...",
                 font=("Segoe UI", 11), bg=BG, fg=FG).pack(pady=(20, 8))
        self._display = tk.Label(self.dialog, text="（等待按键）",
                                 font=("Segoe UI", 18, "bold"), bg=BG, fg=ACCENT)
        self._display.pack(pady=8)
        btn_frame = tk.Frame(self.dialog, bg=BG)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="✅ 确认", font=("Segoe UI", 10, "bold"),
                  bg=ACCENT, fg="white", bd=0, padx=16, pady=4, cursor="hand2",
                  command=self._confirm).pack(side="left", padx=4)
        tk.Button(btn_frame, text="❌ 取消", font=("Segoe UI", 10),
                  bg=CARD, fg=FG, bd=0, padx=16, pady=4, cursor="hand2",
                  command=self._cancel).pack(side="left", padx=4)
        self.dialog.protocol("WM_DELETE_WINDOW", self._cancel)
        self._start_listener()

    def _start_listener(self):
        import threading
        self._listening = True
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        from pynput import keyboard
        def on_press(key):
            if not self._listening:
                return
            try:
                k = key.char.lower()
            except AttributeError:
                k = key.name.lower() if hasattr(key, 'name') else str(key)
            self._keys.add(k)
            display = " + ".join(sorted(self._keys, key=lambda x: 0 if x in ("ctrl","alt","shift","win") else 1))
            self.dialog.after(0, lambda t=display: self._display.config(text=t or "（等待按键）"))
        def on_release(key):
            if not self._listening:
                return False
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

    def _confirm(self):
        if self._keys:
            self._result = "+".join(sorted(self._keys, key=lambda x: 0 if x in ("ctrl","alt","shift","win") else 1))
        self._cleanup()
    def _cancel(self):
        self._result = None
        self._cleanup()
    def _cleanup(self):
        self._listening = False
        try: self.dialog.destroy()
        except: pass
    def show(self) -> Optional[str]:
        self.dialog.wait_window()
        return self._result


class ActionParamFrame(tk.Frame):
    """动态参数面板——根据 action_type 切换。"""
    def __init__(self, parent, action_type="log", payload="",
                 on_change=None):
        super().__init__(parent, bg=BG)
        self._current_type = action_type
        self._payload_var = tk.StringVar(value=payload)
        self._on_change = on_change
        self._widget = None
        self._build()

    def get_payload(self) -> str:
        if self._current_type == "key_combo" and hasattr(self, '_combo_var'):
            return self._combo_var.get()
        return self._payload_var.get()

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

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
            self._build_text()

    def switch_type(self, new_type: str):
        self._current_type = new_type
        self._build()

    def _build_key(self):
        entry = tk.Entry(self, textvariable=self._payload_var,
                         font=("Segoe UI", 9), bg=BG, fg=FG,
                         bd=0, width=18, insertbackground=FG)
        entry.pack(side="left", ipady=2)
        entry.insert(0, self._payload_var.get())
        tk.Label(self, text="例如: enter, volume_up",
                 font=("Segoe UI", 8), bg=BG, fg=DIM).pack(side="left", padx=4)

    def _build_key_combo(self):
        self._combo_var = tk.StringVar(value=self._payload_var.get())
        entry = tk.Entry(self, textvariable=self._combo_var,
                         font=("Segoe UI", 9), bg=BG, fg=FG,
                         bd=0, width=18, insertbackground=FG)
        entry.pack(side="left", ipady=2)
        tk.Button(self, text="🎬 录制", font=("Segoe UI", 8),
                  bg=ACCENT, fg="white", bd=0, padx=8, pady=1,
                  cursor="hand2",
                  command=self._record).pack(side="left", padx=4)

    def _record(self):
        result = KeyRecorderDialog(self.winfo_toplevel()).show()
        if result:
            self._combo_var.set(result)

    def _build_macro(self):
        tk.Label(self, text="每行一个按键/组合键",
                 font=("Segoe UI", 8), bg=BG, fg=DIM).pack(side="left", padx=2)
        tk.Button(self, text="编辑", font=("Segoe UI", 8),
                  bg=ACCENT, fg="white", bd=0, padx=10, pady=1, cursor="hand2",
                  command=self._edit_macro).pack(side="left", padx=4)

    def _edit_macro(self):
        d = tk.Toplevel(self.winfo_toplevel())
        d.title("编辑宏")
        d.geometry("400x300")
        d.configure(bg=BG)
        d.transient(self.winfo_toplevel())
        d.grab_set()
        text = tk.Text(d, bg=BG, fg=FG, font=("Consolas", 10),
                       bd=0, insertbackground=FG)
        text.pack(fill="both", expand=True, padx=8, pady=8)
        text.insert("1.0", self._payload_var.get())
        def save():
            self._payload_var.set(text.get("1.0", "end-1c"))
            d.destroy()
        tk.Button(d, text="✅ 保存", font=("Segoe UI", 10, "bold"),
                  bg=ACCENT, fg="white", bd=0, padx=16, pady=4,
                  cursor="hand2", command=save).pack(pady=8)

    def _build_script(self):
        tk.Label(self, text=".bat / .ps1 / .py",
                 font=("Segoe UI", 8), bg=BG, fg=DIM).pack(side="left", padx=2)
        tk.Button(self, text="浏览…", font=("Segoe UI", 8),
                  bg=ACCENT, fg="white", bd=0, padx=10, pady=1, cursor="hand2",
                  command=self._browse_script).pack(side="left", padx=4)

    def _browse_script(self):
        path = filedialog.askopenfilename(
            title="选择脚本", parent=self,
            filetypes=[("脚本", "*.bat;*.ps1;*.py;*.exe"), ("所有文件", "*.*")])
        if path:
            self._payload_var.set(path)

    def _build_text(self):
        entry = tk.Entry(self, textvariable=self._payload_var,
                         font=("Segoe UI", 9), bg=BG, fg=FG,
                         bd=0, width=22, insertbackground=FG)
        entry.pack(side="left", ipady=2)


class ConfigEditor:
    def __init__(self, config_path: str, master=None,
                 on_close: Callable = None,
                 on_save: Callable = None):
        self._path = config_path
        self._on_close = on_close
        self._on_save = on_save
        with open(config_path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

        self.root = tk.Toplevel(master)
        self.root.title("WavePie 设置")
        self.root.geometry("720x560")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.transient(master)
        self.root.grab_set()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        tk.Label(self.root, text="菜单项编辑",
                 font=("Segoe UI", 14, "bold"), bg=BG, fg=FG,
                 ).pack(anchor="nw", padx=16, pady=(16, 8))

        canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self._inner = tk.Frame(canvas, bg=BG)
        self._inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(16, 0))
        scrollbar.pack(side="right", fill="y", padx=(0, 16))

        self._items = self._data.get("menu", {}).get("items", [])
        self._widgets = []
        for idx, item in enumerate(self._items):
            self._render_item(idx, item)

        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(fill="x", padx=16, pady=12)
        tk.Button(btn_frame, text="➕ 添加项", font=("Segoe UI", 9),
                  bg=CARD, fg=FG, bd=0, padx=12, pady=4, cursor="hand2",
                  command=self._add_item).pack(side="left")
        tk.Button(btn_frame, text="💾 保存", font=("Segoe UI", 10, "bold"),
                  bg=ACCENT, fg="white", bd=0, padx=20, pady=4, cursor="hand2",
                  command=self._save).pack(side="right")

    def _render_item(self, idx: int, item: dict):
        card = tk.Frame(self._inner, bg=CARD, bd=0)
        card.pack(fill="x", pady=3, ipady=4, padx=2)
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=8, pady=2)

        # 标签
        label_var = tk.StringVar(value=item.get("label", ""))
        tk.Label(row, text="标签:", font=("Segoe UI", 9, "bold"),
                 bg=CARD, fg=ACCENT).pack(side="left")
        tk.Entry(row, textvariable=label_var, font=("Segoe UI", 9),
                 bg=BG, fg=FG, bd=0, width=12, insertbackground=FG,
                 ).pack(side="left", padx=(4, 8), ipady=2)

        # 类型
        type_var = tk.StringVar(value=item.get("action_type", "log"))
        type_combo = ttk.Combobox(row, textvariable=type_var,
            values=["log", "key", "key_combo", "macro", "script"],
            width=8, state="readonly")
        type_combo.pack(side="left", padx=4)

        # 参数面板（动态）
        param_frame = tk.Frame(row, bg=BG)
        param_frame.pack(side="left", fill="x", expand=True, padx=(4, 0))
        action_param = ActionParamFrame(param_frame,
            action_type=item.get("action_type", "log"),
            payload=item.get("action_payload", ""))
        action_param.pack(fill="x", expand=True)

        # 类型切换联动
        def on_type_change(*args, tv=type_var, ap=action_param):
            ap.switch_type(tv.get())
        type_combo.bind("<<ComboboxSelected>>", on_type_change)

        # 删除
        def make_del(i=idx):
            def d():
                if len(self._items) > 1:
                    self._items.pop(i); self._rebuild()
            return d
        tk.Button(row, text="✕", font=("Segoe UI", 8, "bold"),
                  bg="#E74C3C", fg="white", bd=0, padx=6, pady=0,
                  cursor="hand2", command=make_del(),
                  ).pack(side="right", padx=(4, 0))

        self._widgets.append({
            "idx": idx, "label_var": label_var, "type_var": type_var,
            "param": action_param,
        })

    def _rebuild(self):
        for w in self._inner.winfo_children(): w.destroy()
        self._widgets.clear()
        for idx, item in enumerate(self._items):
            self._render_item(idx, item)

    def _add_item(self):
        self._items.append({"label": "新命令", "action_type": "log", "action_payload": ""})
        self._render_item(len(self._items)-1, self._items[-1])

    def _save(self):
        for w in self._widgets:
            i = w["idx"]
            if i < len(self._items):
                self._items[i]["label"] = w["label_var"].get()
                self._items[i]["action_type"] = w["type_var"].get()
                self._items[i]["action_payload"] = w["param"].get_payload()
        self._data["menu"]["items"] = self._items
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False)
        if self._on_save:
            self._on_save(self._data)
        self._toast("✅ 已保存")
        self.root.after(400, self._close)

    def _toast(self, text: str):
        t = tk.Toplevel(self.root)
        t.overrideredirect(True); t.attributes("-topmost", True)
        t.configure(bg="#2ECC71")
        tk.Label(t, text=text, font=("Segoe UI", 10, "bold"),
                 bg="#2ECC71", fg="white", padx=20, pady=8).pack()
        t.update_idletasks()
        sw, sh = t.winfo_screenwidth(), t.winfo_screenheight()
        tw, th = t.winfo_width(), t.winfo_height()
        t.geometry(f"+{sw-tw-40}+{sh-th-80}")
        t.after(1500, t.destroy)

    def _close(self):
        try: self.root.destroy()
        except: pass
        if self._on_close: self._on_close()
