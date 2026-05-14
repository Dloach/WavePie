# 2024-12-17: 大规模开发 session — 完成 v1 全部功能 + ESP32 固件

## 操作人
AI + 开发者

## 涉及版本
v1（软件模拟原型）+ firmware（固件）

## 本次完成的功能

### 1. 鼠标版（main.py → F12 触发）
- F12 按住弹出径向菜单，松开执行
- 指针连线从圆心到鼠标
- 选中扇区高亮+外发光
- Esc 取消/退出
- 滚轮音量控制

### 2. 径向菜单 UI（overlay.py）
- 圆形环状菜单，12个扇区
- 12点方向对齐扇区中心
- 中空区域 480px，可见外径 800px
- 外发光 + Emoji 图标 + 中文标签
- 全透明背景（transparentcolor black）
- 多显示器覆盖（虚拟桌面）

### 3. 手柄支持（gamepad.py → pygame 后端）
- XInput 手柄跳过 DualSense 自动连接
- 左摇杆方向控制扇区选择
- L2 扳机按住激活/松开执行
- F12 备用触发

### 4. 硬件采购清单（HARDWARE_SHOPPING_LIST.md）
- ESP32-DevKitC (WROOM-32D) 开发板
- MPU6050 IMU 传感器
- 面包板、杜邦线、按键、LED 等

### 5. ESP32 固件（firmware/）
- BLE GATT 服务（FF01-FF10 四个特性）
- MPU6050 I2C 驱动 + 校准
- 互补滤波（roll/pitch/yaw）
- 多按键去抖 + 长按检测
- LED/蜂鸣器反馈控制

## Bug 修复记录
1. 鼠标位置缓存（(0,0) 导致菜单在左上角）
2. 多显示器坐标偏移（窗口偏移 vs 屏幕坐标）
3. 绘制性能（全量重绘→增量更新→30fps 全量重绘）
4. F12→鼠标侧键→F12 切换
5. inputs 库兼容性→pygame
6. DualSense 蓝牙 SDL 不读信号→跳过
7. 三元运算符优先级导致摇杆永远回中
8. 关闭时守护线程 I/O 锁冲突

## 关键决策
- D-004（多按键分路由 + 双向反馈）在本次 session 中已验证
- 舍弃 inputs 库改用 pygame
- 混合使用 F12 + 手柄（F12 作为备用）

## 遗留问题
- [ ] ESP32 到货后验证固件烧录
- [ ] PC 端 BLEInputProvider 需要实现（已预留接口）
- [ ] 手柄摇杆灵敏度可能需要用户调试
- [ ] IMU 互补滤波参数 α 需要实机调试

## 文件统计
```
根目录:
  DEVELOPMENT_FRAMEWORK.md  (~820行)
  DECISION_LOG.md           (~120行)
  SESSION_STATE.md          (~80行)
  HARDWARE_SHOPPING_LIST.md (~200行)

client-v1/ 软件模拟:
  ~15 个源文件，约 2000 行代码
  main.py, main_gamepad.py, overlay.py, gamepad.py
  actions.py, mapper.py, engine.py, protocol.py, config.py
  tools/gamepad_test.py

firmware/ 固件:
  ~11 个源文件，约 700 行代码
  firmware.ino + 5 个模块 (ble/mpu6050/filter/buttons/feedback)
```
