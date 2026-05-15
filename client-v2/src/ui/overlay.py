"""OverlayUI — 全屏透明径向菜单 + 激光准星。

V2 变化：
  - 删除了鼠标/键盘事件绑定
  - 新增激光准星（浮动白点/十字）
  - 扇区高亮由准星位置驱动（而非鼠标角度）
  - set_gamepad_mode / set_ble_mode 已不再需要
"""

import math
import time
import tkinter as tk
from typing import Callable, Optional

BG = "#2B2B2B"
FG = "#FFFFFF"
ACCENT = "#4A90D9"
HIGHLIGHT = "#F5A623"
CARD = "#3C3C3C"
DIM = "#999999"
THROTTLE_S = 1.0 / 30.0  # 30fps


class OverlayUI:
    """径向菜单 + 激光准星。"""

    def __init__(self, config, on_execute: Callable = None):
        self._cfg = config
        self._on_execute = on_execute

        # ── 窗口 ──
        self.root = tk.Tk()
        self.root.title("WavePie V2")
        self.root.configure(bg="black")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        self.root.attributes("-alpha", 0.85)

        # ── Canvas ──
        self._canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # ── 状态 ──
        self._state = "idle"  # idle | menu_open
        self._n = 0
        self._cx = 0.0
        self._cy = 0.0
        self._sx = 0.0
        self._sy = 0.0
        self._center_r = 200.0   # 内径
        self._visible_r = 480.0  # 外径
        self._sector_angle = math.radians(30)  # 12项
        self._selected_idx = -1
        self._menu_items: list = []
        self._last_draw_time = 0.0

        # ── 准星 ──
        self._sight_x = 0.0
        self._sight_y = 0.0
        self._aim_active = False

        # ── 缓存 Canvas 对象 ──
        self._sector_ids: list[int] = []
        self._glow_ids: list[int] = []
        self._icon_ids: list[int] = []
        self._sight_id: Optional[int] = None
        self._crosshair_ids: list[int] = []

        # ── 屏幕尺寸修复 ──
        self._fullscreen()

        # ── 只保留 ESC 关闭（调试用） ──
        self.root.bind("<Escape>", lambda e: self.deactivate())

        self._update_size()
        self._idle_geom()

    def _fullscreen(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")

    def _update_size(self):
        self._sw = self.root.winfo_screenwidth()
        self._sh = self.root.winfo_screenheight()

    def _idle_geom(self):
        self.root.geometry("1x1+0+0")
        self._canvas.pack_forget()

    def _active_geom(self):
        self._fullscreen()
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._cx = self._sw / 2
        self._cy = self._sh / 2
        # 修复屏幕偏移（多显示器）
        self._sx = self.root.winfo_rootx()
        self._sy = self.root.winfo_rooty()

    # ── 公开 API ──

    @property
    def state(self) -> str:
        return self._state

    @property
    def selected_idx(self) -> int:
        return self._selected_idx

    def activate(self, menu_items: list, cx: int = None, cy: int = None):
        """显示菜单，准备接收准星位置。"""
        if self._state != "idle":
            return
        self._state = "menu_open"
        self._menu_items = menu_items
        self._n = len(menu_items)
        self._sector_angle = 2 * math.pi / max(self._n, 1)
        self._selected_idx = -1
        self._sight_x = 0.0
        self._sight_y = 0.0
        self._aim_active = True

        self._update_size()
        if cx is not None and cy is not None:
            self._cx = cx
            self._cy = cy
        self._active_geom()
        self._build_sectors()

        # 把窗口提到最前
        self.root.lift()
        self.root.focus_force()
        print(f"[UI] 🟢 菜单打开 ({self._n} 项)")

    def deactivate(self):
        """关闭菜单，清除绘制。"""
        if self._state == "idle":
            return
        self._state = "idle"
        self._aim_active = False
        self._clear()
        self._canvas.pack_forget()
        self._idle_geom()
        print("[UI] 🔴 菜单关闭")

    def set_sight(self, x: float, y: float):
        """设置准星相对圆心的偏移坐标。"""
        self._sight_x = x
        self._sight_y = y
        self._update_sector()
        self._redraw()

    def set_ring(self, inner_r: float, outer_r: float):
        self._center_r = inner_r
        self._visible_r = outer_r

    def get_sight_angle(self) -> float:
        """返回准星相对圆心的角度（度），用于 AimEngine 扇区计算。"""
        if self._sight_x == 0 and self._sight_y == 0:
            return -1
        return math.degrees(math.atan2(self._sight_x, -self._sight_y)) % 360

    # ── 内部 ──

    def _update_sector(self):
        """根据准星位置计算高亮扇区。"""
        if self._n <= 1:
            self._selected_idx = 0 if self._n == 1 else -1
            return
        dx = self._sight_x
        dy = self._sight_y
        dist = math.hypot(dx, dy)
        if dist < self._center_r or dist > self._visible_r:
            self._selected_idx = -1
            return
        angle = math.atan2(dy, dx)
        angle += math.pi / 2
        if angle < 0:
            angle += 2 * math.pi
        self._selected_idx = int(angle / self._sector_angle) % self._n

    def _build_sectors(self):
        self._clear()
        n = self._n
        if n == 0:
            return

        step = self._sector_angle
        for i in range(n):
            a0 = i * step - math.pi / 2
            a1 = a0 + step
            # 外弧
            tags = ("sector",)
            sid = self._canvas.create_arc(
                self._cx - self._visible_r, self._cy - self._visible_r,
                self._cx + self._visible_r, self._cy + self._visible_r,
                start=math.degrees(a0) + 1,
                extent=math.degrees(step) - 2,
                fill="", outline=DIM, width=2, tags=tags,
            )
            self._sector_ids.append(sid)

            # 内弧（截断到内径）
            gid = self._canvas.create_arc(
                self._cx - self._visible_r, self._cy - self._visible_r,
                self._cx + self._visible_r, self._cy + self._visible_r,
                start=math.degrees(a0) + 1,
                extent=math.degrees(step) - 2,
                fill="", outline="#555555", width=2, tags=tags,
            )
            self._glow_ids.append(gid)

            # 内圈遮罩（覆盖内径以内的区域，保持透明）
            mask = self._canvas.create_oval(
                self._cx - self._center_r, self._cy - self._center_r,
                self._cx + self._center_r, self._cy + self._center_r,
                fill="black", outline="", tags=("mask",),
            )

        # 标签（圆心向外延伸）
        self._icon_ids = []
        for i in range(n):
            a = i * step + step / 2 - math.pi / 2
            r = (self._center_r + self._visible_r) / 2
            x = self._cx + r * math.cos(a)
            y = self._cy + r * math.sin(a)
            item = self._menu_items[i] if i < len(self._menu_items) else None
            label = item.label if item else f"项{i}"
            # 只显示前 6 个字符
            display = label[:8] if len(label) > 8 else label
            tid = self._canvas.create_text(
                x, y, text=display,
                fill=FG, font=("Segoe UI", 11, "bold"),
                tags=("icon",),
            )
            self._icon_ids.append(tid)

    def _clear(self):
        self._canvas.delete("all")
        self._sector_ids.clear()
        self._glow_ids.clear()
        self._icon_ids.clear()
        self._sight_id = None
        self._crosshair_ids.clear()

    def _redraw(self):
        """刷新高亮 + 准星。"""
        now = time.monotonic()
        if now - self._last_draw_time < THROTTLE_S:
            return
        self._last_draw_time = now

        # 高亮
        for i in range(self._n):
            color = HIGHLIGHT if i == self._selected_idx else DIM
            if i < len(self._sector_ids):
                self._canvas.itemconfig(self._sector_ids[i], outline=color)
            if i < len(self._glow_ids):
                glow = ACCENT if i == self._selected_idx else "#555555"
                self._canvas.itemconfig(self._glow_ids[i], outline=glow)
            if i < len(self._icon_ids):
                self._canvas.itemconfig(self._icon_ids[i], fill=FG if i == self._selected_idx else DIM)

        # 准星
        self._draw_sight()

    def _draw_sight(self):
        """绘制激光准星（十字+中心点）。"""
        # 清除旧准星
        if self._sight_id:
            self._canvas.delete(self._sight_id)
        for cid in self._crosshair_ids:
            self._canvas.delete(cid)
        self._crosshair_ids.clear()

        if not self._aim_active:
            return

        sx = self._cx + self._sight_x
        sy = self._cy + self._sight_y
        r = 6

        # 中心点
        self._sight_id = self._canvas.create_oval(
            sx - r, sy - r, sx + r, sy + r,
            fill=ACCENT, outline="white", width=2,
        )

        # 十字线（短）
        cl = 12
        self._crosshair_ids.append(
            self._canvas.create_line(sx - cl, sy, sx + cl, sy, fill="white", width=1)
        )
        self._crosshair_ids.append(
            self._canvas.create_line(sx, sy - cl, sx, sy + cl, fill="white", width=1)
        )
