"""BLEInputProvider — 通过 BLE 接收 ESP32 体感控制器数据。

实现 InputProvider 接口，用 bleak 库：
  - 扫描并连接 `BLE Gesture Ctrl` 设备
  - 订阅 IMU/按键 通知
  - 解析数据为 InputEvent 流
  - 通过反馈特性发送 LED/蜂鸣指令
"""

import asyncio
import struct
import time
from typing import AsyncIterator, Optional

from src.input.protocol import (
    InputProvider, InputEvent, EventType,
    DeviceFeedback, FeedbackCommand,
    LedColor, LedPattern,
)

# ── BLE 服务/特性 UUID（与固件一致）──
SERVICE_UUID        = "0000FF00-0000-1000-8000-00805F9B34FB"
CHAR_BUTTONS_UUID   = "0000FF01-0000-1000-8000-00805F9B34FB"
CHAR_IMU_UUID       = "0000FF02-0000-1000-8000-00805F9B34FB"
CHAR_SCROLL_UUID    = "0000FF03-0000-1000-8000-00805F9B34FB"
CHAR_FEEDBACK_UUID  = "0000FF10-0000-1000-8000-00805F9B34FB"

DEVICE_NAME = "BLE Gesture Ctrl"


# ============================================================
# BLE 反馈通道
# ============================================================

class BLEFeedback(DeviceFeedback):
    """通过 BLE 向 ESP32 发送 LED/蜂鸣指令。"""

    def __init__(self):
        self._client = None
        self._char = None

    def _bind(self, client, characteristic):
        """由 BLEInputProvider 在连接后绑定。"""
        self._client = client
        self._char = characteristic

    async def send(self, command: FeedbackCommand) -> None:
        if not self._char:
            return
        # 4 字节: [LED模式(高4bits)+LED颜色(低4bits), 蜂鸣状态, 震动ms, 状态码]
        led_byte = 0
        if command.led_pattern == LedPattern.SOLID:
            led_byte |= 0x10
        elif command.led_pattern == LedPattern.SLOW_BLINK:
            led_byte |= 0x20
        elif command.led_pattern == LedPattern.FAST_BLINK:
            led_byte |= 0x30
        elif command.led_pattern == LedPattern.PULSE:
            led_byte |= 0x40

        if command.led_color == LedColor.RED:
            led_byte |= 0x01
        elif command.led_color == LedColor.GREEN:
            led_byte |= 0x02
        elif command.led_color == LedColor.BLUE:
            led_byte |= 0x03
        elif command.led_color == LedColor.YELLOW:
            led_byte |= 0x04

        payload = bytes([
            led_byte,
            1 if command.buzzer_on else 0,
            min(command.vibration_ms, 255) & 0xFF,
            command.status_code & 0xFF,
        ])
        try:
            await self._char.write_value(payload)
        except Exception:
            pass

    async def is_connected(self) -> bool:
        if not self._client:
            return False
        try:
            return self._client.is_connected
        except Exception:
            return False


# ============================================================
# BLE 输入源
# ============================================================

class BLEMotionInputProvider(InputProvider):
    """通过 BLE 接收 ESP32 体感数据。"""

    def __init__(self, config):
        self._config = config
        self._client: Optional[object] = None  # bleak BleakClient
        self._running = False
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._feedback = BLEFeedback()
        self._device: Optional[object] = None

    # ── InputProvider 接口 ──

    async def start(self) -> None:
        """扫描 → 连接 → 订阅通知。"""
        from bleak import BleakScanner, BleakClient

        # 1. 扫描设备
        print("[BLE] 🔍 扫描中...")
        device = None
        for _ in range(30):  # 最多重试 30 次（~15秒）
            devices = await BleakScanner.discover(timeout=2.0)
            for d in devices:
                if d.name and DEVICE_NAME in d.name:
                    device = d
                    break
            if device:
                break
            print("[BLE] 🔍 未找到，继续扫描...")

        if not device:
            raise ConnectionError(f"未找到 BLE 设备: {DEVICE_NAME}")

        self._device = device
        print(f"[BLE] ✅ 找到设备: {device.name} ({device.address})")

        # 2. 连接
        client = BleakClient(device.address)
        await client.connect()
        self._client = client
        print(f"[BLE] ✅ 已连接: {device.address}")

        # 3. 发现服务
        for service in client.services:
            if str(service.uuid).upper() == SERVICE_UUID.upper():
                print(f"[BLE] ✅ 找到服务: {service.uuid}")
                break

        # 4. 订阅按键通知
        def on_button(sender, data: bytearray):
            if len(data) >= 2:
                btn_id = data[0]
                flags = data[1]
                now = time.monotonic()
                if flags & 0x01:
                    evt = InputEvent(
                        type=EventType.BUTTON_DOWN,
                        timestamp=now, button_id=btn_id,
                    )
                else:
                    evt = InputEvent(
                        type=EventType.BUTTON_UP,
                        timestamp=now, button_id=btn_id,
                    )
                try:
                    self._event_queue.put_nowait(evt)
                except asyncio.QueueFull:
                    pass

        # 5. 订阅 IMU 通知
        def on_imu(sender, data: bytearray):
            if len(data) >= 12:
                roll, pitch, yaw = struct.unpack_from('<fff', data, 0)
                now = time.monotonic()
                evt = InputEvent(
                    type=EventType.MOTION,
                    timestamp=now,
                    roll=roll, pitch=pitch, yaw=yaw,
                )
                try:
                    self._event_queue.put_nowait(evt)
                except asyncio.QueueFull:
                    pass

        # 查找特性并订阅
        for svc in client.services:
            for char in svc.characteristics:
                uuid = str(char.uuid).upper()
                if uuid == CHAR_BUTTONS_UUID.upper() and "notify" in char.properties:
                    await client.start_notify(char.uuid, on_button)
                    print("[BLE] 📩 已订阅按键通知")
                elif uuid == CHAR_IMU_UUID.upper() and "notify" in char.properties:
                    await client.start_notify(char.uuid, on_imu)
                    print("[BLE] 📩 已订阅 IMU 通知")
                elif uuid == CHAR_FEEDBACK_UUID.upper() and "write" in char.properties:
                    self._feedback._bind(client, char)
                    print("[BLE] 📤 反馈通道就绪")

        self._running = True
        print("[BLE] 🟢 输入源已启动")

    async def stop(self) -> None:
        self._running = False
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
        print("[BLE] 🔴 已断开")

    async def read_events(self) -> AsyncIterator[InputEvent]:
        """异步遍历输入事件流。"""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(), timeout=1.0
                )
                yield event
            except asyncio.TimeoutError:
                continue

    async def calibrate(self) -> None:
        """IMU 零偏校准（等待 ESP32 完成校准）。"""
        print("[BLE] 📐 校准中...")
        # ESP32 在上电时已自动校准，这里等待 2 秒
        await asyncio.sleep(2)
        print("[BLE] ✅ 校准完成")

    @property
    def feedback(self) -> DeviceFeedback:
        return self._feedback
