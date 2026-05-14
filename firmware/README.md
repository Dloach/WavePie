# ESP32 固件 — 蓝牙体感控制器

## 开发环境

- **Arduino IDE**（推荐）或 **PlatformIO**
- 安装 ESP32 开发板支持包：
  1. Arduino IDE → 文件 → 首选项 → 附加开发板管理器 URL 添加：
     `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
  2. 工具 → 开发板 → 开发板管理器 → 搜索 ESP32 → 安装

## 烧录步骤

1. 用 Micro USB 线连接 ESP32 到电脑
2. Arduino IDE 中选择：
   - 开发板: `ESP32 Dev Module`
   - 端口: (选择你的 ESP32 串口)
3. 打开 `firmware.ino`
4. 点击上传

## 接线

```
ESP32 (30脚)          MPU6050
─────────────────     ────────
3V3  ──────────────── VCC
GND  ──────────────── GND
GPIO 21 ───────────── SDA
GPIO 22 ───────────── SCL

ESP32                 按键
─────────────────     ────────
GPIO 4 (INPUT_PULLUP) ── 主按钮 ── GND
GPIO 5                ── 副键1  ── GND
GPIO 6                ── 副键2  ── GND

ESP32                 LED
─────────────────     ────────────
GPIO 2 (PWM) ── 220Ω ── LED_R(+) ── LED_R(-) ── GND
GPIO 3 (PWM) ── 220Ω ── LED_G(+) ── LED_G(-) ── GND

ESP32                 蜂鸣器
─────────────────     ────────
GPIO 7                ── 蜂鸣器(+) ── GND
```

## BLE 通信协议

| 方向 | 特性 | UUID | 格式 |
|------|------|------|------|
| 设备→PC | 按键 | FF01 | 2 bytes: id, flags |
| 设备→PC | IMU | FF02 | 12 bytes: roll/pitch/yaw (float32×3) |
| 设备→PC | 滚轮 | FF03 | 1 byte: delta (int8) |
| PC→设备 | 反馈 | FF10 | 4 bytes: LED/蜂鸣/状态码 |

## PC 端连接

```bash
cd v1 && python3 -m src.main
```
