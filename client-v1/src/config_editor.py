"""WavePie 配置编辑器 — 图形界面编辑 config.yaml。

功能：
  - 浏览/编辑 12 项径向菜单（id、标签、图标、动作）
  - 浏览/编辑 副键直接动作
  - 浏览/编辑 滚轮映射
  - 保存到 config.yaml

用法：
    python -m src.config_editor
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import load_config, save_config, AppConfig


# ── 颜色 ──
BG = "#1A1A2E"
FG = "#FFFFFF"
CARD = "#2D2D44"
ACCENT = "#4A90D9"
DIM = "#888899"


class ConfigEditor:
    """配置编辑器主窗口。"""

    def __init__(self, config_path: str = None):
        self._config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.yaml",
        )
        self.config: AppConfig = load_config(self._config_path)

        self.root = tk.Tk()
        self.root.title("WavePie 配置编辑器")
        self.root.geometry("900x600")
        self.root.configure(bg=BG)
        self.root.minsize(700, 450)

        self._build_ui()

        # 关闭窗口时检查是否未保存
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI 构建 ──

    def _build_ui(self):
        # 主布局：左侧导航，右侧内容
        paned = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, bg=BG, sashwidth=2, sashrelief=tk.RAISED
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
            ("scroll", "滚轮映射"),
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

        # 底部保存按钮
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
        # 更新导航高亮
        for btn, k in self._nav_btns:
            btn.configure(bg=ACCENT if k == key else BG)
        # 渲染对应内容
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

    # ── 渲染：菜单项 ──

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

        # 找到主按钮(button_id=0)的菜单项
        btn0 = None
        for b in self.config.buttons:
            if b.button_id == 0:
                btn0 = b
                break
        if not btn0 or not btn0.menu_items:
            tk.Label(frame, text="未找到菜单项配置", bg=BG, fg="red").pack()
            return

        # 滚动区域
        canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 每行一个菜单项
        self._menu_widgets = []
        for idx, item in enumerate(btn0.menu_items):
            item_frame = tk.Frame(scroll_frame, bg=CARD, bd=0, highlightthickness=0)
            item_frame.pack(fill=tk.X, pady=3, ipady=4)

            row = tk.Frame(item_frame, bg=CARD)
            row.pack(fill=tk.X, padx=8, pady=2)

            # 序号
            tk.Label(row, text=f"{idx+1}.", font=("Segoe UI", 9), bg=CARD, fg=DIM, width=2).pack(side=tk.LEFT)

            # 图标
            icon_var = tk.StringVar(value=item.icon)
            tk.Label(row, text="图标:", bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(side=tk.LEFT)
            icon_entry = tk.Entry(row, textvariable=icon_var, width=4, bg="#3D3D5C", fg=FG, bd=0, font=("Segoe UI", 10))
            icon_entry.pack(side=tk.LEFT, padx=(2, 8), ipady=2)

            # 标签
            label_var = tk.StringVar(value=item.label)
            tk.Label(row, text="标签:", bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(side=tk.LEFT)
            label_entry = tk.Entry(row, textvariable=label_var, width=14, bg="#3D3D5C", fg=FG, bd=0, font=("Segoe UI", 10))
            label_entry.pack(side=tk.LEFT, padx=(2, 8), ipady=2)

            # 动作类型
            type_var = tk.StringVar(value=item.action_type)
            type_combo = ttk.Combobox(row, textvariable=type_var, values=["log", "key_combo", "macro", "script"], width=10)
            type_combo.configure(state="readonly")
            type_combo.pack(side=tk.LEFT, padx=(2, 8))

            # 动作参数
            payload_var = tk.StringVar(value=item.action_payload)
            tk.Label(row, text="参数:", bg=CARD, fg=DIM, font=("Segoe UI", 9)).pack(side=tk.LEFT)
            payload_entry = tk.Entry(row, textvariable=payload_var, width=20, bg="#3D3D5C", fg=FG, bd=0, font=("Segoe UI", 10))
            payload_entry.pack(side=tk.LEFT, padx=(2, 8), ipady=2)

            # 储存引用以便保存
            self._menu_widgets.append({
                "idx": idx,
                "item": item,
                "icon_var": icon_var,
                "label_var": label_var,
                "type_var": type_var,
                "payload_var": payload_var,
            })

    # ── 渲染：直接动作 ──

    def _render_direct_actions(self):
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(
            frame, text="副键直接动作",
            font=("Segoe UI", 14, "bold"), bg=BG, fg=FG,
        ).pack(anchor="nw")

        self._direct_widgets = []
        for b in self.config.buttons:
            if b.button_id == 0:
                continue  # 跳过主按钮
            card = tk.Frame(frame, bg=CARD, bd=0)
            card.pack(fill=tk.X, pady=4, ipady=6)

            row = tk.Frame(card, bg=CARD)
            row.pack(fill=tk.X, padx=10, pady=2)

            tk.Label(row, text=f"button_id={b.button_id}", font=("Segoe UI", 9, "bold"), bg=CARD, fg=ACCENT, width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{b.label}", font=("Segoe UI", 9), bg=CARD, fg=DIM, width=16, anchor="w").pack(side=tk.LEFT)

            type_var = tk.StringVar(value=b.action_type)
            ttk.Combobox(row, textvariable=type_var, values=["log", "key_combo", "macro", "script"], width=10, state="readonly").pack(side=tk.LEFT, padx=4)

            payload_var = tk.StringVar(value=b.action_payload)
            tk.Entry(row, textvariable=payload_var, width=24, bg="#3D3D5C", fg=FG, bd=0, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=4, ipady=2)

            self._direct_widgets.append({
                "button": b,
                "type_var": type_var,
                "payload_var": payload_var,
            })

        if not self._direct_widgets:
            tk.Label(frame, text="（未配置副键直接动作）", bg=BG, fg=DIM, font=("Segoe UI", 10)).pack(pady=20)

    # ── 渲染：滚轮 ──

    def _render_scroll(self):
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(
            frame, text="滚轮映射",
            font=("Segoe UI", 14, "bold"), bg=BG, fg=FG,
        ).pack(anchor="nw")

        card = tk.Frame(frame, bg=CARD, bd=0)
        card.pack(fill=tk.X, pady=8, ipady=10)

        # 上滚
        row_up = tk.Frame(card, bg=CARD)
        row_up.pack(fill=tk.X, padx=10, pady=4)
        tk.Label(row_up, text="⬆  上滚", font=("Segoe UI", 10, "bold"), bg=CARD, fg=FG, width=8).pack(side=tk.LEFT)
        self._scroll_up_type = tk.StringVar(value=self.config.scroll.up_action_type)
        ttk.Combobox(row_up, textvariable=self._scroll_up_type, values=["log", "key_combo", "macro", "script"], width=10, state="readonly").pack(side=tk.LEFT, padx=4)
        self._scroll_up_payload = tk.StringVar(value=self.config.scroll.up_payload)
        tk.Entry(row_up, textvariable=self._scroll_up_payload, width=30, bg="#3D3D5C", fg=FG, bd=0, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=4, ipady=2)

        # 下滚
        row_down = tk.Frame(card, bg=CARD)
        row_down.pack(fill=tk.X, padx=10, pady=4)
        tk.Label(row_down, text="⬇  下滚", font=("Segoe UI", 10, "bold"), bg=CARD, fg=FG, width=8).pack(side=tk.LEFT)
        self._scroll_down_type = tk.StringVar(value=self.config.scroll.down_action_type)
        ttk.Combobox(row_down, textvariable=self._scroll_down_type, values=["log", "key_combo", "macro", "script"], width=10, state="readonly").pack(side=tk.LEFT, padx=4)
        self._scroll_down_payload = tk.StringVar(value=self.config.scroll.down_payload)
        tk.Entry(row_down, textvariable=self._scroll_down_payload, width=30, bg="#3D3D5C", fg=FG, bd=0, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=4, ipady=2)

    # ── 渲染：手势参数 ──

    def _render_gesture(self):
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(
            frame, text="手势引擎参数",
            font=("Segoe UI", 14, "bold"), bg=BG, fg=FG,
        ).pack(anchor="nw")

        card = tk.Frame(frame, bg=CARD, bd=0)
        card.pack(fill=tk.X, pady=8, ipady=16)

        fields = [
            ("死区 (dead_zone)", "gesture", "dead_zone", 0.05),
            ("灵敏度 (sensitivity)", "gesture", "sensitivity", 1.2),
        ]

        self._gesture_entries = {}
        for label, section, key, default in fields:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill=tk.X, padx=10, pady=4)
            tk.Label(row, text=label, font=("Segoe UI", 10), bg=CARD, fg=FG, width=22, anchor="w").pack(side=tk.LEFT)
            val = getattr(self.config.gesture, key, default)
            var = tk.StringVar(value=str(val))
            entry = tk.Entry(row, textvariable=var, width=12, bg="#3D3D5C", fg=FG, bd=0, font=("Segoe UI", 10), justify=tk.CENTER)
            entry.pack(side=tk.LEFT, padx=4, ipady=2)
            self._gesture_entries[key] = var

        tk.Label(
            card, text="提示：死区越大越不易误触，灵敏度越大光标移动越快",
            font=("Segoe UI", 8), bg=CARD, fg=DIM,
        ).pack(padx=10, pady=(8, 0))

    # ── 渲染：UI 外观 ──

    def _render_ui(self):
        frame = tk.Frame(self._content, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        tk.Label(
            frame, text="UI 外观", font=("Segoe UI", 14, "bold"), bg=BG, fg=FG,
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
            tk.Label(frame, text=line, font=("Segoe UI", 10), bg=BG, fg=FG).pack(anchor="nw", pady=2)

    # ── 保存 ──

    def _save_config(self):
        """将界面修改写回 config.yaml。"""
        try:
            # 1. 更新菜单项
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
                        item.icon = w["icon_var"].get()
                        item.label = w["label_var"].get()
                        item.action_type = w["type_var"].get()
                        item.action_payload = w["payload_var"].get()

            # 2. 更新直接动作
            if hasattr(self, "_direct_widgets"):
                for w in self._direct_widgets:
                    b = w["button"]
                    b.action_type = w["type_var"].get()
                    b.action_payload = w["payload_var"].get()

            # 3. 更新滚轮
            if hasattr(self, "_scroll_up_type"):
                self.config.scroll.up_action_type = self._scroll_up_type.get()
                self.config.scroll.up_payload = self._scroll_up_payload.get()
                self.config.scroll.down_action_type = self._scroll_down_type.get()
                self.config.scroll.down_payload = self._scroll_down_payload.get()

            # 4. 更新手势参数
            if hasattr(self, "_gesture_entries"):
                try:
                    self.config.gesture.dead_zone = float(self._gesture_entries["dead_zone"].get())
                    self.config.gesture.sensitivity = float(self._gesture_entries["sensitivity"].get())
                except ValueError:
                    messagebox.showwarning("参数错误", "死区和灵敏度必须为数字")

            # 写入文件
            save_config(self.config, self._config_path)
            messagebox.showinfo("已保存", f"配置已保存到:\n{self._config_path}")

        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    # ── 关闭 ──

    def _on_close(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    editor = ConfigEditor()
    editor.run()
