# WavePie 🌊🥧

> **BLE gesture controller — radial pie menu via motion & buttons**

WavePie is a handheld Bluetooth controller that lets you control your computer through **gestures**. A built-in 6‑axis IMU tracks your wrist motion, buttons and a scroll wheel provide direct input, and a radial pie menu on screen gives you quick access to common actions — all over BLE.

```
┌──────────────────┐     BLE      ┌──────────────────────┐
│  ESP32 + MPU6050 │  ────────→   │  PC receiver          │
│                  │  FF01~FF10   │  ┌──────────────────┐ │
│  Buttons · IMU   │              │  │ Radial Pie Menu  │ │
│  Scroll · LED    │  ←────────   │  │ Gesture Engine   │ │
│  Buzzer          │  反馈指令    │  │ Action Executor  │ │
└──────────────────┘              └──────────────────────┘
```

## Project Structure

```
├── v1/                  # Software prototype (mouse + keyboard simulation)
│   ├── src/             # Python PC-side application
│   ├── config.yaml      # Button mappings, menu items, gesture params
│   └── tools/           # Diagnostic tools
├── firmware/             # ESP32 firmware (Arduino)
│   ├── firmware.ino     # Main entry
│   ├── ble_service.*    # BLE GATT service
│   ├── mpu6050.*        # IMU driver
│   ├── imu_filter.h     # Complementary filter
│   ├── buttons.*        # Multi-button debounce
│   └── feedback.*       # LED / buzzer control
├── .devlog/             # Development logs
├── DEVELOPMENT_FRAMEWORK.md
├── DECISION_LOG.md
├── SESSION_STATE.md
└── HARDWARE_SHOPPING_LIST.md
```

## Current Status

| Component | Status |
|-----------|--------|
| **v1 — Software Prototype** | ✅ Complete — F12 + gamepad modes, 12-item radial menu, scroll volume |
| **Firmware — ESP32 + MPU6050** | ✅ Written — waiting for hardware to arrive for testing |
| **Hardware** | ⏳ BOM ready (~¥60-80), parts not yet ordered |
| **PC BLE Integration (v2)** | ⬜ Not started |

## Quick Start (Software Prototype)

```bash
cd v1
pip install -r requirements.txt
python -m src.main          # Keyboard mode (F12)
python -m src.main_gamepad  # Gamepad mode (L2 trigger)
```

## License

[GPLv3](LICENSE) — WavePie is free software. You can use, modify, and
distribute it under the terms of the GNU General Public License v3.
