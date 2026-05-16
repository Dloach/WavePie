"""OverlayUI V3 — V1 双显兼容绘制 + V2 BLE 准星。

工作流程:
  BLE 0xAA → set_sight(rx, ry) → 准星位置 → 扇区高亮
  BLE 0xBB → deactivate() → 执行命令

V1 核心保留: GetSystemMetrics 虚拟桌面、MONITORINFO 显示器中央、transparentcolor="black"
"""

import math
import time
import tkinter as tk
from typing import Callable, Optional


# ── 调色板 ──
BG_DARK     = "#1A1A2E"
BG_SECTOR   = "#2D2D44"
HL_SECTOR   = "#4A90D9"
HL_GLOW     = "#5BA3E6"
TEXT_LIGHT  = "#FFFFFF"
TEXT_DIM    = "#888899"
CENTER_DOT  = "#3D3D5C"
BORDER      = "#444466"
POINTER_DOT = "#7BC0FF"
ACCENT = "#4A90D9"

THROTTLE_S = 1.0 / 60.0  # 扇区帧率
SIGHT_THROTTLE = 1.0 / 60.0  # 准星帧率


class OverlayUI:
    def __init__(self, config, on_execute: Callable = None):
        self._cfg = config
        self._on_execute = on_execute
        self._build_window()

    def _build_window(self):
        self._vx, self._vy, self._vw, self._vh = self._get_virtual_screen()

        self.root = tk.Tk()
        self.root.title("WavePie V3")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.attributes("-transparentcolor", "black")

        self._idle_geom()
        self._canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.root.bind("<Escape>", lambda e: self.deactivate())

        # ── 状态 ──
        self._state = "idle"
        self._n = 0
        self._cx = 0.0
        self._cy = 0.0
        self._visible_r = 480.0
        self._sector_angle = math.radians(30)
        self._selected_idx = -1
        self._menu_items: list = []
        self._last_draw_time = 0.0

        # ── 准星 ──
        self._sight_x = 0.0
        self._sight_y = 0.0
        self._sight_id: Optional[int] = None
        self._crosshair_ids: list[int] = []

    # ══════════════════════════════════════════════
    # 虚拟桌面（V1 方法，多显示器兼容）
    # ══════════════════════════════════════════════

    @staticmethod
    def _get_virtual_screen():
        try:
            import ctypes
            u = ctypes.windll.user32
            vx = u.GetSystemMetrics(76)
            vy = u.GetSystemMetrics(77)
            vw = u.GetSystemMetrics(78)
            vh = u.GetSystemMetrics(79)
            if vw > 0 and vh > 0:
                return vx, vy, vw, vh
        except Exception:
            pass
        return 0, 0, 1920, 1080

    def _idle_geom(self):
        self.root.geometry("1x1+0+0")
        self.root.attributes("-alpha", 0.01)

    def _active_geom(self, cx, cy):
        self.root.attributes("-alpha", 0.85)
        self.root.geometry(f"{self._vw}x{self._vh}+{self._vx}+{self._vy}")
        self.root.update_idletasks()
        self._canvas.configure(width=self._vw, height=self._vh)
        self._canvas.pack()
        self.root.lift()
        self.root.focus_force()
        # 屏幕坐标 → Canvas 坐标（减去虚拟桌面原点）
        self._cx = cx - self._vx
        self._cy = cy - self._vy


    # ══════════════════════════════════════════════
    # 公开 API
    # ══════════════════════════════════════════════

    @property
    def state(self) -> str:
        return self._state

    @property
    def selected_idx(self) -> int:
        return self._selected_idx

    def activate(self, menu_items: list, cx: int = None, cy: int = None):
        if self._state != "idle":
            return
        self._state = "menu_open"
        self._menu_items = menu_items
        self._n = len(menu_items)
        self._sector_angle = 2 * math.pi / max(self._n, 1)
        self._selected_idx = -1

        if cx is not None and cy is not None:
            self._cx, self._cy = cx, cy
        else:
            self._cx, self._cy = self._get_monitor_center(None, None)

        self._active_geom(self._cx, self._cy)
        self._build_sectors()
        self._sight_x = 0.0
        self._sight_y = 0.0
        self.root.lift()
        self.root.focus_force()

    def deactivate(self):
        if self._state == "idle":
            return
        self._state = "idle"
        self._selected_idx = -1
        self._clear()
        self._canvas.pack_forget()
        self._idle_geom()

    def set_sight(self, rx: float, ry: float):
        """设置准星位置（归一化 -1..1），约束在圆内。"""
        if self._state != "menu_open":
            return
        max_r = self._visible_r
        sx = rx * max_r
        sy = ry * max_r
        dist = math.hypot(sx, sy)
        if dist > max_r:
            scale = max_r / dist
            sx *= scale
            sy *= scale
        self._sight_x = sx
        self._sight_y = sy

        # 扇区计算
        deadzone = self._visible_r * 0.39
        d = math.hypot(sx, sy)
        new_idx = -1 if d < deadzone else int((math.atan2(-sy, sx) + math.pi / 2) % (2 * math.pi) / self._sector_angle) % self._n
        if new_idx != self._selected_idx:
            self._selected_idx = new_idx
            self._redraw()
        self._draw_sight()

    # ══════════════════════════════════════════════
    # 显示器定位
    # ══════════════════════════════════════════════

    @staticmethod
    def _get_monitor_center(cursor_x, cursor_y):
        """鼠标所在显示器正中央。"""
        try:
            from ctypes import windll, byref, sizeof, Structure, c_long, c_uint32, wintypes
            class RECT(Structure):
                _fields_ = [("l",c_long),("t",c_long),("r",c_long),("b",c_long)]
            class MONITORINFO(Structure):
                _fields_ = [("cb",c_uint32),("rc",RECT),("wk",RECT),("fl",c_uint32)]
            pt = wintypes.POINT()
            windll.user32.GetCursorPos(byref(pt))
            hMon = windll.user32.MonitorFromPoint(pt, 0)
            mi = MONITORINFO()
            mi.cb = sizeof(mi)
            if windll.user32.GetMonitorInfoW(hMon, byref(mi)):
                return (mi.rc.l + mi.rc.r) / 2, (mi.rc.t + mi.rc.b) / 2
        except Exception:
            pass
        return 960, 540

    # ══════════════════════════════════════════════
    # 绘制
    # ══════════════════════════════════════════════

    def _build_sectors(self):
        self._clear()
        n = self._n
        if n == 0:
            return
        step = self._sector_angle
        inner_r = self._visible_r * 0.39

        self._sector_ids = []
        self._glow_ids = []
        self._icon_ids = []

        for i in range(n):
            a0 = i * step - math.pi / 2
            sid = self._canvas.create_arc(
                self._cx - self._visible_r, self._cy - self._visible_r,
                self._cx + self._visible_r, self._cy + self._visible_r,
                start=math.degrees(a0) + 1,
                extent=math.degrees(step) - 2,
                fill="", outline=TEXT_DIM, width=2,
            )
            self._sector_ids.append(sid)
            gid = self._canvas.create_arc(
                self._cx - self._visible_r, self._cy - self._visible_r,
                self._cx + self._visible_r, self._cy + self._visible_r,
                start=math.degrees(a0) + 1,
                extent=math.degrees(step) - 2,
                fill="", outline="#555555", width=2,
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
                x, y, text=label, fill=TEXT_LIGHT,
                font=("Segoe UI", 11, "bold"),
            )
            self._icon_ids.append(tid)

    def _clear(self):
        self._canvas.delete("all")
        self._sight_id = None
        self._crosshair_ids.clear()

    def _draw_sight(self):
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
            self._canvas.create_line(sx - cl, sy, sx + cl, sy, fill="white", width=1))
        self._crosshair_ids.append(
            self._canvas.create_line(sx, sy - cl, sx, sy + cl, fill="white", width=1))

    def _redraw(self):
        now = time.monotonic()
        if now - self._last_draw_time < THROTTLE_S:
            return
        self._last_draw_time = now
        for i in range(self._n):
            out = HL_SECTOR if i == self._selected_idx else TEXT_DIM
            fill = HL_GLOW if i == self._selected_idx else ""
            tcol = TEXT_LIGHT if i == self._selected_idx else TEXT_DIM
            if i < len(self._sector_ids):
                self._canvas.itemconfig(self._sector_ids[i], outline=out, fill="")
            if i < len(self._glow_ids):
                self._canvas.itemconfig(self._glow_ids[i], outline=fill, fill=fill)
            if i < len(self._icon_ids):
                self._canvas.itemconfig(self._icon_ids[i], fill=tcol)
        self._draw_sight()
