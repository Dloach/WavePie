"""OverlayUI — 全屏透明径向菜单（V2 精简版）。

接收 BLE 传回的扇区索引 → 高亮对应项。
"""

import math
import time
import tkinter as tk
from typing import Callable, Optional

BG = "#2B2B2B"
FG = "#FFFFFF"
ACCENT = "#4A90D9"
HIGHLIGHT = "#F5A623"
DIM = "#999999"
THROTTLE_S = 1.0 / 30.0


class OverlayUI:
    def __init__(self, config, on_execute: Callable = None):
        self._cfg = config
        self._on_execute = on_execute

        self.root = tk.Tk()
        self.root.title("WavePie")
        self.root.configure(bg="black")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.attributes("-alpha", 0.85)

        self._canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        self._state = "idle"
        self._n = 0
        self._cx = 0.0
        self._cy = 0.0
        self._visible_r = 480.0  # 缩放 120%
        self._sector_angle = math.radians(30)
        self._selected_idx = -1
        self._menu_items: list = []
        self._last_draw_time = 0.0
        self._sector_ids: list[int] = []
        self._glow_ids: list[int] = []
        self._icon_ids: list[int] = []
        self._sight_x = 0.0
        self._sight_y = 0.0
        self._sight_id: Optional[int] = None
        self._crosshair_ids: list[int] = []

        self.root.bind("<Escape>", lambda e: self.deactivate())
        self._idle_geom()

    # ── 几何 ──

    def _idle_geom(self):
        self.root.geometry("1x1+0+0")
        self._canvas.pack_forget()

    def _active_geom(self):
        """窗口覆盖鼠标所在显示器，菜单圆心 = 该显示器中央。"""
        import ctypes, struct
        mx = self.root.winfo_pointerx()
        my = self.root.winfo_pointery()
        try:
            hMon = ctypes.windll.user32.MonitorFromPoint(mx, my, 0)
            buf = ctypes.create_string_buffer(40)
            ctypes.memset(buf, 0, 40)
            ctypes.memmove(buf, ctypes.byref(ctypes.c_uint32(40)), 4)
            ok = ctypes.windll.user32.GetMonitorInfoW(hMon, buf)
            if not ok:
                raise Exception("GetMonitorInfoW failed")
            left, top, right, bottom = struct.unpack_from("<llll", buf, 4)
        except Exception:
            left = top = 0
            right = self.root.winfo_screenwidth()
            bottom = self.root.winfo_screenheight()

        sw = right - left
        sh = bottom - top
        self.root.geometry(f"{sw}x{sh}+{left}+{top}")
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._cx = sw / 2
        self._cy = sh / 2

    # ── 公开 API ──

    @property
    def state(self) -> str:
        return self._state

    def activate(self, menu_items: list):
        if self._state != "idle":
            return
        self._state = "menu_open"
        self._menu_items = menu_items
        self._n = len(menu_items)
        self._sector_angle = 2 * math.pi / max(self._n, 1)
        self._selected_idx = -1
        self._active_geom()
        self._build_sectors()
        self.root.lift()
        self.root.focus_force()
        print(f"[UI] 🟢 菜单 ({self._n} 项)")

    def deactivate(self):
        if self._state == "idle":
            return
        self._state = "idle"
        self._selected_idx = -1
        self._clear()
        self._canvas.pack_forget()
        self._idle_geom()
        print("[UI] 🔴 关闭")

    @property
    def selected_idx(self) -> int:
        return self._selected_idx

    def select_sector(self, idx: int):
        """BLE 传入扇区索引 → 高亮。"""
        if self._state != "menu_open":
            return
        if idx < 0 or idx >= self._n:
            self._selected_idx = -1
        else:
            self._selected_idx = idx
        self._redraw()

    def set_sight(self, rx: float, ry: float):
        """设置准星位置（归一化 -1..1），自动计算扇区。"""
        if self._state != "menu_open":
            return
        # 2x 速度 + 映射到像素偏移，约束在圆形内
        max_r = self._visible_r
        sx = rx * max_r
        sy = ry * max_r
        # 圆形裁剪
        dist = math.hypot(sx, sy)
        if dist > max_r:
            scale = max_r / dist
            sx *= scale
            sy *= scale
        self._sight_x = sx
        self._sight_y = sy

        dist = math.hypot(sx, sy)
        deadzone = self._visible_r * 0.3 * 1.3  # 中心盲区 +30%
        if dist < deadzone:
            self._selected_idx = -1
        else:
            angle = math.atan2(-sy, sx)  # sy取反：屏幕Y正→下，atan2期望Y正→上
            angle += math.pi / 2
            if angle < 0:
                angle += 2 * math.pi
            self._selected_idx = int(angle / self._sector_angle) % self._n
        self._redraw()

    # ── 绘制 ──

    def _build_sectors(self):
        self._clear()
        n = self._n
        if n == 0:
            return
        step = self._sector_angle
        inner_r = self._visible_r * 0.39  # 中心盲区 +30%

        for i in range(n):
            a0 = i * step - math.pi / 2
            a1 = a0 + step
            sid = self._canvas.create_arc(
                self._cx - self._visible_r, self._cy - self._visible_r,
                self._cx + self._visible_r, self._cy + self._visible_r,
                start=math.degrees(a0) + 1,
                extent=math.degrees(step) - 2,
                fill="", outline=DIM, width=2,
            )
            self._sector_ids.append(sid)
            gid = self._canvas.create_arc(
                self._cx - self._visible_r, self._cy - self._visible_r,
                self._cx + self._visible_r, self._cy + self._visible_r,
                start=math.degrees(a0) + 1,
                extent=math.degrees(step) - 2,
                fill="#4A90D9", outline="#4A90D9", width=2, stipple="gray25",
            )
            self._glow_ids.append(gid)
            self._canvas.create_oval(
                self._cx - inner_r, self._cy - inner_r,
                self._cx + inner_r, self._cy + inner_r,
                fill="black", outline="",
            )

        for i in range(n):
            a = i * step + step / 2 - math.pi / 2
            r = (inner_r + self._visible_r) / 2
            x = self._cx + r * math.cos(a)
            y = self._cy + r * math.sin(a)
            item = self._menu_items[i] if i < len(self._menu_items) else None
            label = item.label[:8] if item and item.label else f"项{i}"
            tid = self._canvas.create_text(
                x, y, text=label,
                fill=FG, font=("Segoe UI", 11, "bold"),
            )
            self._icon_ids.append(tid)

    def _clear(self):
        self._canvas.delete("all")
        self._sector_ids.clear()
        self._glow_ids.clear()
        self._icon_ids.clear()
        self._sight_id = None
        self._crosshair_ids.clear()

    def _draw_sight(self):
        # 清除旧准星（含十字线）
        if self._sight_id:
            self._canvas.delete(self._sight_id)
            self._sight_id = None
        for cid in self._crosshair_ids:
            self._canvas.delete(cid)
        self._crosshair_ids.clear()

        sx = self._cx + self._sight_x
        sy = self._cy + self._sight_y
        r = 5
        self._sight_id = self._canvas.create_oval(
            sx - r, sy - r, sx + r, sy + r,
            fill=ACCENT, outline="white", width=2,
        )
        cl = 10
        self._crosshair_ids.append(
            self._canvas.create_line(sx - cl, sy, sx + cl, sy, fill="white", width=1)
        )
        self._crosshair_ids.append(
            self._canvas.create_line(sx, sy - cl, sx, sy + cl, fill="white", width=1)
        )

    def _redraw(self):
        now = time.monotonic()
        if now - self._last_draw_time < THROTTLE_S:
            return
        self._last_draw_time = now
        for i in range(self._n):
            tcol = FG if i == self._selected_idx else DIM
            if i < len(self._sector_ids):
                out = HIGHLIGHT if i == self._selected_idx else DIM
                self._canvas.itemconfig(self._sector_ids[i], outline=out)
            if i < len(self._glow_ids):
                fill = ACCENT if i == self._selected_idx else ""
                self._canvas.itemconfig(self._glow_ids[i], fill=fill)
            if i < len(self._icon_ids):
                self._canvas.itemconfig(self._icon_ids[i], fill=tcol)
        self._draw_sight()
