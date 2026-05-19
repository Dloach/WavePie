"""WavePie V3 OverlayUI — 纯净版（仅窗口 + 准星）。"""

import math
import time
import tkinter as tk
from typing import Callable, Optional

VEIL    = "#0A0A18"
ACCENT  = "#4466DD"
SIGHT_INNER = "#FFFFFF"
SIGHT_OUTER = "#6688EE"
SIGHT_LINE  = "#AABBFF"
TEXT_FG = "#FFFFFF"
TEXT_DIM = "#7777AA"


class OverlayUI:
    def __init__(self, config, on_execute: Callable = None):
        self._cfg = config
        self._on_execute = on_execute
        self._vx, self._vy, self._vw, self._vh = self._get_virtual_screen()

        self.root = tk.Tk()
        self.root.title("WavePie")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.attributes("-transparentcolor", "black")
        self._canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.root.bind("<Escape>", lambda e: self.deactivate())
        self._idle_geom()

        self._state = "idle"
        self._cx = 0.0
        self._cy = 0.0
        self._sx = 0.0
        self._sy = 0.0
        self._ids = {}

    # ── 虚拟桌面 ──
    @staticmethod
    def _get_virtual_screen():
        try:
            import ctypes
            u = ctypes.windll.user32
            vx = u.GetSystemMetrics(76)
            vy = u.GetSystemMetrics(77)
            vw = u.GetSystemMetrics(78)
            vh = u.GetSystemMetrics(79)
            if vw > 0 and vh > 0: return vx, vy, vw, vh
        except Exception: pass
        return 0, 0, 1920, 1080

    def _idle_geom(self):
        self.root.geometry("1x1+0+0")
        self.root.attributes("-alpha", 0.01)

    def _show_geom(self):
        self.root.attributes("-alpha", 0.85)
        self.root.geometry(f"{self._vw}x{self._vh}+{self._vx}+{self._vy}")
        self.root.update_idletasks()
        self._canvas.configure(width=self._vw, height=self._vh)
        self._canvas.pack()
        self.root.lift()
        self.root.focus_force()

    # ── 公开 API ──
    @property
    def state(self) -> str:
        return self._state

    @property
    def selected_idx(self) -> int:
        return -1  # TODO

    def activate(self):
        if self._state != "idle": return
        self._state = "menu_open"
        self._cx, self._cy = 960, 540  # 准星初始位置
        self._sx = 0.0; self._sy = 0.0
        self._show_geom()
        self.root.lift()
        self.root.focus_force()

    def deactivate(self):
        if self._state == "idle": return
        self._state = "idle"
        self._canvas.delete("all")
        self._ids.clear()
        self._canvas.pack_forget()
        self._idle_geom()

    def set_sight(self, rx: float, ry: float):
        """更新准星位置（归一化 -1..1），约束在圆内。"""
        if self._state != "menu_open": return
        mr = 400.0  # 临时外径
        sx = rx * mr
        sy = ry * mr
        d = math.hypot(sx, sy)
        if d > mr:
            s = mr / d
            sx *= s; sy *= s
        self._sx = sx
        self._sy = sy
        self._redraw()

    # ── 绘制 ──
    def _init_sight(self):
        """创建准星 Canvas 元素（一次性）。"""
        c = self._canvas
        r = 5.0; cl = 12.0
        self._ids["sight_dot"] = c.create_oval(
            0, 0, 1, 1, fill=SIGHT_INNER, outline="")
        self._ids["sight_outer"] = c.create_oval(
            0, 0, 1, 1, fill="", outline=SIGHT_OUTER, width=1.5)
        self._ids["sight_lines"] = []
        for _ in range(4):
            self._ids["sight_lines"].append(
                c.create_line(0, 0, 1, 1, fill=SIGHT_LINE, width=1))

    def _redraw(self):
        if "sight_dot" not in self._ids:
            self._init_sight()
        c, ids = self._canvas, self._ids
        sx = self._cx + self._sx
        sy = self._cy + self._sy
        r, ro, cl = 5.0, 15.0, 12.0
        c.coords(ids["sight_dot"], sx-r, sy-r, sx+r, sy+r)
        c.coords(ids["sight_outer"], sx-ro, sy-ro, sx+ro, sy+ro)
        c.coords(ids["sight_lines"][0], sx-cl, sy, sx-ro, sy)
        c.coords(ids["sight_lines"][1], sx+ro, sy, sx+cl, sy)
        c.coords(ids["sight_lines"][2], sx, sy-cl, sx, sy-ro)
        c.coords(ids["sight_lines"][3], sx, sy+ro, sx, sy+cl)
