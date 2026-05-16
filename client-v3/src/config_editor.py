"""WavePie V2 配置编辑器 — 编辑菜单项。"""

import os
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable

import yaml

BG = "#2B2B2B"
FG = "#FFFFFF"
ACCENT = "#4A90D9"
CARD = "#3C3C3C"
DIM = "#999999"


class ConfigEditor:
    """菜单项编辑器（V2 精简版）。"""

    def __init__(self, config_path: str, master=None,
                 on_close: Callable = None,
                 on_save: Callable = None):
        self._path = config_path
        self._on_close = on_close
        self._on_save = on_save

        # 加载配置
        with open(config_path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

        self.root = tk.Toplevel(master)
        self.root.title("WavePie V2 设置")
        self.root.geometry("640x480")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.transient(master)
        self.root.grab_set()

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        # 标题
        tk.Label(
            self.root, text="菜单项编辑",
            font=("Segoe UI", 14, "bold"), bg=BG, fg=FG,
        ).pack(anchor="nw", padx=16, pady=(16, 8))

        # 滚轮容器
        canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self._inner = tk.Frame(canvas, bg=BG)
        self._inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(16, 0))
        scrollbar.pack(side="right", fill="y", padx=(0, 16))

        # 渲染菜单项
        self._items = self._data.get("menu", {}).get("items", [])
        self._widgets = []
        for idx, item in enumerate(self._items):
            self._render_item(idx, item)

        # 添加按钮
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(fill="x", padx=16, pady=12)

        tk.Button(
            btn_frame, text="➕ 添加项", font=("Segoe UI", 9),
            bg=CARD, fg=FG, bd=0, padx=12, pady=4, cursor="hand2",
            command=self._add_item,
        ).pack(side="left")

        tk.Button(
            btn_frame, text="💾 保存", font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg="white", bd=0, padx=20, pady=4, cursor="hand2",
            command=self._save,
        ).pack(side="right", padx=(0, 0))

    def _render_item(self, idx: int, item: dict):
        card = tk.Frame(self._inner, bg=CARD, bd=0)
        card.pack(fill="x", pady=3, ipady=4, padx=2)

        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=8, pady=2)

        # 标签
        label_var = tk.StringVar(value=item.get("label", ""))
        tk.Label(row, text="标签:", font=("Segoe UI", 9, "bold"),
                 bg=CARD, fg=ACCENT).pack(side="left")
        label_entry = tk.Entry(row, textvariable=label_var,
                               font=("Segoe UI", 9), bg=BG, fg=FG,
                               bd=0, width=14, insertbackground=FG)
        label_entry.pack(side="left", padx=(4, 8), ipady=2)

        # 类型
        type_var = tk.StringVar(value=item.get("action_type", "log"))
        type_combo = ttk.Combobox(
            row, textvariable=type_var,
            values=["log", "key", "key_combo", "macro", "script"],
            width=8, state="readonly",
        )
        type_combo.pack(side="left", padx=4)

        # 参数
        payload_var = tk.StringVar(value=item.get("action_payload", ""))
        payload_entry = tk.Entry(row, textvariable=payload_var,
                                 font=("Segoe UI", 9), bg=BG, fg=FG,
                                 bd=0, width=20, insertbackground=FG)
        payload_entry.pack(side="left", padx=(4, 8), ipady=2)

        # 删除
        def make_del(i=idx):
            def delete():
                if len(self._items) > 1:
                    self._items.pop(i)
                    self._rebuild()
            return delete

        tk.Button(
            row, text="✕", font=("Segoe UI", 8, "bold"),
            bg="#E74C3C", fg="white", bd=0, padx=6, pady=0,
            cursor="hand2", command=make_del(),
        ).pack(side="right", padx=(4, 0))

        self._widgets.append({
            "idx": idx,
            "label_var": label_var,
            "type_var": type_var,
            "payload_var": payload_var,
        })

    def _rebuild(self):
        for w in self._inner.winfo_children():
            w.destroy()
        self._widgets.clear()
        for idx, item in enumerate(self._items):
            self._render_item(idx, item)

    def _add_item(self):
        new_item = {"label": "新命令", "action_type": "log", "action_payload": ""}
        self._items.append(new_item)
        idx = len(self._items) - 1
        self._render_item(idx, new_item)

    def _save(self):
        # 从控件读取
        for w in self._widgets:
            idx = w["idx"]
            if idx < len(self._items):
                self._items[idx]["label"] = w["label_var"].get()
                self._items[idx]["action_type"] = w["type_var"].get()
                self._items[idx]["action_payload"] = w["payload_var"].get()

        self._data["menu"]["items"] = self._items
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False)

        # 通知 app
        if self._on_save:
            self._on_save(self._data)

        self._toast("✅ 已保存")
        self.root.after(400, self._close)

    def _toast(self, text: str):
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.configure(bg="#2ECC71")
        tk.Label(t, text=text, font=("Segoe UI", 10, "bold"),
                 bg="#2ECC71", fg="white", padx=20, pady=8).pack()
        t.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        tw, th = t.winfo_width(), t.winfo_height()
        t.geometry(f"+{sw - tw - 40}+{sh - th - 80}")
        t.after(1500, t.destroy)

    def _close(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        if self._on_close:
            self._on_close()
