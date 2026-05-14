"""硬件抽象层 (HAL) — 核心接口定义。

所有输入/输出源通过此接口与业务代码交互。
Phase 1 用 MouseInputProvider，Phase 3 用 BLEInputProvider，只需切换配置。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import AsyncIterator, Optional


# ============================================================
# 事件类型 & 枚举
# ============================================================

class EventType(Enum):
    """输入事件类型。"""
    BUTTON_DOWN = "button_down"   # 某键按下
    BUTTON_UP   = "button_up"     # 某键松开
    MOTION      = "motion"        # 姿态/鼠标移动
    SCROLL      = "scroll"        # 滚轮转动
    IDLE        = "idle"          # 无操作（心跳）


class ButtonRole(IntEnum):
    """硬件按键的逻辑角色。

    Phase 1 模拟阶段用 tkinter 事件名映射；
    Phase 3 真实阶段用 BLE button_id 映射。
    """
    MAIN       = 0    # 主按钮：触发 Overlay 体感选择
    AUX_1      = 1    # 副键1：可配置直接动作
    AUX_2      = 2    # 副键2
    AUX_3      = 3    # 副键3
    # 可继续扩展 AUX_N ...


# ============================================================
# 输入事件
# ============================================================

@dataclass
class InputEvent:
    """一条从输入源到达的统一事件。"""
    type: EventType
    timestamp: float                   # monotonic 时间戳

    # ── 按键相关（BUTTON_DOWN / BUTTON_UP 时有效）──
    button_id: int = 0                 # 对应 ButtonRole 或 raw ID
    is_long_press: bool = False        # 长按标志（预留）

    # ── 姿态数据（MOTION 时有效）──
    roll: float = 0.0                  # Z轴旋转（左右摆） -180 ~ 180
    pitch: float = 0.0                 # Y轴旋转（前后倾） -180 ~ 180
    yaw: float = 0.0                   # X轴旋转（水平转） -180 ~ 180

    # ── 滚轮数据（SCROLL 时有效）──
    scroll_delta: int = 0              # +1 顺/下，-1 逆/上

    # ── 派生数据（下游引擎填充）──
    delta_x: float = 0.0               # 光标 X 偏移（归一化 -1..1）
    delta_y: float = 0.0               # 光标 Y 偏移（归一化 -1..1）
    velocity: float = 0.0              # 摆动速度


# ============================================================
# 输入源接口
# ============================================================

class InputProvider(ABC):
    """所有输入源的统一抽象接口（双向：读事件，写反馈）。"""

    # ── 输入端 ──

    @abstractmethod
    async def start(self) -> None:
        """启动输入源（打开设备 / 监听端口 / 启动钩子）。"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """停止输入源，释放资源。"""
        ...

    @abstractmethod
    def read_events(self) -> AsyncIterator[InputEvent]:
        """异步遍历输入事件流。

        Usage:
            async for event in provider.read_events():
                handle(event)
        """
        ...

    @abstractmethod
    async def calibrate(self) -> None:
        """校准（IMU 归零 / 灵敏度设定）。"""
        ...

    # ── 输出端（软件 → 硬件）──

    @property
    @abstractmethod
    def feedback(self) -> "DeviceFeedback":
        """获取反馈通道。不支持反馈时返回 NoopFeedback。"""
        ...


# ============================================================
# 设备反馈接口（软件 → 硬件）
# ============================================================

class LedColor(Enum):
    OFF    = "off"
    RED    = "red"
    GREEN  = "green"
    BLUE   = "blue"
    YELLOW = "yellow"


class LedPattern(Enum):
    SOLID      = "solid"       # 常亮
    SLOW_BLINK = "slow_blink"  # 慢闪（~1Hz）
    FAST_BLINK = "fast_blink"  # 快闪（~3Hz）
    PULSE      = "pulse"       # 呼吸


@dataclass
class FeedbackCommand:
    """一次反馈指令，可同时设置多种信号。"""
    led_color: Optional[LedColor] = None
    led_pattern: Optional[LedPattern] = None
    buzzer_on: bool = False
    vibration_ms: int = 0
    status_code: int = 0          # 0=正常，非0=错误码


class DeviceFeedback(ABC):
    """软件 → 设备的反馈通道。"""

    @abstractmethod
    async def send(self, command: FeedbackCommand) -> None:
        """发送反馈指令到设备。"""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """反馈通道是否可用。"""
        ...


# ============================================================
# 空实现（模拟阶段用）
# ============================================================

class NoopFeedback(DeviceFeedback):
    """模拟阶段空实现，所有操作为 No-op。"""

    async def send(self, command: FeedbackCommand) -> None:
        pass

    async def is_connected(self) -> bool:
        return False
