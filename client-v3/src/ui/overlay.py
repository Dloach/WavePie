"""WavePie V3 OverlayUI — 圆形辐射菜单。

设计原则:
  - Canvas 元素仅在 activate 时创建一次，通过 itemconfig/coords 更新
  - 零每帧创建/删除，保证 60fps 流畅
  - 简洁而精致的视觉效果
"""

import math
import time
import tkinter as tk
from typing import Callable, Optional

# ═══════════════════════════════════════════════════
#  调色板
# ═══════════════════════════════════════════════════
VEIL        = "#0A0A18"
RING_FILL   = "#12122A"
RING_EDGE   = "#282850"
DEAD_FILL   = "#0C0C20"
DEAD_EDGE   = "#1E1E42"
SECTOR_LINE = "#2A2A52"
SECTOR_HL   = "#4466DD"
SECTOR_GLOW = "#3355BB"
CENTER_DOT  = "#5577FF"
CENTER_RING = "#282860"
TEXT_IDLE   = "#7777AA"
TEXT_HL     = "#FFFFFF"
SIGHT_INNER = "#FFFFFF"
SIGHT_OUTER = "#6688EE"
SIGHT_LINE  = "#AABBFF"
FLASH_COLOR = "#FFFFFF"

# ═══════════════════════════════════════════════════
#  尺寸（绝对）
# ═══════════════════════════════════════════════════
DEAD_RATIO   = 0.40      # 死区占菜单外径比
CENTER_R     = 8.0       # 中心点半径
SIGHT_R      = 5.0       # 准星点半径
SIGHT_CROSS_L = 12.0     # 十字线长

# ═══════════════════════════════════════════════════
#  动画参数
# ═══════════════════════════════════════════════════
ENTER_MS    = 280        # 入场淡入
EXIT_MS     = 200        # 退场淡出
CONFIRM_MS  = 350        # 确认闪光
GLOW_MS     = 100        # 发光过渡
PULSE_S     = 2.2        # 呼吸周期(秒)
SMOOTH      = 0.10       # 准星平滑系数（越小越快）
SNAP        = 0.68       # 磁吸强度（0=关 1=瞬间吸附到扇区中心）
SNAP_RADIAL = 0.35       # 径向磁吸（拉向环形中段）

# ═══════════════════════════════════════════════════
#  小工具
# ═══════════════════════════════════════════════════

def _lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))

def _lerp_hex(c1: str, c2: str, t: float) -> str:
    """插值两个 #RRGGBB 颜色。"""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
    r2, g2, b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
    return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"

def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


# ═══════════════════════════════════════════════════
#  OverlayUI
# ═══════════════════════════════════════════════════

class OverlayUI:
    def __init__(self, config, on_execute: Callable = None):
        self._cfg = config
        self._on_execute = on_execute
        self._vx, self._vy, self._vw, self._vh = self._get_virtual_screen()
        self._calc_sizes()

        # ── 窗口 ──
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
        self._angle = 0.0             # 扇区角度
        self._selected = -1
        self._in_dead = True          # 原始位置在死区内
        self._menu_items = []
        self._glows = []              # 当前发光值
        self._glow_targets = []       # 目标发光值

        # ── 准星 ──
        self._sx = 0.0      # 视觉位置（含磁吸）
        self._sy = 0.0
        self._raw_sx = 0.0   # 原始位置（用于扇区判定）
        self._raw_sy = 0.0

        # ── 动画 ──
        self._enter_t = 0.0
        self._exit_t = 0.0
        self._confirm_t = 0.0
        self._exiting = False
        self._confirming = False
        self._confirm_idx = -1
        self._tick_running = False
        self._clock = time.monotonic()
        self._anim_clock = 0.0
        self._last_exit_time = 0.0     # 防止退场后立即重新激活

        # ── Canvas 元素 ID（惰性创建） ──
        self._ids = {}  # dict of lists/dicts, 在 _build 中填充

    # ══════════════════════════════════════════════
    #  屏幕工具
    # ══════════════════════════════════════════════

    @staticmethod
    def _get_virtual_screen():
        try:
            import ctypes
            u = ctypes.windll.user32
            return u.GetSystemMetrics(76), u.GetSystemMetrics(77), \
                   u.GetSystemMetrics(78), u.GetSystemMetrics(79)
        except Exception:
            return 0, 0, 1920, 1080

    def _calc_sizes(self):
        """根据屏幕高度动态计算菜单尺寸。"""
        self._menu_r = self._vh * 0.40     # 外径 = 屏幕高 80% ÷ 2
        self._dead_r = self._menu_r * DEAD_RATIO
        self._label_r = (self._dead_r + self._menu_r) / 2

    def _idle_geom(self):
        self.root.geometry("1x1+0+0")
        self.root.attributes("-alpha", 0.01)

    def _show_geom(self, cx, cy):
        self.root.attributes("-alpha", 0.01)
        self.root.geometry(f"{self._vw}x{self._vh}+{self._vx}+{self._vy}")
        self.root.update_idletasks()
        self._canvas.configure(width=self._vw, height=self._vh)
        self._canvas.pack()
        self.root.lift()
        self.root.focus_force()
        self._cx = cx - self._vx
        self._cy = cy - self._vy

    @staticmethod
    def _get_monitor_center(cursor_x, cursor_y):
        try:
            from ctypes import windll, byref, sizeof, Structure, c_long, c_uint32, wintypes
            class R(Structure):
                _fields_ = [("l",c_long),("t",c_long),("r",c_long),("b",c_long)]
            class MI(Structure):
                _fields_ = [("cb",c_uint32),("rc",R),("wk",R),("fl",c_uint32)]
            pt = wintypes.POINT()
            windll.user32.GetCursorPos(byref(pt))
            h = windll.user32.MonitorFromPoint(pt, 0)
            mi = MI(); mi.cb = sizeof(mi)
            if windll.user32.GetMonitorInfoW(h, byref(mi)):
                return (mi.rc.l + mi.rc.r) / 2, (mi.rc.t + mi.rc.b) / 2
        except Exception:
            return 960, 540

    # ══════════════════════════════════════════════
    #  公开 API
    # ══════════════════════════════════════════════

    @property
    def state(self) -> str:
        return self._state

    @property
    def selected_idx(self) -> int:
        # 准星在死区内 → 返回 -1（放弃命令）
        return -1 if self._in_dead else self._selected

    def activate(self, menu_items: list, cx: int = None, cy: int = None):
        # 退场后冷却期：600ms 内不允许重新激活
        if self._state != "idle":
            return
        if time.monotonic() - self._last_exit_time < 0.6:
            return
        self._state = "menu_open"
        self._menu_items = menu_items
        self._n = len(menu_items)
        self._angle = 2 * math.pi / max(self._n, 1)
        self._selected = -1
        self._glows = [0.0] * self._n
        self._glow_targets = [0.0] * self._n

        if cx is not None and cy is not None:
            self._cx, self._cy = cx, cy
        else:
            self._cx, self._cy = self._get_monitor_center(None, None)

        self._show_geom(self._cx, self._cy)
        self._sx = 0.0
        self._sy = 0.0
        self._raw_sx = 0.0
        self._raw_sy = 0.0

        # 动画重置
        self._enter_t = 0.0
        self._exit_t = 0.0
        self._confirm_t = 0.0
        self._exiting = False
        self._confirming = False

        # 构建所有 Canvas 元素（一次性）
        self._build()

        # 启动动画循环
        self._start_tick()
        self.root.lift()
        self.root.focus_force()

    def deactivate(self):
        if self._state == "idle" or self._exiting:
            return
        self._exiting = True
        self._exit_t = 0.0
        self._last_exit_time = time.monotonic()
        # 有选中扇区则先播确认
        if self._selected >= 0:
            self._confirming = True
            self._confirm_idx = self._selected
            self._confirm_t = 0.0

    def set_sight(self, rx: float, ry: float):
        if self._state != "menu_open" or self._exiting:
            return
        mr = self._menu_r
        dr = self._dead_r
        # 归一化 → 像素，约束在圆内
        sx = rx * mr
        sy = ry * mr
        d = math.hypot(sx, sy)
        if d > mr:
            s = mr / d
            sx *= s; sy *= s

        # 指数平滑（加速响应）
        self._raw_sx = self._raw_sx * SMOOTH + sx * (1.0 - SMOOTH)
        self._raw_sy = self._raw_sy * SMOOTH + sy * (1.0 - SMOOTH)

        # 扇区判定（用原始位置）
        raw_d = math.hypot(self._raw_sx, self._raw_sy)
        self._in_dead = raw_d < dr

        if self._in_dead:
            # 死区内：粘性保持上一次扇区（视觉高亮不灭）
            if self._selected < 0:
                new_idx = -1
            else:
                new_idx = self._selected
        else:
            new_idx = int(
                (math.atan2(-self._raw_sy, self._raw_sx) + math.pi / 2)
                % (2 * math.pi) / self._angle
            ) % self._n

        if new_idx != self._selected:
            self._selected = new_idx
            for i in range(self._n):
                self._glow_targets[i] = 1.0 if i == new_idx else 0.0

        # ── 磁吸：视觉准星拉向扇区中心 ──
        if self._selected >= 0 and raw_d > dr * 0.7:
            center_angle = (self._selected + 0.5) * self._angle - math.pi / 2
            raw_angle = math.atan2(-self._raw_sy, self._raw_sx)
            da = (center_angle - raw_angle + math.pi) % (2 * math.pi) - math.pi
            snapped_angle = raw_angle + da * SNAP
            ring_mid = (dr + mr) / 2
            snapped_d = raw_d + (ring_mid - raw_d) * SNAP_RADIAL
            self._sx = snapped_d * math.cos(snapped_angle)
            self._sy = -snapped_d * math.sin(snapped_angle)
        else:
            self._sx = self._raw_sx
            self._sy = self._raw_sy

    # ══════════════════════════════════════════════
    #  构建（一次性创建所有 Canvas 元素）
    # ══════════════════════════════════════════════

    def _build(self):
        self._canvas.delete("all")
        self._ids.clear()
        c = self._canvas
        ox, oy = self._cx, self._cy
        n = self._n
        mr = self._menu_r
        dr = self._dead_r
        lr = self._label_r

        # ── 背景遮罩 ──
        self._ids["veil"] = c.create_rectangle(
            0, 0, self._vw, self._vh,
            fill=VEIL, outline="",
        )
        # 菜单区环形底色
        self._ids["ring_bg"] = c.create_oval(
            ox - mr, oy - mr,
            ox + mr, oy + mr,
            fill=RING_FILL, outline=RING_EDGE, width=2,
        )
        # 死区
        self._ids["dead"] = c.create_oval(
            ox - dr, oy - dr,
            ox + dr, oy + dr,
            fill=DEAD_FILL, outline=DEAD_EDGE, width=1,
        )
        # 外装饰线
        self._ids["ring_out"] = c.create_oval(
            ox - mr - 12, oy - mr - 12,
            ox + mr + 12, oy + mr + 12,
            fill="", outline="#1A1A3A", width=1,
        )

        # ── 扇区填充块（高亮时变色，创建在死区之前故中心被死区圆形覆盖） ──
        self._ids["fills"] = []
        for i in range(n):
            a0 = i * self._angle - math.pi / 2
            deg0 = math.degrees(a0) + 1
            extent = math.degrees(self._angle) - 2
            fid = c.create_arc(
                ox - mr, oy - mr,
                ox + mr, oy + mr,
                start=deg0, extent=extent,
                fill=RING_FILL, outline="",
            )
            self._ids["fills"].append(fid)

        # ── 扇区弧线 ──
        self._ids["arcs"] = []
        self._ids["seps"] = []
        for i in range(n):
            a0 = i * self._angle - math.pi / 2
            deg0 = math.degrees(a0) + 1
            extent = math.degrees(self._angle) - 2
            aid = c.create_arc(
                ox - mr, oy - mr,
                ox + mr, oy + mr,
                start=deg0, extent=extent,
                style="arc", outline=SECTOR_LINE, width=1,
            )
            self._ids["arcs"].append(aid)
            # 分隔线
            x1 = ox + dr * math.cos(a0)
            y1 = oy + dr * math.sin(a0)
            x2 = ox + mr * math.cos(a0)
            y2 = oy + mr * math.sin(a0)
            sid = c.create_line(x1, y1, x2, y2, fill="#1A1A38", width=1)
            self._ids["seps"].append(sid)

        # ── 标签 ──
        self._ids["labels"] = []
        for i in range(n):
            a = i * self._angle + self._angle / 2 - math.pi / 2
            lx = ox + lr * math.cos(a)
            ly = oy + lr * math.sin(a)
            item = self._menu_items[i] if i < len(self._menu_items) else None
            text = item.label[:8] if item and item.label else f"#{i+1}"
            tid = c.create_text(
                lx, ly, text=text,
                fill=TEXT_IDLE,
                font=("Segoe UI", 11, "bold"),
            )
            self._ids["labels"].append(tid)

        # ── 中心枢纽 ──
        # 呼吸点
        self._ids["center_dot"] = c.create_oval(
            ox - CENTER_R, oy - CENTER_R,
            ox + CENTER_R, oy + CENTER_R,
            fill=CENTER_DOT, outline="",
        )
        # 外光晕环
        self._ids["center_halo"] = c.create_oval(
            ox - CENTER_R * 2.5, oy - CENTER_R * 2.5,
            ox + CENTER_R * 2.5, oy + CENTER_R * 2.5,
            fill="", outline=CENTER_RING, width=1,
        )

        # ── 准星 ──
        self._ids["sight_outer"] = c.create_oval(
            0, 0, 1, 1, fill="", outline=SIGHT_OUTER, width=1.5,
        )
        self._ids["sight_inner"] = c.create_oval(
            0, 0, 1, 1, fill="", outline=SIGHT_LINE, width=1.5,
        )
        self._ids["sight_dot"] = c.create_oval(
            0, 0, 1, 1, fill=SIGHT_INNER, outline="",
        )
        # 十字线（4条）
        self._ids["sight_lines"] = []
        for _ in range(4):
            lid = c.create_line(0, 0, 1, 1, fill=SIGHT_LINE, width=1.5)
            self._ids["sight_lines"].append(lid)

        # ── 确认闪光元素（隐藏态） ──
        self._ids["flash_ring"] = c.create_oval(
            0, 0, 1, 1, fill="", outline=FLASH_COLOR, width=3,
        )
        self._ids["flash_arc"] = c.create_arc(
            0, 0, 1, 1, start=0, extent=1,
            fill="", outline=FLASH_COLOR, width=4,
        )

    # ══════════════════════════════════════════════
    #  动画循环
    # ══════════════════════════════════════════════

    def _start_tick(self):
        if self._tick_running:
            return
        self._tick_running = True
        self._clock = time.monotonic()
        self._tick()

    def _tick(self):
        now = time.monotonic()
        dt = now - self._clock
        self._clock = now
        dt = min(dt, 0.05)
        self._anim_clock += dt

        # ── 入场 ──
        if self._enter_t < 1.0 and not self._exiting:
            self._enter_t = min(1.0, self._enter_t + dt * 1000 / ENTER_MS)
            # 窗透明度平滑过渡
            alpha = 0.01 + _ease_out(self._enter_t) * 0.86
            self.root.attributes("-alpha", alpha)

        # ── 发光过渡 ──
        for i in range(self._n):
            self._glows[i] = _lerp(
                self._glows[i], self._glow_targets[i],
                min(1.0, dt * 1000 / GLOW_MS),
            )

        # ── 确认 & 退场 ──
        if self._exiting:
            if self._confirming:
                self._confirm_t = min(1.0, self._confirm_t + dt * 1000 / CONFIRM_MS)
                if self._confirm_t >= 1.0:
                    self._confirming = False
                    self._exit_t = 0.0
            else:
                self._exit_t = min(1.0, self._exit_t + dt * 1000 / EXIT_MS)
                alpha = 0.87 * (1.0 - _ease_out(self._exit_t))
                self.root.attributes("-alpha", max(0.01, alpha))
                if self._exit_t >= 1.0:
                    self._finish_exit()
                    return

        # ── 更新所有元素 ──
        self._update_sectors()
        self._update_labels()
        self._update_center()
        self._update_sight()
        self._update_flash()

        # ── 下一帧 ──
        if self._state != "idle":
            self.root.after(16, self._tick)
        else:
            self._tick_running = False

    def _finish_exit(self):
        self._state = "idle"
        self._selected = -1
        self._tick_running = False
        self._canvas.delete("all")
        self._canvas.pack_forget()
        self._idle_geom()

    # ══════════════════════════════════════════════
    #  元素更新（itemconfig / coords，零创建）
    # ══════════════════════════════════════════════

    def _update_sectors(self):
        """更新扇区填充色 + 弧线颜色。"""
        if "arcs" not in self._ids:
            return
        for i in range(self._n):
            g = self._glows[i]
            # 填充块：从背景色过渡到发光色
            fill_color = _lerp_hex(RING_FILL, SECTOR_GLOW, g)
            self._canvas.itemconfig(self._ids["fills"][i], fill=fill_color)
            # 边框弧线
            line_color = _lerp_hex(SECTOR_LINE, SECTOR_HL, g)
            self._canvas.itemconfig(self._ids["arcs"][i], outline=line_color)

    def _update_labels(self):
        """更新标签颜色（高亮扇区文字变白）。"""
        if "labels" not in self._ids:
            return
        for i in range(self._n):
            g = self._glows[i]
            color = _lerp_hex(TEXT_IDLE, TEXT_HL, g)
            self._canvas.itemconfig(self._ids["labels"][i], fill=color)
            # 字号微调
            size = int(11 + g * 3)
            self._canvas.itemconfig(self._ids["labels"][i],
                                    font=("Segoe UI", size, "bold"))

    def _update_center(self):
        """中心呼吸动画。"""
        ids = self._ids
        ox, oy = self._cx, self._cy
        pulse = math.sin(self._anim_clock * 2 * math.pi / PULSE_S) * 0.4 + 0.6

        c = self._canvas
        r = CENTER_R * (0.75 + pulse * 0.5)
        c.coords(ids["center_dot"], ox - r, oy - r, ox + r, oy + r)
        hr = r * 2.5
        c.coords(ids["center_halo"], ox - hr, oy - hr, ox + hr, oy + hr)
        dot_c = _lerp_hex("#3355AA", CENTER_DOT, pulse * 1.2)
        c.itemconfig(ids["center_dot"], fill=dot_c)
        c.itemconfig(ids["center_halo"], outline=dot_c)

    def _update_sight(self):
        """移动准星（coords 更新）。"""
        if self._enter_t < 0.3:
            return
        ids = self._ids
        sx = self._cx + self._sx
        sy = self._cy + self._sy
        c = self._canvas

        # 外环
        ro = SIGHT_R * 3.0
        c.coords(ids["sight_outer"], sx - ro, sy - ro, sx + ro, sy + ro)
        # 内环
        ri = SIGHT_R * 1.8
        c.coords(ids["sight_inner"], sx - ri, sy - ri, sx + ri, sy + ri)
        # 中心点
        rd = SIGHT_R
        c.coords(ids["sight_dot"], sx - rd, sy - rd, sx + rd, sy + rd)
        # 十字线
        cl = SIGHT_CROSS_L
        c.coords(ids["sight_lines"][0], sx - cl, sy, sx - ri, sy)
        c.coords(ids["sight_lines"][1], sx + ri, sy, sx + cl, sy)
        c.coords(ids["sight_lines"][2], sx, sy - cl, sx, sy - ri)
        c.coords(ids["sight_lines"][3], sx, sy + ri, sx, sy + cl)

    def _update_flash(self):
        """确认闪光动画。"""
        if not self._confirming or self._confirm_idx < 0:
            # 隐藏
            self._canvas.coords(self._ids["flash_ring"], 0, 0, 1, 1)
            self._canvas.coords(self._ids["flash_arc"], 0, 0, 1, 1)
            return

        t = self._confirm_t
        ox, oy = self._cx, self._cy
        c = self._canvas

        # 扩散环
        prog = _ease_out(t)
        flash_r = self._menu_r * prog * 1.2
        alpha = 1.0 - prog
        if alpha > 0.01:
            shade = int(0xAA + 0x55 * alpha)
            fc = f"#{min(0xFF,shade):02x}{min(0xFF,shade):02x}FF"
            c.coords(self._ids["flash_ring"],
                     ox - flash_r, oy - flash_r,
                     ox + flash_r, oy + flash_r)
            c.itemconfig(self._ids["flash_ring"], outline=fc, width=3)
        else:
            c.coords(self._ids["flash_ring"], 0, 0, 1, 1)

        # 选中扇区高亮
        idx = self._confirm_idx
        if idx < self._n and alpha > 0.05:
            a0 = idx * self._angle - math.pi / 2
            deg0 = math.degrees(a0) + 1
            ext = math.degrees(self._angle) - 2
            fc2 = _lerp_hex(SECTOR_HL, FLASH_COLOR, alpha)
            c.coords(self._ids["flash_arc"],
                     ox - self._menu_r, oy - self._menu_r,
                     ox + self._menu_r, oy + self._menu_r)
            c.itemconfig(self._ids["flash_arc"],
                         start=deg0, extent=ext,
                         outline=fc2, width=4)
        else:
            c.coords(self._ids["flash_arc"], 0, 0, 1, 1)
