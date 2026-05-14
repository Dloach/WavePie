"""GestureEngine — 手势处理引擎。

将输入事件中的姿态/位移数据映射为光标选择。
Phase 1 中处理来自鼠标的 MOTION 事件，Phase 3 处理 IMU 数据。
"""

from dataclasses import dataclass


@dataclass
class GestureOutput:
    """手势引擎处理结果。"""
    cursor_index: int       # 当前高亮的菜单项索引（0-based）
    delta_x: float          # 累计 X 偏移
    delta_y: float          # 累计 Y 偏移
    confidence: float       # 置信度 0~1


class GestureEngine:
    """手势引擎。

    职责：
    1. 死区滤波：微小抖动不触发选择变化
    2. 加速度映射：摆得快 = 光标移动大
    3. 累计偏差 → 菜单项索引
    """

    def __init__(self, config):
        self._config = config
        self.reset()

    def reset(self) -> None:
        """重置累计状态。"""
        self._accum_x = 0.0
        self._accum_y = 0.0
        self._last_output = GestureOutput(
            cursor_index=0, delta_x=0.0, delta_y=0.0, confidence=0.0
        )

    def process(self, roll: float, pitch: float, velocity: float,
                num_items: int) -> GestureOutput:
        """处理一帧姿态/位移数据，返回当前应高亮的菜单索引。

        Args:
            roll: 左右摆动角度（度），来自 InputEvent.roll
            pitch: 前后倾斜角度（度），来自 InputEvent.pitch
            velocity: 摆动速度（绝对值），来自 InputEvent.velocity
            num_items: 菜单项总数

        Returns:
            GestureOutput 包含当前选中的索引
        """
        # 1. 死区滤波
        if abs(roll) < self._config.dead_zone * 10:
            roll = 0.0
        if abs(pitch) < self._config.dead_zone * 10:
            pitch = 0.0

        # 2. 灵敏度缩放
        roll *= self._config.sensitivity
        pitch *= self._config.sensitivity

        # 3. 加速度映射
        if self._config.acceleration and velocity > 1.0:
            # 根据速度动态放大位移（速度越快，放大越多）
            accel_factor = 1.0 + (velocity / 10.0)
            roll *= accel_factor
            pitch *= accel_factor

        # 4. 累加到累计位移
        #    使用指数移动平均做平滑
        alpha = 0.6  # 新数据权重
        self._accum_x = self._accum_x * (1 - alpha) + roll * alpha
        self._accum_y = self._accum_y * (1 - alpha) + pitch * alpha

        # 5. 累计位移 → 菜单索引
        #    竖排菜单：用 pitch（上下倾斜）控制选择
        #    横排菜单：用 roll（左右摆动）控制选择（可配）
        if num_items <= 1:
            idx = 0
        else:
            # 每 15 度偏移切换一个选项
            threshold = 15.0
            idx = int(self._accum_y / threshold)   # 正：上移=负值→索引减小，下移=正值→索引增大
            # 钳位到有效范围
            idx = max(0, min(idx, num_items - 1))

        return GestureOutput(
            cursor_index=idx,
            delta_x=self._accum_x,
            delta_y=self._accum_y,
            confidence=min(1.0, abs(self._accum_x) / (threshold * num_items)),
        )
