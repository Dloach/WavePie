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
├── client-v1/           # PC client — software prototype
│   ├── src/             # Python PC-side application
│   │   ├── app.py       # 🌟 统一入口（托盘 + F12 + 手柄）
│   │   ├── tray.py      # 系统托盘图标
│   │   ├── config_editor.py  # 配置编辑器 GUI
│   │   ├── ui/          # 径向菜单 OverlayUI
│   │   ├── input/       # 输入层 (mouse/gamepad/protocol)
│   │   ├── mapper/      # ActionMapper 路由
│   │   ├── gesture/     # 手势引擎
│   │   ├── executor/    # 跨平台键盘模拟
│   │   └── utils/       # YAML 配置加载
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
├── HARDWARE_SHOPPING_LIST.md
└── WavePie.exe          # 🚀 打包后的单文件 exe（拖桌面即用）
```

## Current Status

| Component | Status |
|-----------|--------|
| **client-v1 — PC Client** | ✅ F12 + gamepad, 托盘图标, 配置编辑器 GUI |
| **Packaged EXE** | ✅ WavePie.exe — 零安装，删文件即卸载 |
| **Firmware — ESP32 + MPU6050** | ✅ Written — waiting for hardware |
| **Hardware** | ⏳ BOM ready (~¥60-80), not yet ordered |
| **PC BLE Integration** | ⬜ Not started (waiting for hardware) |

## Quick Start

### 开发模式
```bash
cd client-v1
pip install -r requirements.txt
python -m src.app            # 🌟 统一入口（托盘 + F12 + 手柄）
```

### 打包运行
直接双击 `WavePie.exe` — 启动后缩到系统托盘，F12 弹出菜单。

## License

[GPLv3](LICENSE) — WavePie is free software. You can use, modify, and
distribute it under the terms of the GNU General Public License v3.
