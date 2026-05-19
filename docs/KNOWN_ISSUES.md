# WavePie 关键问题知识库

> 本文档记录 V1→V3 开发过程中遇到且已验证的致命问题及根治方案。
> 后续 AI 在修改涉及以下模块的代码前，必须先阅读本文档。

---

## KB-001: 多显示器透明 Overlay 坐标转换

**状态**: ✅ 已验证，V3 修复
**严重度**: 🔴 致命（菜单完全不出现在非主显示器）

### 问题

当虚拟桌面原点 `(vx, vy)` 不为 `(0, 0)` 时（比如左显示器在主显左侧），
从 Windows API (`GetMonitorInfoW`) 获取的显示器中央坐标是**屏幕空间坐标**，
但 tkinter Canvas 的坐标系是**窗口本地坐标**。

二者差了一个窗口原点偏移量。

### 错误代码
```python
# GetMonitorInfoW 返回的是屏幕坐标
self._cx = cx_screen      # 例如 -1280（左显示器中央在屏幕坐标）
self._cy = cy_screen
# Canvas 在 create_arc 时当作本地坐标 → 画到 (-1280, cy) 本地
# 窗口起点是 (-2560, 0) → 实际画出在 (-3840, cy) 屏幕位置 → 飞出桌面！
```

### 正确代码
```python
# 屏幕坐标 → Canvas 本地坐标
self._cx = cx_screen - self._vx   # -1280 - (-2560) = 1280
self._cy = cy_screen - self._vy
```

### 校验公式
```
本地坐标 = 屏幕坐标 - 窗口原点
```

窗口原点 = `(self._vx, self._vy)` = `GetSystemMetrics(76, 77)`
```
76 = SM_XVIRTUALSCREEN
77 = SM_YVIRTUALSCREEN
```

### 影响范围
- `OverlayUI._active_geom()` — 菜单圆心定位
- 所有从 Windows API 获取坐标后直接用于 Canvas 绘制的代码
- 已知影响：ViewSonic/LG 等多显示器 → 非主显不显示菜单

### 相关 commit
```
fix: screen-to-canvas coordinate conversion for multi-monitor
```

---

## KB-002: `winfo_screenwidth()` 不可靠

**状态**: ✅ 已弃用
**严重度**: 🟡 中等

### 问题

`tkinter.winfo_screenwidth()` 在高 DPI 或多显示器环境中可能返回缩放过或错误的宽度。
必须使用 Win32 API `GetSystemMetrics(78, 79)` 获取真实虚拟桌面尺寸。

### 正确方法
```python
import ctypes
user32 = ctypes.windll.user32
vw = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
vh = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
```

---

## KB-003: ESP32 GPIO 引脚禁区

**状态**: ✅ 已验证
**严重度**: 🔴 致命（烧芯片或完全不起效）

### 不可用的 GPIO

| 引脚 | 原因 | 后果 |
|------|------|------|
| GPIO 1 | TXD0（串口发送） | 干扰串口 |
| GPIO 3 | RXD0（串口接收） | 干扰串口 |
| GPIO 6-11 | 内部 SPI Flash | **操作会死机重启** |

### V3 固件安全引脚分配
```
LED:     GPIO 2
Button:  GPIO 4
I2C SDA: GPIO 21
I2C SCL: GPIO 22
```

---

## KB-004: BLE 断开后自动重广播

**状态**: ✅ 已修复
**严重度**: 🟡 中等

### 问题

ESP32 BLE 客户端断开连接后，默认不自动重启广告。
PC 端重启后必须按 EN 键或重新上电才能搜到。

### 修复

`ble_service.h` 的 `ServerCB::onDisconnect` 中添加：
```cpp
void onDisconnect(BLEServer* s) override {
    *_flag = false;
    s->startAdvertising();  // ← 这一行
}
```

---

## KB-005: 准星方向调试

**状态**: ✅ 已验证（MPU6050 逆时针旋转 90° 摆放）

### 坐标轴映射（2026-05-16 最终确认）

| 用户动作 | 固件积分 | BLE 字节 | main.py | 效果 |
|---------|---------|---------|---------|------|
| 手腕左转 | accum_roll += gz | roll_byte | rx = -roll / 127 × 1.5 | 准星左移 |
| 手腕右转 | accum_roll += gz | roll_byte | rx = -roll / 127 × 1.5 | 准星右移 |
| 手腕前倾（枪口上抬） | accum_pitch += gx | pitch_byte | ry = -pitch / 127 × 1.5 | 准星上移 |
| 手腕后仰（枪口下压） | accum_pitch += gx | pitch_byte | ry = -pitch / 127 × 1.5 | 准星下移 |

### 关键公式

俯视图（芯片平放，文字朝上，小圆点左前，逆时针旋转 90°）：

```
        前倾（上）
            ↑
   左转 ←  芯片  → 右转
            ↓
        后仰（下）
```

- 陀螺仪 Z 轴（gz）= 左右旋转（yaw）→ `accum_roll`
- 陀螺仪 X 轴（gx）= 前后俯仰（pitch）→ `accum_pitch`

### 以后改方向只需调 main.py 的符号

```python
rx = -ble.latest_roll / 127.0 * 1.5   # 取反 = 方向正确
ry = -ble.latest_pitch / 127.0 * 1.5  # 取反 = 方向正确
```

---

## KB-006: Python 依赖的 bleak 3.x 没有 `get_services()`

**状态**: ✅ 已知
**严重度**: 🟡 中等

### 说明

bleak 3.x 移除了 `client.get_services()` 方法。服务在 `connect()` 后自动发现，
通过 `client.services` 属性访问。可能需要等待 1 秒让服务发现完成。

```python
await client.connect()
await asyncio.sleep(1.0)  # 等待自动发现
for svc in client.services:
    ...
```
