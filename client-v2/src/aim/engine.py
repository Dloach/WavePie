"""AimEngine — 激光准星引擎（速率控制）。

当用户按下扳机时：
  1. 记录当前姿态为零点基准
  2. 准星置于圆环中心
运动中：
  倾斜偏离零点 → 准星持续漂移（速率=倾斜量×灵敏度）
  回正到零点   → 准星停止
  准星始终约束在圆环（内径~外径）之间
松开扳机：
  返回当前高亮扇区索引

坐标系：
  圆心 = (cx, cy)
  内径 = center_r，外径 = visible_r
  roll  (左右倾) → X 方向漂移
  pitch (前后倾) → Y 方向漂移
"""

import math
import time


class AimEngine:
    def __init__(self, config):
        self._cfg = config.aim
        self.reset()

    def reset(self):
        self._x = 0.0          # 准星相对圆心的偏移 X
        self._y = 0.0          # 准星相对圆心的偏移 Y
        self._ref_roll = 0.0
        self._ref_pitch = 0.0
        self._active = False
        self._last_update = 0.0
        self._vx = 0.0
        self._vy = 0.0
        self._center_r = 200.0  # 默认值，由 overlay 在 run/activate 时设置
        self._visible_r = 480.0

    def set_ring(self, inner_r: float, outer_r: float):
        """由 OverlayUI 设置圆环尺寸。"""
        self._center_r = inner_r
        self._visible_r = outer_r

    def on_trigger(self, roll: float, pitch: float):
        """扳机按下：校准零点，准星居中。"""
        self._ref_roll = roll
        self._ref_pitch = pitch
        self._x = 0.0
        self._y = 0.0
        self._vx = 0.0
        self._vy = 0.0
        self._active = True
        self._last_update = time.monotonic()
        print(f"[Aim] 🎯 触发，零点 roll={roll:.1f} pitch={pitch:.1f}")

    def on_motion(self, roll: float, pitch: float):
        """姿态更新：速率漂移准星位置。"""
        if not self._active:
            return

        now = time.monotonic()
        dt = min(now - self._last_update, 0.1)  # cap to 100ms
        self._last_update = now

        dz = self._cfg.dead_zone
        sens = self._cfg.sensitivity
        smooth = self._cfg.smoothing

        # 倾斜偏移量
        dx_raw = pitch - self._ref_pitch  # pitch → X
        dy_raw = -(roll - self._ref_roll)  # roll → Y (正roll=左倾→向上)

        # 死区
        if abs(dx_raw) < dz:
            dx_raw = 0.0
        if abs(dy_raw) < dz:
            dy_raw = 0.0

        # 速率（带平滑）
        target_vx = dx_raw * sens
        target_vy = dy_raw * sens
        self._vx = self._vx * smooth + target_vx * (1 - smooth)
        self._vy = self._vy * smooth + target_vy * (1 - smooth)

        # 漂移
        self._x += self._vx * dt
        self._y += self._vy * dt

        # 约束到圆环内
        dist = math.hypot(self._x, self._y)
        if dist > self._visible_r:
            self._x = self._x / dist * self._visible_r
            self._y = self._y / dist * self._visible_r
        elif dist < self._center_r and dist > 0:
            # 拉到内径边缘
            self._x = self._x / dist * self._center_r
            self._y = self._y / dist * self._center_r

    def on_release(self) -> int:
        """扳机松开：返回当前高亮扇区索引，重置。"""
        idx = self.get_sector()
        self._active = False
        self._x = 0.0
        self._y = 0.0
        self._vx = 0.0
        self._vy = 0.0
        return idx

    def get_sector(self, num_items: int = 12) -> int:
        """返回准星当前指向的扇区索引（0-based）。"""
        if not self._active:
            return -1
        if self._x == 0.0 and self._y == 0.0:
            return -1
        angle = math.degrees(math.atan2(self._x, -self._y)) % 360
        sector_deg = 360.0 / num_items
        return int((angle + sector_deg / 2) / sector_deg) % num_items

    def get_cursor(self) -> tuple:
        """返回准星坐标 (x, y) 供 UI 绘制。"""
        return (self._x, self._y)

    @property
    def is_active(self) -> bool:
        return self._active
