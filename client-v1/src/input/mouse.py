"""MouseInputProvider — Phase 1 鼠标模拟输入源。

将鼠标按键 / 移动 / 滚轮映射为统一的 InputEvent 事件流。
事件通过 asyncio.Queue 从 tkinter 回调传递给异步消费者。
"""

import asyncio
import math
import time
from typing import AsyncIterator

from src.input.protocol import (
    InputProvider, InputEvent, EventType,
    ButtonRole, DeviceFeedback, NoopFeedback,
)


class MouseInputProvider(InputProvider):
    """鼠标模拟输入源。

    按键映射（config.yaml 中的 button_map）：
      左键 → ButtonRole.MAIN (button_id=0)
      右键 → ButtonRole.AUX_1 (button_id=1)
      F1  → ButtonRole.AUX_2 (button_id=2)
      F2  → ButtonRole.AUX_3 (button_id=3)
    """

    def __init__(self, config):
        self._config = config
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._running = False
        self._start_time = 0.0

        # 鼠标位置跟踪（用于计算 delta）
        self._last_x = 0.0
        self._last_y = 0.0
        self._last_motion_time = 0.0

    # ── InputProvider 接口 ──

    async def start(self) -> None:
        self._running = True
        self._start_time = time.monotonic()

    async def stop(self) -> None:
        self._running = False

    async def read_events(self) -> AsyncIterator[InputEvent]:
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(), timeout=0.05
                )
                yield event
            except asyncio.TimeoutError:
                continue

    async def calibrate(self) -> None:
        pass  # 鼠标不需要校准

    # ── 反馈通道 ──

    @property
    def feedback(self) -> DeviceFeedback:
        return NoopFeedback()

    # ── 从 tkinter 回调注入事件 ──

    def _now(self) -> float:
        return time.monotonic()

    def _make_event(self, type_: EventType, **kwargs) -> InputEvent:
        return InputEvent(type=type_, timestamp=self._now(), **kwargs)

    def put_button_down(self, button_id: int) -> None:
        """由 tkinter 回调调用：按下按钮。"""
        self._event_queue.put_nowait(
            self._make_event(EventType.BUTTON_DOWN, button_id=button_id)
        )

    def put_button_up(self, button_id: int) -> None:
        """由 tkinter 回调调用：松开按钮。"""
        self._event_queue.put_nowait(
            self._make_event(EventType.BUTTON_UP, button_id=button_id)
        )

    def put_motion(self, x: int, y: int) -> None:
        """由 tkinter 回调调用：鼠标移动。

        计算相对位移并从设备中心视角给出模拟姿态值。
        """
        now = self._now()
        if self._last_motion_time == 0:
            dx, dy = 0.0, 0.0
        else:
            dt = now - self._last_motion_time
            if dt > 0:
                dx = (x - self._last_x) * self._config.mouse.sensitivity
                dy = (y - self._last_y) * self._config.mouse.sensitivity
            else:
                dx, dy = 0.0, 0.0

        self._last_x = x
        self._last_y = y
        self._last_motion_time = now

        # 模拟姿态：用鼠标位移模拟体感摆动
        # 将屏幕位移映射到 -30~30 度的姿态角变化
        roll = math.degrees(math.atan2(dx, 500))   # 左右摆
        pitch = math.degrees(math.atan2(dy, 500))   # 前后倾
        velocity = math.sqrt(dx ** 2 + dy ** 2)

        self._event_queue.put_nowait(
            self._make_event(
                EventType.MOTION,
                roll=roll,
                pitch=pitch,
                yaw=0.0,
                delta_x=dx,
                delta_y=dy,
                velocity=velocity,
            )
        )

    def put_scroll(self, delta: int) -> None:
        """由 tkinter 回调调用：滚轮转动。"""
        self._event_queue.put_nowait(
            self._make_event(EventType.SCROLL, scroll_delta=delta)
        )
