"""BLEInputProvider — V2 精简版。

功能：
  - 扫描连接 ESP32（设备名可配）
  - 订阅 IMU 通知 → 写 latest_roll/pitch/yaw
  - 订阅按键通知 → 回调 on_button(id, pressed)
  - 无事件队列（V2 主线程轮询 latest_*）
"""

import asyncio
import struct
from typing import Optional, Callable

SERVICE_UUID       = "0000FF00-0000-1000-8000-00805F9B34FB"
CHAR_BUTTONS_UUID  = "0000FF01-0000-1000-8000-00805F9B34FB"
CHAR_IMU_UUID      = "0000FF02-0000-1000-8000-00805F9B34FB"
CHAR_FEEDBACK_UUID = "0000FF10-0000-1000-8000-00805F9B34FB"


class BLEInputProvider:
    """ESP32 体感输入源。"""

    def __init__(self, device_name: str = "BLE Gesture Ctrl"):
        self._device_name = device_name
        self._client: Optional[object] = None
        self._running = False
        self._on_button: Optional[Callable] = None  # cb(button_id, pressed)

        # 最新 IMU 数据（主线程轮询）
        self.latest_roll = 0.0
        self.latest_pitch = 0.0
        self.latest_yaw = 0.0

    @property
    def is_connected(self) -> bool:
        if not self._client:
            return False
        try:
            return self._client.is_connected
        except Exception:
            return False

    def set_on_button(self, cb: Callable):
        """设置按键回调。"""
        self._on_button = cb

    async def start(self):
        from bleak import BleakScanner, BleakClient

        print("[BLE] 🔍 扫描中...")
        device = None
        for _ in range(30):
            devices = await BleakScanner.discover(timeout=2.0)
            for d in devices:
                if d.name and self._device_name in d.name:
                    device = d
                    break
            if device:
                break

        if not device:
            raise ConnectionError(f"未找到 {self._device_name}")

        print(f"[BLE] ✅ {device.name} ({device.address})")
        client = BleakClient(device.address)
        await client.connect()
        self._client = client
        print(f"[BLE] ✅ 已连接")

        # 等待服务自动发现
        await asyncio.sleep(1.0)
        found = any(
            str(s.uuid).upper() == SERVICE_UUID.upper()
            for s in client.services
        )
        print(f"[BLE] {'✅ 找到 FF00 服务' if found else '⚠️ 未找到 FF00'}")

        # 订阅按键
        def on_button(sender, data: bytearray):
            if len(data) >= 2 and self._on_button:
                self._on_button(data[0], bool(data[1] & 0x01))

        # 订阅 IMU
        def on_imu(sender, data: bytearray):
            if len(data) >= 12:
                r, p, y = struct.unpack_from('<fff', data, 0)
                self.latest_roll = r
                self.latest_pitch = p
                self.latest_yaw = y

        for svc in client.services:
            for char in svc.characteristics:
                u = str(char.uuid).upper()
                if u == CHAR_BUTTONS_UUID.upper() and "notify" in char.properties:
                    await client.start_notify(char.uuid, on_button)
                    print("[BLE] 📩 已订阅按键")
                elif u == CHAR_IMU_UUID.upper() and "notify" in char.properties:
                    await client.start_notify(char.uuid, on_imu)
                    print("[BLE] 📩 已订阅 IMU")

        self._running = True
        print("[BLE] 🟢 输入源就绪")

    async def stop(self):
        self._running = False
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
        print("[BLE] 🔴 已断开")
