# v1 — 软件模拟原型

> 目标：纯软件环境验证体感控制交互逻辑，零硬件成本

## 当前状态

✅ **全部完成** — 键盘版 + 手柄版 + 12项径向菜单

## 启动方式

```bash
cd client-v1
pip install -r requirements.txt
python -m src.main          # F12 键盘版
python -m src.main_gamepad  # 手柄版（同时支持F12备用）
```

## 交互方式

### 键盘版（`python -m src.main`）

| 操作 | 功能 |
|------|------|
| **按住 F12** | 在屏幕中央弹出 12 项径向菜单 |
| **移动鼠标** | 指针连线从圆心指向鼠标，扇区高亮跟随方向 |
| **松开 F12** | 执行选中项 |
| **Esc** | 取消 / 退出 |
| **滚轮** | 音量控制 |

### 手柄版（`python -m src.main_gamepad`）

| 操作 | 功能 |
|------|------|
| **按住 L2 扳机** | 激活径向菜单 |
| **左摇杆** | 方向选择扇区 |
| **松开 L2** | 执行选中项 |
| **F12** | 备用触发 |
| **Esc** | 取消 / 退出 |

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 核心语言 | Python 3.12 | 异步事件循环 |
| UI | tkinter | 全屏透明覆盖层 |
| 全局热键 | pynput | 键盘/鼠标全局监听 |
| 手柄驱动 | pygame | XInput / DirectInput |
| 键盘模拟 | ctypes / PowerShell | Win32 API keybd_event |
| 配置 | YAML | 12 项可配置菜单 |
| 音量 | WM_APPCOMMAND | 系统级广播 |

## 项目文件结构

```
client-v1/
├── config.yaml              # 菜单项/按键映射/灵敏度配置
├── src/
│   ├── main.py              # 键盘版入口（F12）
│   ├── main_gamepad.py      # 手柄版入口（L2+摇杆）
│   ├── input/
│   │   ├── protocol.py      # HAL 接口定义
│   │   ├── mouse.py         # 鼠标输入模拟
│   │   └── gamepad.py       # 手柄输入驱动
│   ├── mapper/mapper.py     # 按键→行为路由
│   ├── gesture/engine.py    # 手势引擎
│   ├── ui/overlay.py        # 径向菜单 UI
│   ├── executor/actions.py  # 键盘模拟/宏/脚本
│   └── utils/config.py      # 配置加载器
└── tools/
    └── gamepad_test.py      # 手柄信号诊断
```

## 硬件准备

硬件采购清单见根目录 `HARDWARE_SHOPPING_LIST.md`。
固件代码在 `firmware/`，等待 ESP32+MPU6050 到货后烧录联调。

## 模块结构

```
client-v1/
├── config.yaml              # 用户配置（按键映射、菜单项、灵敏度）
├── requirements.txt
├── src/
│   ├── main.py              # 入口，串联所有模块
│   ├── input/
│   │   ├── protocol.py      # InputEvent, InputProvider, DeviceFeedback 接口
│   │   ├── feedback.py      # NoopFeedback 空实现
│   │   └── mouse.py         # MouseInputProvider（Phase 1 鼠标模拟）
│   ├── mapper/
│   │   └── mapper.py        # ActionMapper（按键 → 行为路由）
│   ├── gesture/
│   │   └── engine.py        # GestureEngine（姿态→光标映射）
│   ├── ui/
│   │   └── overlay.py       # OverlayUI（tkinter 透明浮动菜单）
│   ├── executor/
│   │   └── actions.py       # ActionExecutor（键盘模拟 / 宏 / 脚本）
│   └── utils/
│       └── config.py        # 配置加载器
```

## 已知限制

- **鼠标模拟与真实体感的操控手感有本质差异** — 此版产出的算法参数在接入真实设备后需重新标定
- 透明穿透窗口仅在 Windows 上完全实现（`WS_EX_TRANSPARENT`），macOS/Linux 为基本功能
- 键盘模拟依赖平台工具（PowerShell / osascript / xdotool），部分环境可能受限
- 无 GUI 配置界面，修改 config.yaml 后需重启

## 下一步（Phase 1.7）

- 端到端启动测试，验证完整链路
- 调优手势引擎参数（死区、灵敏度）
- 丰富菜单示例配置
