# 项目状态

> 最后更新: 2024-12-17 深夜
> 每次操作后更新。AI 下次启动时首先读取本文件以快速恢复上下文。

---

## 当前版本

**client-v1 PC 客户端 — 托盘应用 + 配置编辑器 ✅**
**ESP32 固件 — 已编写，待硬件到货联调 ⏳**

## 已完成

### 桌面应用增强
- [x] 系统托盘图标（pystray，缩到右下角通知栏）
- [x] 配置编辑器 GUI（tkinter 可视化编辑菜单项/按键/滚轮）
- [x] 统一入口 app.py（F12 + 手柄 + 托盘合一）
- [x] PyInstaller 打包为单文件 exe（38MB，零安装零残留）
- [x] 默认配置改为真正的 key_combo 快捷键（不再只是 log）

### 框架 & 文档
- [x] `DEVELOPMENT_FRAMEWORK.md` — 宪法级开发框架
- [x] `DECISION_LOG.md` — 4 条架构决策记录
- [x] `SESSION_STATE.md` — 状态追踪
- [x] `HARDWARE_SHOPPING_LIST.md` — 硬件采购清单

### v1 软件模拟原型
- [x] HAL 接口（InputEvent / InputProvider / DeviceFeedback）
- [x] MouseInputProvider（鼠标模拟输入）
- [x] ActionMapper 路由层（Overlay / 直接执行）
- [x] GestureEngine 手势引擎
- [x] OverlayUI 径向菜单（12项，大环480-800px，中心透明）
- [x] ActionExecutor 跨平台键盘模拟
- [x] pynput 全局热键（F12 按住/松开）
- [x] 多显示器支持（虚拟桌面 + MonitorFromPoint）
- [x] 手柄支持（XInput / DualSense）
- [x] 配置驱动（config.yaml）
- [x] 滚轮音量控制

### ESP32 固件（已编写待测试）
- [x] BLE GATT 服务（按键/IMU/滚轮/反馈 4个特性）
- [x] MPU6050 I2C 驱动
- [x] 互补滤波姿态解算
- [x] 多按键去抖 + 长按检测
- [x] LED/蜂鸣器反馈控制

## 待办

- [ ] **ESP32 + MPU6050 到货** → 烧录固件 + 接线
- [ ] **PC 端 BLEInputProvider 实现**（v2 范围）
- [ ] **硬件 ↔ PC 联调**
- [ ] **手感调优**（灵敏度、死区、加速度曲线）
- [ ] **外壳 3D 打印**

## 本次 session 成果（12月17日）

1. 从零搭建完整软件模拟原型（F12+鼠标/手柄操控径向菜单）
2. 完成 PS5/XInput 双手柄支持
3. 完成硬件采购清单
4. 完成 ESP32 固件编写（等待硬件到货验证）

## 下次启动流程

```
1. 读取 DEVELOPMENT_FRAMEWORK.md
2. 读取 DECISION_LOG.md（特别是 D-003/D-004）
3. 读取本文件 SESSION_STATE.md
4. 读取 .devlog/ 最新日志
5. 读取 firmware/README.md
6. 输出"上下文就绪"确认
```
