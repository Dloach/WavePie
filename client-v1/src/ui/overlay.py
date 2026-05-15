"""OverlayUI — 圆形径向菜单（Pie Menu），增量更新优化。

操作方式：
  按住 F12 → 圆形菜单弹出，圆心在鼠标位置
  鼠标移向某个扇区 → 圆心到鼠标画一条连线，连线经过的扇区高亮
  松开 F12 → 执行高亮的扇区对应的功能

性能：
  扇区、图标、标签在激活时创建一次（_draw_create），
  后续鼠标移动只更新颜色和线条（_draw_update），避免反复 delete 重建。
"""

import math
import sys
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
POINTER_LINE = "#6AB0FF"
POINTER_DOT  = "#7BC0FF"

# 最大帧率（秒），限制 _draw_update 调用频率
THROTTLE_S = 0.016  # ~60fps


class OverlayUI:
    """径向菜单 UI（增量更新）。"""

    def __init__(self, config, gesture_engine=None, on_execute: Callable = None):
        self._config = config
        self._on_execute = on_execute

        self._state = "idle"
        self._menu_items: list = []
        self._selected_idx = -1
        self._prev_selected_idx = -1
        self._cx = 0
        self._cy = 0
        self._radius = 200
        self._center_r = 35
        self._sector_angle = 0.0
        self._n = 0

        # 鼠标指针位置（画连线用）
        self._px = 0
        self._py = 0

        self._activate_callback: Optional[Callable] = None
        self._gamepad_mode = False   # 手柄模式隐藏指针连线
        self._ble_mode = False       # BLE 模式禁用鼠标覆盖

        # ── Canvas 对象 ID 缓存 ──
        self._sector_ids = []
        self._glow_ids = []
        self._icon_ids = []
        self._label_ids = []
        self._line_id = None
        self._dash_id = None
        self._dot_id = None
        self._center_oval = None
        self._center_x = None
        self._center_hint = None
        self._built = False

        # 绘制节流
        self._last_draw_time = 0.0

        self._build_window()

    def _build_window(self):
        self.root = tk.Tk()
        self.root.title("BLE Gesture Controller")

        self._sw, self._sh, self._sx, self._sy = self._get_virtual_screen()

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.attributes("-transparentcolor", "black")

        self._idle_geom()
        self._canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.root.bind("<Button-1>", self._on_click)
        self.root.bind("<Motion>", self._on_motion)

    @staticmethod
    def _get_monitor_center(cursor_x: int, cursor_y: int):
        """获取鼠标所在屏幕的正中心坐标。"""
        try:
            import ctypes
            from ctypes import wintypes

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", ctypes.c_ulong),
                ]

            pt = wintypes.POINT(cursor_x, cursor_y)
            hMon = ctypes.windll.user32.MonitorFromPoint(pt, 2)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(mi)
            ctypes.windll.user32.GetMonitorInfoW(hMon, ctypes.byref(mi))
            cx = (mi.rcMonitor.left + mi.rcMonitor.right) // 2
            cy = (mi.rcMonitor.top + mi.rcMonitor.bottom) // 2
            return cx, cy
        except Exception:
            # 回退：虚拟桌面中心
            return 960, 540

    @staticmethod
    def _get_virtual_screen():
        try:
            import ctypes
            user32 = ctypes.windll.user32
            vx = user32.GetSystemMetrics(76)
            vy = user32.GetSystemMetrics(77)
            vw = user32.GetSystemMetrics(78)
            vh = user32.GetSystemMetrics(79)
            if vw > 0 and vh > 0:
                return vw, vh, vx, vy
        except Exception:
            pass
        r = tk.Tk()
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        r.destroy()
        return sw, sh, 0, 0

    def _idle_geom(self):
        self.root.geometry("1x1+0+0")
        self.root.attributes("-alpha", 0.01)

    def _active_geom(self):
        self.root.geometry(f"{self._sw}x{self._sh}+{self._sx}+{self._sy}")
        self.root.attributes("-alpha", 0.92)  # 扇区半透明效果
        self._canvas.configure(width=self._sw, height=self._sh)
        self._canvas.pack()

    # ── 公开 API ──

    @property
    def state(self):
        return self._state

    def set_activate_callback(self, cb: Callable[[], None]):
        self._activate_callback = cb

    def select_sector(self, idx: int):
        """程序化设置选中扇区（供 GamepadProvider 调用，线程安全）。

        Args:
            idx: 扇区索引，-1 表示不选中任何扇区
        """
        if self._state != "menu_open":
            return
        if idx < -1 or idx >= self._n:
            return
        if idx == self._selected_idx:
            return
        self._selected_idx = idx
        self._redraw()

    def set_gamepad_mode(self, enabled: bool):
        """切换手柄模式：隐藏指针连线。"""
        self._gamepad_mode = enabled

    def set_ble_mode(self, enabled: bool):
        """切换 BLE 模式：禁用鼠标覆盖选择。"""
        self._ble_mode = enabled

    def activate(self, button_id: int, items: list, screen_x: int, screen_y: int):
        if self._state == "menu_open":
            return
        if not items:
            return

        self._state = "menu_open"
        self._menu_items = items
        self._n = len(items)
        self._sector_angle = 2 * math.pi / self._n
        self._selected_idx = -1
        self._prev_selected_idx = -1
        self._px = screen_x
        self._py = screen_y
        self._built = False

        # 圆心固定在鼠标所在屏幕的正中央
        self._cx, self._cy = self._get_monitor_center(screen_x, screen_y)

        # 圆圈巨大（鼠标永远在圆内）
        self._radius = 3000
        # 扇区内边界（中空 480px）
        self._center_r = 480
        # 扇区可见外边界
        self._visible_r = 800

        # cx, cy 已在 _get_monitor_center 中计算，无需再 clamp

        self._active_geom()
        self._redraw()           # 全量绘制

    def deactivate(self):
        if self._state == "idle":
            return
        self._state = "idle"
        self._menu_items = []
        self._selected_idx = -1
        self._prev_selected_idx = -1
        self._canvas.delete("all")
        self._canvas.pack_forget()
        self._idle_geom()

    # ── 事件 ──

    def _on_motion(self, event: tk.Event):
        if self._state != "menu_open" or self._n == 0 or self._ble_mode:
            return

        abs_x = event.x_root
        abs_y = event.y_root
        self._px = abs_x
        self._py = abs_y

        dx = abs_x - self._cx
        dy = abs_y - self._cy
        dist = math.hypot(dx, dy)

        # 只在可见扇区范围内（cr ~ visible_r）才允许选中
        if dist < self._center_r or dist > self._visible_r:
            self._selected_idx = -1
        else:
            angle = math.atan2(dy, dx)
            angle += math.pi / 2
            if angle < 0:
                angle += 2 * math.pi
            self._selected_idx = int(angle / self._sector_angle) % self._n

        # 节流绘制（30fps）
        now = time.monotonic()
        if now - self._last_draw_time >= THROTTLE_S:
            self._redraw()
            self._last_draw_time = now

    def _on_click(self, event: tk.Event):
        if self._state != "menu_open" or self._n == 0:
            return
        dx = event.x_root - self._cx
        dy = event.y_root - self._cy
        if math.hypot(dx, dy) < self._center_r:
            self.deactivate()
            return
        if 0 <= self._selected_idx < self._n:
            item = self._menu_items[self._selected_idx]
            if self._on_execute:
                self._on_execute(item.action_type, item.action_payload)
        self.deactivate()

    # ── 全局触发（鼠标侧键 / 未来 BLE 设备）──

    def on_trigger_press(self):
        """触发键按下 → 激活菜单。"""
        if self._state == "idle" and self._activate_callback:
            self.root.after(0, self._activate_callback)

    def on_trigger_release(self):
        """触发键松开 → 执行选中项 / 取消。"""
        if self._state == "menu_open":
            idx = self._selected_idx
            def do_exec():
                # 先取出菜单项（deactivate 会清空 _menu_items）
                item = self._menu_items[idx] if 0 <= idx < len(self._menu_items) else None
                self.deactivate()
                if item and self._on_execute:
                    # 延迟 50ms 让焦点回到前一个窗口再发按键
                    self.root.after(50, lambda: self._on_execute(
                        item.action_type, item.action_payload))
            self.root.after(0, do_exec)

    def on_global_esc(self):
        if self._state == "menu_open":
            self.root.after(0, self.deactivate)
        # idle 时 ESC 无操作（防止误退）

    # ══════════════════════════════════════════════════════
    # 绘制：全量重绘（30fps 节流）
    # ══════════════════════════════════════════════════════

    def _ctx_xy(self):
        """返回 (cx, cy, px, py) Canvas 坐标（已减屏幕偏移）。"""
        ox, oy = self._sx, self._sy
        return (
            self._cx - ox,
            self._cy - oy,
            self._px - ox,
            self._py - oy,
        )

    def _redraw(self):
        """全量重绘：只画扇区（环状）+ 连线，其余全部透明。

        透明原理：Canvas 背景色 black，窗口 attributes("-transparentcolor","black")，
        所以没画东西的区域 = 全透明，用户看到的是桌面。
        """
        self._canvas.delete("all")
        n = self._n
        if n == 0:
            return

        cx, cy, px, py = self._ctx_xy()
        R = self._radius         # 巨大圆（保证鼠标永远在圆内用于角度计算）
        cr = self._center_r      # 扇区内边界
        vr = self._visible_r     # 扇区可见/可交互外边界
        sel = self._selected_idx
        steps = 18

        # ── 环状扇区（从 cr 到 vr，之外全透明不画）──
        for i in range(n):
            # 偏移半格，让 12 点钟方向对齐扇区中心
            half = self._sector_angle / 2
            a1 = -math.pi / 2 + i * self._sector_angle - half
            a2 = a1 + self._sector_angle
            mid = a1 + self._sector_angle / 2
            hl = (i == sel)

            fill = HL_SECTOR if hl else BG_SECTOR

            # 绘制一个闭合多边形：内弧 → 外弧（用 vr 限制可见区）
            pts = []
            for j in range(steps + 1):
                t = a1 + (a2 - a1) * j / steps
                pts.extend([cx + vr * math.cos(t), cy + vr * math.sin(t)])
            for j in range(steps, -1, -1):
                t = a1 + (a2 - a1) * j / steps
                pts.extend([cx + cr * math.cos(t), cy + cr * math.sin(t)])
            self._canvas.create_polygon(
                pts, fill=fill, outline="", width=0, smooth=True,
            )

            # 选中扇区外发光（外弧边缘）
            if hl:
                gpts = []
                for j in range(steps + 1):
                    t = a1 + (a2 - a1) * j / steps
                    gpts.extend([cx + (vr + 4) * math.cos(t),
                                 cy + (vr + 4) * math.sin(t)])
                for j in range(steps, -1, -1):
                    t = a1 + (a2 - a1) * j / steps
                    gpts.extend([cx + (vr - 6) * math.cos(t),
                                 cy + (vr - 6) * math.sin(t)])
                self._canvas.create_polygon(
                    gpts, fill="", outline=HL_GLOW, width=0, smooth=True,
                )

            # 图标（放在扇区中间偏内，12项时略小）
            icon_r = cr + (vr - cr) * 0.32
            icon = getattr(self._menu_items[i], 'icon', '') or ''
            if icon:
                self._canvas.create_text(
                    cx + icon_r * math.cos(mid), cy + icon_r * math.sin(mid),
                    text=icon, font=("Segoe UI Emoji", 28),
                    fill=TEXT_LIGHT if hl else TEXT_DIM,
                )

            # 标签（放在扇区中间偏外）
            text_r = cr + (vr - cr) * 0.6
            self._canvas.create_text(
                cx + text_r * math.cos(mid), cy + text_r * math.sin(mid),
                text=self._menu_items[i].label,
                font=("Microsoft YaHei", 14, "bold" if hl else "normal"),
                fill=TEXT_LIGHT if hl else TEXT_DIM,
            )

        # ── 指针连线（手柄模式下隐藏）──
        if not self._gamepad_mode:
            self._draw_pointer_line(cx, cy, px, py, cr)

    def _draw_pointer_line(self, cx, cy, px, py, cr):
        """绘制圆心到鼠标的连线。"""
        dx = px - cx
        dy = py - cy
        dist = math.hypot(dx, dy)

        if dist > cr:
            # 主线
            self._canvas.create_line(
                cx, cy, px, py,
                fill=POINTER_LINE, width=3, capstyle="round",
            )
            # 虚线延伸到光点后面
            if dist > 0:
                ux, uy = dx / dist, dy / dist
                self._canvas.create_line(
                    px, py, px + ux * 200, py + uy * 200,
                    fill=POINTER_LINE, width=1, dash=(4, 6),
                )
            # 光点
            self._canvas.create_oval(
                px - 5, py - 5, px + 5, py + 5,
                fill=POINTER_DOT, outline="",
            )

        # ── 中心不画任何东西（全透明）──
        # 背景 = black = transparentcolor，所以中心区域完全透明

    # ── 启动 ──

    def run(self):
        self.root.mainloop()
