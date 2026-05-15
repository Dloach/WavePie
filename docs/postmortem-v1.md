# WavePie V1 → V2 经验总结

> 本文档记录 client-v1 开发过程中遇到的关键问题、根治方案以及
> V2 开发应避免的陷阱。开发 V2 前请完整阅读本文档。

---

## 1. 架构层面：哪些做对了

### ✅ HAL 接口抽象（InputProvider）
按配置切换输入源（mouse / ble / gamepad），上层代码零修改。
- `InputProvider` 抽象类定义 `read_events()` 异步流
- `InputEvent` 统一事件格式（MOTION / BUTTON_DOWN / BUTTON_UP）
- `DeviceFeedback` 接口解耦反馈通道

**V2 保留此模式，继续扩展。**

### ✅ 单一执行入口
```
触发源 → _do_action(type, payload) → ActionExecutor.execute()
```
圆形菜单、手柄按键、未来其他触发源都走同一条路，避免重复逻辑。

### ✅ ActionMapper 路由层
- `button_id` 索引 + `trigger` 字符串索引
- Overlay 模式 / Direct 模式分流
- config.yaml 驱动，不改代码

---

## 2. 关键 Bug 及根治方案

### 🐛 Enum vs 字符串比较（最致命）
```python
# ❌ 永远为 False —— RouteAction.DIRECT 是枚举，不是字符串
if br and br.route == "direct":

# ✅ 正确比较方式
if br and br.route == RouteAction.DIRECT:
```

**教训：** 项目中只要有一个 Enum 类型的字段，就**禁止**用字符串与之比较。所有 `route` 比较必须用 `RouteAction.XXX`。

**V2 检查清单：**
- [ ] 所有 route/type 比较用的是 Enum 成员
- [ ] 没有隐藏的 `x == "direct"` 或 `x == "overlay"` 字符串比较

### 🐛 Python 闭包捕获循环变量
```python
for b in buttons:
    tv = tk.StringVar(value=b.action_type)
    combo = ttk.Combobox(textvariable=tv)
    # ❌ cb 捕获的是变量 tv 本身，循环结束后 tv 指向最后一个
    def cb(*args):
        new_type = tv.get()  # 永远读到最后一个
    # ✅ 用默认参数固定当前迭代的值
    def cb(*args, tv=tv):
        new_type = tv.get()
```

**教训：** 在循环中定义回调函数时，所有要捕获的变量必须用**默认参数**固定。

**V2 检查清单：**
- [ ] 循环中创建的回调没有捕获外层变量
- [ ] 所有需要捕获的变量都用默认参数传入

### 🐛 tkinter 线程安全
```python
# ❌ 在后台线程建 Tk() + mainloop() → 事件全部异常
editor = ConfigEditor()
editor.root.mainloop()

# ✅ Toplevel 挂到主窗口，共享主线程事件循环
editor = ConfigEditor(master=self.ui.root)
```

**教训：** tkinter 不是线程安全的。所有窗口必须是主线程 `Tk()` 的子 `Toplevel`。非阻塞窗口不要调 `mainloop()`。

**V2 检查清单：**
- [ ] 所有 UI 窗口都是 `Toplevel(master)`，不是 `Tk()`
- [ ] 没有从后台线程直接操作 tkinter 控件
- [ ] 跨线程调度用 `root.after(0, callback)`

### 🐛 BLE 数据频率 vs tkinter 事件队列
```python
# ❌ 每个 IMU 事件都 root.after() → 队列爆炸
on_imu():
    self.ui.root.after(0, handler, evt)  # 66Hz

# ✅ 只存最新值，主线程轮询
on_imu():
    self.latest_roll = roll  # 轻量写
# 主线程每隔 33ms 轮询一次
root.after(33, poll):
    handler(latest_roll, latest_pitch)
```

**教训：** 高频数据（IMU 66Hz）不要每条都调 `root.after()`。用共享变量 + 主线程定期轮询。

**V2 检查清单：**
- [ ] 高频数据走共享变量 + 轮询，不走 per-event 调度
- [ ] 轮询频率 ≤ 30fps（人眼感知上限）

### 🐛 ESP32 引脚冲突（烧坏芯片的重灾区）
| 引脚 | 用途 | 问题 |
|------|------|------|
| GPIO 3 | RXD0 | 设 OUTPUT 会搞死串口通信 |
| GPIO 6-11 | 内部 Flash | 操作会崩溃 ESP32 |
| GPIO 1 | TXD0 | 设 OUTPUT 影响串口 |

**教训：** 固件引脚分配前先查 **ESP32 Pin Mux 表**，避开功能引脚。

**V2 检查清单：**
- [ ] 所有引脚不是 RXD0(3)、TXD0(1)、Flash(6-11)
- [ ] 确认开发板原理图有没有特殊引脚（如 PSRAM 引脚）

### 🐛 bleak API 版本差异
```python
# ❌ bleak 3.x 没有 get_services()
await client.get_services()  # AttributeError

# ✅ 等待服务自动发现
await asyncio.sleep(1.0)
for svc in client.services:
    ...
```

**教训：** 使用新的 Python 库前先检查 API 版本。bleak 3.x 和 2.x 的 API 差异显著。

**V2 检查清单：**
- [ ] 所有 Python 依赖版本锁定（requirements.txt）
- [ ] 新库 API 与实际安装版本一致

---

## 3. 硬件经验

### ESP32 供电
- BLE + MPU6050 同时工作峰值电流 ~500mA
- 普通 USB 线压降大 → 触发 brownout 检测 → 芯片重启
- 解决方案：短粗 USB 线 / 直接插主板口 / 加 100µF 电容

### MPU6050 I2C 接线
- 杜邦线接触不良会导致 I2C 间歇性失败
- 建议 V2 直接焊接或使用杜邦头压紧
- `Wire.begin(21, 22)` 需显式指定引脚

### BLE 连接
- ESP32 BLE 通知频率实测可达 66Hz
- Windows BLE 栈可能批量送达通知
- 用 nRF Connect / LightBlue 手机 APP 扫描确认设备广播

---

## 4. V2 开发建议

### 推荐技术栈
| 层 | V1 方案 | V2 建议 | 原因 |
|---|---------|---------|------|
| UI | tkinter | 同或换 PyQt/WinUI | tkinter 够用但维护性差 |
| BLE | bleak | 同（成熟） | 已验证可用 |
| 打包 | PyInstaller | 同 | 零安装零卸载已验证 |
| 固件 | Arduino | 保持或转 ESP-IDF | Arduino 够用 |

### 优先修复清单
1. GestureEngine 对圆形菜单的场景适配（目前为线性菜单设计）
2. BLE 断线重连逻辑
3. 配置热重载的健壮性
4. 内存泄漏检查（tkinter after 回调不断叠加）

### 推荐的目录结构
```
wavepie-v2/
├── pc-client/        # PC 端应用
│   ├── src/
│   │   ├── input/    # InputProvider 实现
│   │   ├── mapper/   # ActionMapper
│   │   ├── gesture/  # 手势引擎
│   │   ├── executor/ # 动作执行
│   │   └── ui/       # 界面
│   └── config.yaml
├── firmware/         # ESP32 固件
├── docs/             # 文档
│   └── postmortem-v1.md  ← 本文档
├── tools/            # 诊断工具
└── README.md
```

---

## 5. 文件清单（client-v1 最终版）

```
client-v1/
├── src/
│   ├── app.py              (247行) 统一入口
│   ├── tray.py             (116行) 系统托盘
│   ├── config_editor.py    (968行) 配置编辑器
│   ├── input/
│   │   ├── protocol.py     (164行) HAL 接口
│   │   ├── mouse.py        (129行) 鼠标模拟输入
│   │   ├── gamepad.py      (155行) 手柄输入
│   │   └── ble.py          (233行) BLE 输入
│   ├── mapper/mapper.py    (117行) 路由层
│   ├── gesture/engine.py   (93行)  手势引擎
│   ├── ui/overlay.py       (423行) 径向菜单
│   ├── executor/actions.py (250行) 动作执行
│   └── utils/config.py     (✓)    配置加载
├── config.yaml             (128行) 
└── requirements.txt        (7行)
```

> client-v1 于 2026-05-14 归档。
> 核心经验已记录于此文档，V2 开发前请完整阅读。
