"""BLEInputProvider — V2 接收 2D 瞄准数据（roll_byte + pitch_byte）。"""

import asyncio
from typing import Optional, Callable

SERVICE_UUID      = "0000FF00-0000-1000-8000-00805F9B34FB"
CHAR_STATE_UUID   = "0000FF01-0000-1000-8000-00805F9B34FB"


class BLEInputProvider:
    def __init__(self, device_name: str = "WavePie"):
        self._device_name = device_name
        self._client: Optional[object] = None
        self._running = False

        self.on_aim: Optional[Callable] = None       # cb(roll_byte, pitch_byte)
        self.on_confirm: Optional[Callable] = None    # cb(sector)

    @property
    def is_connected(self) -> bool:
        if not self._client:
            return False
        try:
            return self._client.is_connected
        except Exception:
            return False

    async def start(self):
        from bleak import BleakScanner, BleakClient

        print("[BLE] 🔍 扫描中...")
        device = None
        names = [self._device_name, "BLE Gesture Ctrl"]
        for _ in range(30):
            devices = await BleakScanner.discover(timeout=2.0)
            for d in devices:
                if d.name:
                    for n in names:
                        if n in d.name:
                            device = d
                            break
                    if device:
                        break
            if device:
                break

        if not device:
            raise ConnectionError(f"未找到 {' / '.join(names)}")

        print(f"[BLE] ✅ {device.name}")
        client = BleakClient(device.address)
        await client.connect()
        self._client = client
        print(f"[BLE] ✅ 已连接")
        await asyncio.sleep(1.0)

        # 解析 0xAA + 2 bytes (aim) 或 0xBB + 1 byte (confirm)
        def on_state(sender, data: bytearray):
            if len(data) < 2:
                return
            cmd = data[0]
            if cmd == 0xAA and len(data) >= 3 and self.on_aim:
                roll = data[1] if data[1] < 128 else data[1] - 256  # unsigned→signed
                pitch = data[2] if data[2] < 128 else data[2] - 256
                self.on_aim(roll, pitch)
            elif cmd == 0xBB and self.on_confirm:
                self.on_confirm(data[1])

        for svc in client.services:
            for char in svc.characteristics:
                u = str(char.uuid).upper()
                if u == CHAR_STATE_UUID.upper() and "notify" in char.properties:
                    await client.start_notify(char.uuid, on_state)
                    print("[BLE] 📩 已订阅状态")

        self._running = True
        print("[BLE] 🟢 就绪")

    async def stop(self):
        self._running = False
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
