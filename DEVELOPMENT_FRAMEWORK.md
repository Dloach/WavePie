# 蓝牙体感控制器 — 开发框架文档

> 本文档是项目的**宪法级文件**。每次新版本开发前，AI 必须首先阅读本文档。
> 所有决策不得与本文档的设计原则冲突。如需修改本文档本身，必须记录在案并说明理由。

---

## 目录

1. [项目概览](#1-项目概览)
2. [目录结构约定](#2-目录结构约定)
3. [工作流程与 AI 启动协议](#3-工作流程与-ai-启动协议)
4. [版本路线图](#4-版本路线图)
5. [硬件抽象层设计 (HAL)](#5-硬件抽象层设计-hal)
6. [核心技术栈与储备清单](#6-核心技术栈与储备清单)
7. [代码规范与项目约定](#7-代码规范与项目约定)
8. [AI 协作连续性协议](#8-ai-协作连续性协议)
9. [附录：关键文件索引](#9-附录关键文件索引)

---

## 1. 项目概览

### 一句话定义

> 一个通过手持蓝牙设备的多按键 + 体感摆动 + 滚轮，控制计算机弹出选择菜单或直接执行操作的软硬件双向交互系统。支持软件向设备发送状态提示信号（LED、蜂鸣等）。

### 系统架构

```
┌───────────────────────────────────────────────────────┐
│                    输入层 (Input Layer)                 │
│  ┌───────────┐  ┌──────────────────────────────────┐  │
│  │ 鼠标模拟   │  │          BLE 设备                 │  │
│  │ (Phase 1) │  │  ┌───┐ ┌───┐ ┌───┐ ┌─────────┐  │  │
│  └─────┬─────┘  │  │B0│ │B1│ │B2│ │IMU+滚轮 │  │  │
│        │        │  │主 │ │副 │ │副 │ │ (体感)  │  │  │
│        │        │  └─┬─┘ └─┬─┘ └─┬─┘ └────┬────┘  │  │
│        │        │    └──┬───┴──┬──┘        │       │  │
│        └─────┬──┘       │      │           │       │  │
│              │          └──┬───┴───┬───────┘       │  │
│              ▼             ▼       ▼               │  │
│   ┌──────────────────────────────┐                 │  │
│   │      InputProvider           │  ← HAL 抽象     │  │
│   │  InputEvent:                 │    统一事件流   │  │
│   │   按键(button_id: uint)      │                 │  │
│   │   姿态(roll/pitch/yaw)       │                 │  │
│   │   滚轮(scroll_delta)         │                 │  │
│   └──────────────┬───────────────┘                 │  │
│                  │                                 │  │
│   ┌──────────────▼───────────────┐                 │  │
│   │     DeviceFeedback           │  ← 软件 → 硬件  │  │
│   │  OutputChannel:              │    反馈通道     │  │
│   │   信号(LED 状态/颜色/闪烁)   │                 │  │
│   │   提示(蜂鸣/震动)            │                 │  │
│   └──────────────────────────────┘                 │  │
└───────────────────────────┬─────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────┐
│                  路由层 (ActionMapper)                  │
│                                                       │
│  ── 根据 button_id + 配置，决定事件流向 ──              │
│                                                       │
│   button_0 (主按钮) ─→ Overlay 模式 ─→ 手势引擎 + UI   │
│   button_1..N        ─→ 直接行动 ─→ ActionExecutor     │
│   scroll_wheel       ─→ 预设动作 ─→ ActionExecutor     │
│                                                       │
│   所有映射关系通过 config.yaml 可配置                   │
└───────────────────────────┬───────────────────────────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
       ┌────────────┐ ┌──────────┐ ┌──────────────┐
       │ 手势引擎    │ │ Overlay  │ │ 直接动作执行  │
       │姿态→光标    │ │ 浮动菜单  │ │ 快捷键/宏/   │
       │滤波/灵敏度 │ │ 高亮选择  │ │ 滚轮映射     │
       └─────┬──────┘ └────┬─────┘ └──────┬───────┘
             └───────┬─────┘              │
                     ▼                    │
              ┌──────────────┐           │
              │ 动作执行器    │◄──────────┘
              │ ActionExecutor│
              └──────────────┘
```

### 交互流程

设备上有多种按键，不同按键走不同路径：

```
【路径 A: 主按钮 → Overlay 选择（体感交互）】

① 按下主按钮 ──→ ② Overlay 弹出 ──→ ③ 摆动设备移动高亮
                                              │
                  ⑧ 执行选中功能 ◄─ ⑦ 松开按钮

【路径 B: 副键 / 滚轮 → 直接执行（无 UI 干扰）】

① 按下副键 ──→ ② 直接执行映射的快捷键 / 宏

① 拨动滚轮 ──→ ② 直接触发映射的功能（如音量增减）

【路径 C: 软件 → 硬件反馈】

① 设备连接成功 ──→ 软件发送「已连接」→ LED 亮绿灯
① 任务执行失败 ──→ 软件发送「失败」  → LED 闪烁红灯
```

**核心原则：路径 A 和路径 B 共享同一个 ActionExecutor，只是触发方式不同。**

---

## 2. 目录结构约定

```
project-root/
│
├── DEVELOPMENT_FRAMEWORK.md    # ◄ 本文档（宪法）
├── DECISION_LOG.md             # 架构决策记录（增量追加）
├── SESSION_STATE.md            # 当前版本状态（每次操作后更新）
├── TECH_PREP.md                # 技术储备笔记（可选，补充学习用）
│
├── .devlog/                    # 操作日志目录
│   ├── 2024-01-01_v1-init.md
│   ├── 2024-01-15_v1-overlay-done.md
│   └── ...                     # 每次关键操作留一条日志
│
├── v1/                         # 版本 1：软件模拟原型
│   ├── README.md               # 该版本的说明、启动方式
│   └── src/                    # 源码（按技术栈组织）
│
├── v2/                         # 版本 2：加入 BLE 通信层
│   ├── README.md
│   └── src/
│
├── firmware/                   # ESP32 固件源码
│
└── ...                         # 后续版本依此类推
```

### 版本目录规则

| 规则 | 说明 |
|------|------|
| **每个版本一个独立子目录** | `v1/` `v2/` …，彼此独立，不互相依赖 |
| **每版本有自己的 README** | 说明该版本的用途、启动方式、依赖、已知限制 |
| **向下兼容不做强制要求** | 每个版本是阶段快照，不是升级包 |
| **公共文档在根目录** | `DEVELOPMENT_FRAMEWORK.md` 对所有版本生效 |
| **跨版本共享的库** | 成熟后提取到 `shared/`（仅当确实需要时） |

---

## 3. 工作流程与 AI 启动协议

### 3.1 每次开始一个新版本 / 新操作前

AI **必须**执行以下启动流程，缺一不可：

```
┌──────────────────────────────────────────────┐
│              启动检查清单                       │
├──────────────────────────────────────────────┤
│  □ 1. 读取 DEVELOPMENT_FRAMEWORK.md           │
│  □ 2. 读取 DECISION_LOG.md（了解历史决策）       │
│  □ 3. 读取 SESSION_STATE.md（了解当前状态）      │
│  □ 4. 读取 .devlog/ 中最新的操作日志             │
│  □ 5. 读取当前版本目录的 README.md              │
│  □ 6. 输出"上下文就绪确认"到日志                 │
└──────────────────────────────────────────────┘
```

**AI 在完成上述读取后**，应在回复开头输出一条确认语句：

> ✅ 上下文就绪
> - 已读取框架文档：DEVELOPMENT_FRAMEWORK.md
> - 最新决策：DECISION_LOG.md 第 N 条
> - 当前状态：SESSION_STATE.md（Phase X / Step Y）
> - 上次操作：.devlog/xxx.md

### 3.2 每次关键操作后

AI **必须**执行以下收尾流程：

```
┌──────────────────────────────────────────────┐
│              操作收尾清单                       │
├──────────────────────────────────────────────┤
│  □ 1. 在 .devlog/ 中追加一条操作日志            │
│      文件名格式：YYYY-MM-DD_action-summary.md  │
│  □ 2. 更新 SESSION_STATE.md                   │
│      记录当前进展、遗留问题、下次待办             │
│  □ 3. 如果涉及架构决策，追加到 DECISION_LOG.md  │
│  □ 4. 更新当前版本 README.md（如果有变更）       │
└──────────────────────────────────────────────┘
```

### 3.3 日志格式规范

每条 `.devlog/` 日志文件结构如下：

```markdown
# YYYY-MM-DD: 简短标题

## 操作人
AI / 手动

## 涉及版本
vX

## 做了什么
- 要点 1
- 要点 2

## 关键决策（如果有）
- 决策内容
- 理由

## 遗留问题 / 待办
- [ ] 问题 1

## 备注
其他需要记录的信息
```

---

## 4. 版本路线图

### Phase 1 — 软件模拟原型（当前阶段 → v1）

| 步骤 | 内容 | 交付物 |
|------|------|--------|
| 1.0 | 技术选型 + 环境搭建 | 项目骨架、依赖安装脚本 |
| 1.1 | 核心数据结构定义 | InputEvent、ActionDef、DeviceFeedback 等类型 |
| 1.2 | 鼠标输入模拟层 (MouseInputProvider) | 多按键 + 滚轮 → InputEvent 事件流 |
| 1.3 | ActionMapper 路由层 | 按键 → 行为映射引擎（config 驱动） |
| 1.4 | 手势引擎 | 灵敏度、死区、加速度、光标映射 |
| 1.5 | 浮动选择 UI | 透明覆盖层、选项列表、高亮移动 |
| 1.6 | 动作执行器 | 键盘模拟 / 宏执行 / 滚轮动作 / 插件机制 |
| 1.7 | 端到端集成与调试 | 多键 + 体感 + 直接动作全链路跑通 |

### Phase 2 — BLE 通信层（v2）

| 步骤 | 内容 | 交付物 |
|------|------|--------|
| 2.0 | BLE 协议设计 | GATT 服务定义（含多按键、IMU、滚轮、反馈通道） |
| 2.1 | BLE 主机端库集成 | Python `bleak` / Rust 等 |
| 2.2 | BLEInputProvider 实现 | 实现 InputProvider + OutputChannel 接口 |
| 2.3 | DeviceFeedbackOverBLE 实现 | 软件 → 设备通知（LED / 蜂鸣 / 状态码） |
| 2.4 | 模拟 → BLE 切换机制 | 配置切换，无需改业务代码 |

### Phase 3 — 真实硬件接入

| 步骤 | 内容 | 交付物 |
|------|------|--------|
| 3.0 | 硬件 BOM 与接线图 | 物料清单、电路图 |
| 3.1 | 固件开发 | ESP32 BLE GATT + IMU 滤波 |
| 3.2 | 固件 ↔ 主机联调 | 数据流验证 |
| 3.3 | 整机测试与手感调优 | 延迟、灵敏度、人体工学 |

### 后续版本方向（未定）

- v4: 图形化配置面板（灵敏度 / 按键映射 / 菜单项 / 反馈规则）
- v5: 宏录制与回放编辑器
- v6: 复杂反馈规则引擎（条件/定时/优先级）
- v7: 多设备支持 / 多 profile 热切换

---

## 5. 硬件抽象层设计 (HAL)

这是**整个项目最关键的设计决策**。目的：
1. **Phase 1 用鼠标模拟，Phase 3 无缝切换到真实设备，业务代码零修改。**
2. **支持多按键 + 滚轮 + 体感，其中某些按键直接执行、某些走 Overlay 选择。**
3. **支持软件向设备发送反馈信号。**

### 5.1 核心接口：InputEvent（事件模型）

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import AsyncIterator, Optional

class EventType(Enum):
    BUTTON_DOWN = "button_down"      # 某键按下
    BUTTON_UP   = "button_up"        # 某键松开
    MOTION      = "motion"           # IMU 姿态变化
    SCROLL      = "scroll"           # 滚轮转动
    IDLE        = "idle"             # 无操作（心跳）

class ButtonRole(IntEnum):
    """硬件上每个按键的逻辑角色。
    
    v1 模拟阶段用 keyboard key 映射；
    真实硬件阶段用 BLE button_id。
    """
    MAIN       = 0    # 主按钮：触发 Overlay 体感选择
    AUX_1      = 1    # 副键1：可配置直接动作
    AUX_2      = 2    # 副键2
    AUX_3      = 3    # 副键3
    # 可扩展 AUX_N ...

@dataclass
class InputEvent:
    type: EventType
    timestamp: float               # monotonic 时间戳

    # ── 按键相关（type=BUTTON_DOWN / BUTTON_UP 时有效）──
    button_id: int = 0             # 哪一个按键（对应 ButtonRole 或 raw ID）
    is_long_press: bool = False    # 是否为长按（预留：可分配不同行为）

    # ── 姿态数据（type=MOTION 时有效）──
    roll: float = 0.0              # Z轴旋转（左右摆） -180 ~ 180
    pitch: float = 0.0             # Y轴旋转（前后倾） -180 ~ 180
    yaw: float = 0.0               # X轴旋转（水平转） -180 ~ 180

    # ── 滚轮数据（type=SCROLL 时有效）──
    scroll_delta: int = 0          # 滚轮增量：+1 顺时针，-1 逆时针

    # ── 派生数据（由下游引擎填充，不一定来自硬件）──
    delta_x: float = 0.0           # 光标X偏移（归一化）
    delta_y: float = 0.0           # 光标Y偏移（归一化）
    velocity: float = 0.0          # 摆动速度
```

### 5.2 核心接口：InputProvider（事件流 + 反馈通道）

```python
class InputProvider(ABC):
    """所有输入源的统一抽象接口。

    🌐 双向：输入端通过 read_events()，输出端通过 feedback。
    """

    # ── 输入端 ──

    @abstractmethod
    async def start(self) -> None:
        """启动输入源（打开设备 / 监听端口等）。"""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """停止输入源，释放资源。"""
        ...

    @abstractmethod
    def read_events(self) -> AsyncIterator[InputEvent]:
        """异步遍历输入事件流。

        调用方通过 `async for event in provider.read_events()` 消费。
        """
        ...

    @abstractmethod
    async def calibrate(self) -> None:
        """校准（IMU 归零 / 灵敏度设定等）。"""
        ...

    # ── 输出端（软件 → 设备）──

    @property
    @abstractmethod
    def feedback(self) -> "DeviceFeedback":
        """获取反馈通道。如果输入源不支持反馈（如纯 mouse），返回 NoopFeedback。"""
        ...
```

### 5.3 核心接口：DeviceFeedback（软件 → 硬件反馈）

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class LedColor(Enum):
    OFF    = "off"
    RED    = "red"
    GREEN  = "green"
    BLUE   = "blue"
    YELLOW = "yellow"

class LedPattern(Enum):
    SOLID      = "solid"       # 常亮
    SLOW_BLINK = "slow_blink"  # 慢闪（~1Hz）
    FAST_BLINK = "fast_blink"  # 快闪（~3Hz）
    PULSE      = "pulse"       # 呼吸

@dataclass
class FeedbackCommand:
    """一次反馈指令。可同时设置多个信号。"""
    led_color: Optional[LedColor] = None
    led_pattern: Optional[LedPattern] = None
    buzzer_on: bool = False          # 蜂鸣器
    vibration_ms: int = 0            # 震动时长（ms，0=不震）
    status_code: int = 0             # 状态码（0=正常，非0=错误码）

class DeviceFeedback(ABC):
    """软件 → 设备反馈通道。

    使用场景：
      - 设备连接成功 → LED 常亮绿灯
      - 宏执行失败   → LED 快闪红灯 + 一声蜂鸣
      - 切换 profile  → LED 黄灯呼吸 + 短震

    模拟阶段（NoopFeedback）所有调用为 No-op。
    """

    @abstractmethod
    async def send(self, command: FeedbackCommand) -> None:
        """发送反馈指令到设备。"""
        ...

    @abstractmethod
    async def is_connected(self) -> bool:
        """反馈通道是否可用（设备在线）。"""
        ...


class NoopFeedback(DeviceFeedback):
    """模拟/无设备时的空反馈实现，不实际发送任何指令。"""

    async def send(self, command: FeedbackCommand) -> None:
        pass  # 模拟阶段直接忽略

    async def is_connected(self) -> bool:
        return False
```

### 5.4 核心接口：ActionMapper（路由层）

```python
from dataclasses import dataclass
from enum import Enum
from typing import Union

class RouteAction(Enum):
    OVERLAY   = "overlay"        # 进入 Overlay 选择模式
    DIRECT    = "direct"         # 直接执行映射的 action
    SCROLL    = "scroll_map"     # 滚轮 → 预设功能（音量/滚动等）

@dataclass
class ButtonActionMap:
    """将硬件按键映射到软件行为。"""
    button_id: int               # 硬件按键 ID
    route: RouteAction           # 路由类型
    # 以下是 route=DIRECT 时的具体动作定义
    action_type: str = ""        # "key_combo" | "macro" | "script"
    action_payload: str = ""     # 快捷键组合 或 宏名称 或 脚本路径
    long_press_action_type: str = ""   # 长按触发不同动作（预留）
    long_press_payload: str = ""

@dataclass
class ScrollMap:
    """滚轮映射。"""
    up_action_type: str    # 滚轮向上 → 什么动作
    up_payload: str
    down_action_type: str  # 滚轮向下 → 什么动作
    down_payload: str

# ── 配置示例（config.yaml）──
#
# buttons:
#   - button_id: 0           # 主按钮
#     route: overlay
#   - button_id: 1           # 副键1
#     route: direct
#     action_type: key_combo
#     action_payload: "ctrl+shift+s"   # 比如截图
#   - button_id: 2           # 副键2
#     route: direct
#     action_type: macro
#     action_payload: "paste_markdown"
#
# scroll:
#   up:
#     action_type: key_combo
#     action_payload: "volume_up"
#   down:
#     action_type: key_combo
#     action_payload: "volume_down"
#
# feedback_rules:            # 反馈规则（v2+）
#   on_connect: { led: green, pattern: solid }
#   on_action_fail: { led: red, pattern: fast_blink, buzzer: true }
```

### 5.5 两个实现

```
InputProvider (抽象接口)
    │
    ├── MouseInputProvider         ← Phase 1 实现
    │     鼠标左键 → 主按钮 (button_id=0)
    │     鼠标右键 → 副键1  (button_id=1)
    │     键盘F1~F4 → 副键2~5
    │     滚轮     → SCROLL 事件
    │     鼠标移动 → MOTION 事件
    │     feedback → NoopFeedback (空实现)
    │
    └── BLEInputProvider           ← Phase 2/3 实现
          接收蓝牙设备多按键 + IMU + 滚轮数据
          归一化为相同 InputEvent 格式
          feedback → 写 BLE 特征值 (LED/蜂鸣)
```

### 5.6 切换机制

```python
# 通过配置文件切换，绝不硬编码

# config.yaml
input:
  provider: "mouse"   # "mouse" | "ble"
  # mouse 配置
  mouse:
    sensitivity: 1.0
    # 模拟按键映射
    button_map:
      main_button: "mouse_left"      # button_id=0
      aux_buttons: ["mouse_right", "f1", "f2", "f3"]  # button_id 1..4
  # ble 配置（仅 provider=ble 时生效）
  ble:
    device_address: "xx:xx:xx:xx:xx:xx"
    reconnect: true
```

**切换不涉及任何业务代码修改。** 所有业务代码只依赖 `InputProvider` 和 `DeviceFeedback` 接口。

### 5.7 预留的固件通信协议

```
BLE GATT Service:
  UUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (自定义 128-bit)

  ── 设备 → 软件（Notification / Read）──

  Characteristic - Buttons:
    UUID: xxxx...0001
    Format: N bytes 位掩码 + 事件标记
    Byte 0: button_states 位掩码 (bit0=主按钮, bit1..7=副键)
    Byte 1: event_flags (bit0=长按, bit1=双击, 预留)
    Notify: true

  Characteristic - IMU:
    UUID: xxxx...0002
    Format: 6×float32 (accel_x/y/z, gyro_x/y/z) 或 4×float32 (quaternion)
    Notify: true (50-100Hz)

  Characteristic - Scroll:
    UUID: xxxx...0003
    Format: 1×int8 (delta: +1 顺时针, -1 逆时针)
    Notify: true

  ── 软件 → 设备（Write）──

  Characteristic - Feedback:
    UUID: xxxx...0010
    Format: 4 bytes
    Byte 0: LED 颜色 + 模式 (高4位=颜色枚举, 低4位=模式枚举)
    Byte 1: 蜂鸣/震动标志 (bit0=蜂鸣, bit1=震动)
    Byte 2: 状态码
    Byte 3: 预留
    Write: true
```

> **目前不需要实现 BLE 端。** Phase 1 只需设计好接口，Phase 2/3 再填充实现。

---

## 6. 核心技术栈与储备清单

### 6.1 推荐技术栈

| 层 | 推荐方案 | 备选方案 | 选择理由 |
|----|---------|---------|---------|
| **BLE 主机通信** | Python `bleak` | Rust `btleplug` | 开发速度快，迭代成本低 |
| **手势引擎** | Python 原生 | NumPy 加速 | 初期算法简单，Python 足够 |
| **浮动 UI** | Tauri (Rust + HTML/JS) | Electron / PyQt / tkinter | 跨平台一致性好，内存占用小 |
| **键盘模拟** | `pyautogui` (Win/Mac/Linux) | `pynput` / AutoHotkey | 跨平台 API 统一 |
| **宏录制** | 自定义轻量 DSL | Python 脚本 | 灵活可控 |
| **固件** | Arduino / ESP-IDF (C++) | MicroPython | BLE 库成熟，实时性好 |
| **配置管理** | YAML + `pydantic` | JSON + dataclass | 类型安全，可校验 |
| **日志** | `structlog` / 纯文件追加 | `logging` 模块 | 结构清晰，便于 AI 解析 |
| **反馈通道** | BLE Write (硬件) / Noop (模拟) | 串口/hidraw | 由 HAL 抽象，切换透明 |

### 6.2 技术储备清单

以下是你（或 AI）在进入对应阶段前需要熟悉的内容：

| 技术 | 需要掌握的程度 | 对应阶段 |
|------|---------------|---------|
| Python 异步编程 (`asyncio`) | 能写出稳定的 `async/await` 事件循环 | Phase 1 |
| `bleak` 库基本用法 | 能扫描、连接、订阅 BLE notification + Write | Phase 2 |
| Tauri / Electron 基本概念 | 能创建无边框窗口、透明背景、事件通信 | Phase 1 |
| IMU 传感器基础 | 加速度计/陀螺仪原理、互补滤波 | Phase 3 |
| ESP32 Arduino BLE | GATT 创建（多 characteristic）、notification + read 回调 | Phase 3 |
| 姿态解算 | Madgwick / Mahony 滤波算法（可选） | Phase 3 |
| BLE Characteristic Write | 软件端写特征值控制 LED/蜂鸣等 | Phase 2-3 |

> 不需要提前全部掌握。每个阶段开始前储备对应的技术即可。

---

## 7. 代码规范与项目约定

### 7.1 通用原则

- **可读性优先于"巧妙"**：如果一段逻辑需要注释解释，说明它不够清晰
- **防御性编程**：所有外部输入做类型校验，不信任数据源
- **测试意识**：核心算法（手势映射、事件处理）应有单元测试
- **渐进式优化**：先跑通，再调优，不提前做性能优化

### 7.2 命名约定

| 类别 | 约定 | 示例 |
|------|------|------|
| Python 包/模块 | 小写蛇形 | `gesture_engine.py` |
| Python 类 | 大驼峰 | `MouseInputProvider` |
| Python 函数/方法 | 小写蛇形 | `read_events()`, `map_to_cursor()` |
| Python 常量 | 全大写蛇形 | `DEFAULT_SENSITIVITY = 1.0` |
| Python 类型别名 | 大驼峰 | `InputEventDict` |
| TypeScript (UI) | 标准 TS 约定 | `camelCase` 变量, `PascalCase` 组件 |
| 固件 C/C++ | 标准 Arduino 风格 | `snake_case` 函数, `kConst` 常量 |
| 配置文件键 | 小写蛇形 | `input.provider`, `gesture.sensitivity` |
| Git 分支 | `vX/feature-name` | `v1/overlay-ui` |
| 提交信息 | 中文简短说明 | `v1: 完成鼠标输入提供层` |

### 7.3 文件结构约定

每个版本子目录内推荐结构：

```
vN/
├── README.md
├── requirements.txt        # Python 依赖
├── config.yaml             # 配置文件
├── src/                    # 源码
│   ├── main.py             # 入口
│   ├── input/              # 输入层（HAL）
│   │   ├── __init__.py
│   │   ├── protocol.py     # InputEvent, InputProvider, DeviceFeedback 接口
│   │   ├── feedback.py     # NoopFeedback, FeedbackCommand 定义
│   │   └── mouse.py        # MouseInputProvider (含多按键映射)
│   ├── gesture/            # 手势引擎
│   │   ├── __init__.py
│   │   └── engine.py
│   ├── ui/                 # UI（如果有前端代码）
│   │   └── ...
│   ├── mapper/             # 动作路由
│   │   ├── __init__.py
│   │   ├── mapper.py       # ActionMapper (按键→Route 分发)
│   │   └── config_loader.py # 映射配置加载
│   ├── executor/           # 动作执行
│   │   ├── __init__.py
│   │   └── actions.py
│   └── utils/              # 工具函数
│       ├── __init__.py
│       ├── config.py
│       └── log.py
├── tests/                  # 测试
│   └── test_gesture.py
└── assets/                 # 资源文件
```

### 7.4 注释规范

```python
# 好注释：解释"为什么"而不是"是什么"

# 不好的注释：
x += 1  # x 加 1

# 好的注释：
# IMU 原始数据有直流偏置，减去静止时的均值做归零
x += 1
```

```python
# 公共函数/类必须有 docstring
def map_to_cursor(roll: float, sensitivity: float = 1.0) -> float:
    """将体感旋转角映射为光标位移量。
    
    Args:
        roll: Z轴旋转角度（度）
        sensitivity: 灵敏度倍数
        
    Returns:
        归一化的位移量（-1.0 ~ 1.0）
    """
```

### 7.5 Git 提交约定

```
v1: 完成鼠标输入提供层
- 实现 MouseInputProvider
- 实现 InputEvent 数据类
- 添加配置读取支持
```

风格：`vN: 一句话概括`，换行后列表详述。

---

## 8. AI 协作连续性协议

这是**确保项目维护数月后 AI 不走偏**的核心机制。原则：**把一切需要记住的东西写进文件，不依赖 AI 的上下文窗口。**

### 8.1 三个核心文件

#### ① `DECISION_LOG.md` — 架构决策记录

每次做出架构、技术、设计上的决策时，追加一条记录。

```markdown
## D-001 | YYYY-MM-DD | 选择 Tauri 作为 UI 框架

**背景：** Phase 1 需要跨平台透明覆盖窗口
**方案对比：**
- Electron：内存占用大（~120MB），打包体积大
- Tauri：内存占用小（~10MB），Rust 后端性能好
- tkinter：跨平台透明窗口支持不一致
- PyQt：商业许可问题，打包复杂
**决策：** 选用 Tauri
**理由：** 最小化资源占用，Rust 后端在未来 BLE 集成中也有用
**后续影响：** UI 和主逻辑之间需通过 IPC 通信
```

#### ② `SESSION_STATE.md` — 当前状态文件

每次操作后更新。AI 下次启动时用这个文件快速恢复上下文。

```markdown
# 项目状态 (更新于 YYYY-MM-DD HH:MM)

## 当前版本
v1 — 软件模拟原型

## 已完成
- [x] 项目骨架搭建
- [x] MouseInputProvider 实现
- [ ] 手势引擎 (进行中)
- [ ] 浮动选择 UI
- [ ] 动作执行器
- [ ] 端到端集成

## 上次操作
手势引擎基本框架完成，死区滤波已实现，光标映射公式待调试

## 当前的已知问题
1. 灵敏度参数还未经过真实测试，默认值可能偏高
2. 鼠标模拟的"归中"手感不自然

## 下次待办
1. 实现光标映射（将滤波后的角度值转换为屏幕位移）
2. 编写单元测试验证手势映射公式

## 近期待办事项
- 选定 Tauri 版本并搭建 UI 项目骨架
```

#### ③ `.devlog/*.md` — 操作日志

每次关键操作留下一条日志（见 3.3 节格式）。

### 8.2 当 AI 发现矛盾时

```
如果 AI 发现当前操作与 DECISION_LOG.md 中某条历史决策矛盾：
  → 暂停执行
  → 在回复中明确指出矛盾：
     "当前方案与 D-003 冲突：D-003 决定采用 X，而当前方案在用 Y"
     "建议：A) 推翻旧决策并更新 DECISION_LOG / B) 调整当前方案"
  → 等待开发者裁决
```

### 8.3 "走歪"的预防机制

| 风险 | 预防措施 |
|------|---------|
| AI 忘记整体架构 | 每次启动检查清单强制重读框架文档 |
| AI 引入不一致的风格 | 代码规范（第 7 节）作为硬约束 |
| AI 做出与历史决策矛盾的方案 | DECISION_LOG 提供"记忆"，矛盾时暂停 |
| AI 偏离项目目标 | 项目概览（第 1 节）锚定核心定位 |
| 多个版本间代码风格不一致 | 各版本 README 说明本版本的约定 |
| AI 优化过度偏离原型目标 | Version 路线图（第 4 节）兜住 scope |

### 8.4 长期开发的节奏建议

```
1. 每次启动 ≥1 小时的开发 session
   ── 执行启动检查清单（5 分钟）
   ── 明确本次目标（写入 SESSION_STATE）
   ── 开发（核心时间）
   ── 执行收尾清单（5-10 分钟）
   
2. 每次收尾时问自己：
   ── "下次 AI 打开这个项目，只看文件能完全理解进展吗？"
   ── 如果不能，说明日志写的不够 → 补充
```

---

## 9. 附录：关键文件索引

| 文件 | 用途 | 谁维护 |
|------|------|--------|
| `DEVELOPMENT_FRAMEWORK.md` | 宪法级框架文档，长期不变 | 开发者（==本文==） |
| `DECISION_LOG.md` | 架构决策历史，持续追加 | AI + 开发者 |
| `SESSION_STATE.md` | 当前版本状态，每次操作后更新 | AI |
| `.devlog/` 目录 | 操作日志，按日期命名 | AI |
| `vN/README.md` | 每个版本的说明 | AI |
| `vN/config.yaml` | 每个版本的配置 | AI |
| `TECH_PREP.md` | 技术储备笔记（可选） | 开发者 |

---

> **最后一条规则：** 当你不确定该怎么做时，把问题写进 SESSION_STATE.md 的"已知问题"里，然后继续做确定的部分。停滞比做错更浪费。
