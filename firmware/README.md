# WavePie V2 固件 — 手枪式握把体感开关

## 新架构

```
Core 0: MPU6050 (100Hz) → Madgwick 滤波 → 激活锁定 → 扇区映射 → BLE 发送
Core 1: BLE 广播 + 连接管理
```

## 协议

| 包类型 | 命令字 | 数据 | 说明 |
|--------|--------|------|------|
| 扇区更新 | 0xAA | 扇区索引(1B) | 激活期间实时发送 |
| 确认执行 | 0xBB | 最终扇区(1B) | 松开按键时发送 |

## 扇区映射

- max_angle = ±60° 覆盖全部 12 扇区
- 迟滞 5° 防止边界抖动
- 水平指向角从相对四元数 q_rel 提取

## 烧录

Arduino IDE 打开 firmware.ino，选 ESP32 Dev Module 上传。

## 引脚

- GPIO 4 (INPUT_PULLUP) → 按键 → GND
- GPIO 2 → 板载 LED（激活时亮）
- SDA=21, SCL=22 → MPU6050
