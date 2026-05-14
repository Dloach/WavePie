# 项目状态

> 最后更新: 2026-05-14
> 每次操作后更新。AI 下次启动时首先读取本文件以快速恢复上下文。

---

## 当前版本

**client-v1 PC 客户端 — 托盘应用 + 配置编辑器 ✅**
**ESP32 固件 — 已编写，待硬件到货联调 ⏳**
**项目名: WavePie** (https://github.com/Dloach/WavePie)

## 已完成

### 桌面应用增强（本次 session）
- [x] 系统托盘图标（pystray，双击/右键→设置）
- [x] 配置编辑器 GUI — 菜单项 / 直接动作（手柄按键绑定） / 手势参数
- [x] 动态参数面板 — key / key_combo / macro / script / log 自动切换
- [x] 键盘录制（pynput VK 码识别，支持 Ctrl+Shift+Z）
- [x] 宏编辑弹窗 + 脚本文件选择器
- [x] 保存 toast + 自动关闭窗口
- [x] ESC 不再退出程序
- [x] 动作执行统一入口 `_do_action()` — 圆形菜单和手柄走同一条路
- [x] Enum 比较 bug 修复（RouteAction.DIRECT 而非 "direct" 字符串）
- [x] 移除滚轮触发
- [x] PyInstaller 单文件 exe（40MB，零安装零残留）

### 框架 & 文档
- [x] `DEVELOPMENT_FRAMEWORK.md` — 宪法级开发框架
- [x] `DECISION_LOG.md` — 架构决策记录
- [x] `SESSION_STATE.md` — 状态追踪
- [x] `.devlog/` — session 操作日志
- [x] `HARDWARE_SHOPPING_LIST.md` — 硬件采购清单

### 客户端代码
- [x] HAL 接口（InputEvent / InputProvider / DeviceFeedback）
- [x] MouseInputProvider（鼠标模拟输入）
- [x] ActionMapper 路由层（Overlay / 直接执行，含 trigger 索引）
- [x] GestureEngine 手势引擎
- [x] OverlayUI 径向菜单（12项，大环480-800px，中心透明）
- [x] ActionExecutor 跨平台键盘模拟（key / key_combo / macro / script）
- [x] pynput 全局热键（F12 按住/松开）
- [x] 手柄全按键轮询 + 直接动作触发
- [x] 配置驱动（config.yaml，含 trigger 字段）

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
- [ ] **日常使用体验打磨**（快捷键自定义、易用性）

## 下次启动流程

```
1. 读取 DEVELOPMENT_FRAMEWORK.md
2. 读取 DECISION_LOG.md（特别是 D-003/D-004）
3. 读取本文件 SESSION_STATE.md
4. 读取 .devlog/ 最新日志
5. 读取 firmware/README.md
6. 输出"上下文就绪"确认
```
