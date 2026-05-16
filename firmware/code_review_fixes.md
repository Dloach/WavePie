# 固件代码修复清单

> 按优先级排列，每个条目包含 **问题描述** + **具体修复方案** + **涉及文件**。

---

##   P0 — 扇区边界无迟滞（会抖）

**问题**：`HYSTERESIS` 常量定义后从未使用，`apply_hysteresis()` 末尾总是 `return raw`，没有任何滞回逻辑。用户在扇区边界附近手腕微动会产生 0xAA 包泛滥。

**涉及文件**：`firmware.ino`

**修复**：

```cpp
// 删除全局变量 last_angle（不再需要）

// 新增全局变量
float g_hyst_angle = -999.0f;  // 上次触发扇区切换时的角度

// 替换 apply_hysteresis 函数为：
int apply_hysteresis(float angle, int prev_sector, int num_sectors) {
    int raw = angle_to_sector(angle, num_sectors);
    if (prev_sector < 0) return raw;
    if (raw == prev_sector) return raw;

    // 环形距离（支持跨越 0 号扇区边界）
    int diff = raw - prev_sector;
    if (diff > num_sectors / 2) diff -= num_sectors;
    if (diff < -num_sectors / 2) diff += num_sectors;

    // 快速跨越（>1步）直接切换，不用迟滞
    if (abs(diff) > 1) return raw;

    // ⬇ 邻域切换：角度必须越过中心线至少半个扇区宽度才能触发
    float half_sector = (2.0f * MAX_ANGLE) / num_sectors / 2.0f;

    if (diff == 1) {
        // 正方向：角度必须超过当前扇区上边界 + 半扇区
        float boundary = ((float)(prev_sector) * (2.0f * MAX_ANGLE) / num_sectors) - MAX_ANGLE + half_sector + HYSTERESIS;
        if (angle > boundary) return raw;
    } else if (diff == -1) {
        // 负方向：角度必须低于当前扇区下边界 - 半扇区
        float boundary = ((float)(prev_sector) * (2.0f * MAX_ANGLE) / num_sectors) - MAX_ANGLE - half_sector - HYSTERESIS;
        if (angle < boundary) return raw;
    }

    return prev_sector;  // 不切换
}
```

> 如果上面这个实现太复杂，简化版：记录一次切换后，2~3 帧内不再次切换（时间滞回）。

---

##   P1 — BLE 跨核调用风险 / `_connected` 竞态

**问题**：注释说 BLE 在 Core 1，但 `ble.sendSector()` / `ble.sendConfirm()` 实际在 Core 0 执行。`_connected` 被 BLE task 的 ServerCB 写、Core 0 读，没有 `volatile` 保护。

**涉及文件**：`ble_service.h`（1 处）、`firmware.ino`（架构改动）

**修复 A（推荐）——用 FreeRTOS 队列解耦**：

在 `firmware.ino` 中，Core 0 不再直接调 BLE，而是通过队列发送事件，Core 1 从队列读取后再调用 BLE：

```cpp
// firmware.ino 顶部新增：
#include <freertos/queue.h>

struct BLEEvent {
    enum { SECTOR, CONFIRM } type;
    uint8_t sector;
};
QueueHandle_t g_bleQueue = nullptr;

// core0_task 中，把原来的 ble.sendSector((uint8_t)sector) 替换为：
BLEEvent ev = { BLEEvent::SECTOR, (uint8_t)sector };
xQueueSend(g_bleQueue, &ev, 0);

// ble.sendConfirm(...) 替换为：
BLEEvent ev = { BLEEvent::CONFIRM, (uint8_t)current_sector };
xQueueSend(g_bleQueue, &ev, portMAX_DELAY);

// core1_task 改为：
void core1_task(void* param) {
    ble.begin("WavePie");
    BLEEvent ev;
    while (true) {
        if (xQueueReceive(g_bleQueue, &ev, pdMS_TO_TICKS(10))) {
            if (ev.type == BLEEvent::SECTOR)
                ble.sendSector(ev.sector);
            else
                ble.sendConfirm(ev.sector);
        }
    }
}

// setup() 中，在创建 task 之前：
g_bleQueue = xQueueCreate(16, sizeof(BLEEvent));
```

**修复 B（最小改动）**——仅修复 `_connected` 竞态，保留当前调用方式：

`ble_service.h` 中：

```cpp
// 改：
bool _connected = false;

// 为：
volatile bool _connected = false;

// 同时 ServerCB 的 _flag 类型也要改：
ServerCB(volatile bool* flag) : _flag(flag) {}
void onConnect(BLEServer* s) override { *_flag = true; }
void onDisconnect(BLEServer* s) override { *_flag = false; }
private:
    volatile bool* _flag;
```

> 修复 B 不能解决跨核调 `notify()` 的潜在问题，只是在当前 ESP32 Arduino BLE 实现恰好能跑的前提下降风险。

---

##   P2 — 按键无去抖

**问题**：机械按键按下/松开时有数毫秒的弹跳，100Hz 采样会读到多次翻转，导致锁定/解锁状态闪跳。

**涉及文件**：`firmware.ino` — `core0_task` 函数

**修复**：

```cpp
// 在 core0_task 顶部加入去抖变量：
bool last_btn_state = false;
unsigned long btn_debounce_ms = 0;
constexpr unsigned long DEBOUNCE_DELAY = 30; // 30ms 去抖

// 替换原来的 btn 读取逻辑：
// 旧:  bool btn = (digitalRead(PIN_BUTTON) == LOW);
// 新:
bool btn_raw = (digitalRead(PIN_BUTTON) == LOW);
bool btn;

if (btn_raw != last_btn_state) {
    btn_debounce_ms = now;       // 记录跳变时刻
}
if (now - btn_debounce_ms > DEBOUNCE_DELAY) {
    btn = btn_raw;               // 稳定后采纳
} else {
    btn = last_btn_state;        // 还在抖动期，维持旧值
}
last_btn_state = btn_raw;

// g_button_down = btn; // 删掉这行（此变量未被 Core 1 使用）
```

然后删掉全局变量 `volatile bool g_button_down`（没有代码读取它）。

---

##   P3 — heading 提取含俯仰耦合

**问题**：`quat_heading` 直接将前向轴 `[0,0,1]` 旋转到世界坐标后取 atan2，设备前倾/后仰时前向轴会倾斜，产生虚假水平角。

**涉及文件**：`firmware.ino` — `quat_heading` 函数

**修复方案（取决于设备握持方向）**：

如果设备 Z 轴朝前、Y 轴朝上（手枪式垂直握持）：

```cpp
float quat_heading(const float q[4]) {
    // 旋转 Y 轴 [0, 1, 0]（设备上方）到世界坐标 → 得到重力方向
    float gy_x = 2.0f * (q[1]*q[2] + q[0]*q[3]);  // 不过这里需要 q_conj * [0,1,0] * q
    // ...

    // 简化方法：直接取 Madgwick 的 yaw()，它从欧拉角提取，已经正确
    // 缺点：yaw 的 atan2 参数基于的是 body frame Z 轴在世界坐标的投影
    // 如果设备 Y 朝上、Z 朝前，直接用 heading() 即可：
    // return atan2f(2.0f*(q[0]*q[3] + q[1]*q[2]),
    //               1.0f - 2.0f*(q[2]*q[2] + q[3]*q[3])) * 180.0f / M_PI;
}
```

**如果你确定设备是 Z 朝前、X 朝下（像握枪一样）**：

```cpp
float quat_heading(const float q[4]) {
    // 用重力方向 [0,0,1] → body frame 的投影来确定水平面
    // 然后取 body frame 的 X 轴投影到水平面
    float gx_body = 2.0f * (q[1]*q[3] - q[0]*q[2]);  // 重力在 body X
    float gy_body = 2.0f * (q[2]*q[3] + q[0]*q[1]);  // 重力在 body Y
    float gz_body = 2.0f * (0.5f - q[1]*q[1] - q[2]*q[2]);  // 重力在 body Z

    // 前向轴 [1,0,0] 在水平面上的投影
    // 使用 Gram-Schmidt：减去重力方向的分量
    float g_norm = sqrtf(gx_body*gx_body + gy_body*gy_body + gz_body*gz_body);
    float fx = 1.0f - gx_body * gx_body / (g_norm * g_norm);  // 近似
    // ...

    // ⚠️ 上面的投影涉及较复杂的几何。建议先用 Mathematica/手算验证坐标系定义
    // 在没搞清楚前，直接去掉 pitch 分量凑合的方案：
    // 如果设备前向轴（X）水平，直接用 q 的 yaw 分量
    return atan2f(2.0f*(q[0]*q[3] + q[1]*q[2]),
                  1.0f - 2.0f*(q[2]*q[2] + q[3]*q[3])) * 180.0f / M_PI;
}
```

> **关键**：你需要先拿串口打印 `angle`，实际挥动设备看数值变化，确认坐标系映射是否对。如果手持时前倾后仰不会改变扇区号，说明公式正确。

---

##     中等优先级

### M1 — Madgwick 变量命名

**文件**：`madgwick.h` — `update` 函数内

**修复**：把 `qDot1`~`qDot4` 改名为 `dq_w, dq_x, dq_y, dq_z`（对应 q[0]~q[3]）：

```cpp
float dq_w = 0.5f * (-q1*gx - q2*gy - q3*gz);
float dq_x = 0.5f * ( q0*gx + q2*gz - q3*gy);
float dq_y = 0.5f * ( q0*gy - q1*gz + q3*gx);
float dq_z = 0.5f * ( q0*gz + q1*gy - q2*gx);

// ...

q[0] += dq_w * dt;
q[1] += dq_x * dt;
q[2] += dq_y * dt;
q[3] += dq_z * dt;
```

### M2 — MPU6050 失败后无超时重启

**文件**：`firmware.ino` — `setup` 函数

**修复**：

```cpp
if (!mpu_begin()) {
    for (int i = 0; i < 30; i++) {  // 3秒快闪后重启
        digitalWrite(PIN_LED, !digitalRead(PIN_LED));
        delay(100);
    }
    ESP.restart();
}
```

### M3 — 删除死代码

| 位置 | 内容 |
|------|------|
| `madgwick.h` — `heading()` | 删除整个函数（`.ino` 里用的是 `quat_heading`） |
| `madgwick.h` — `roll()/pitch()/yaw()` | 三选一：删掉 或 保留（未来调试用） |
| `firmware.ino` — `g_button_down` | 删掉全局变量（无人读取） |

### M4 — `new ServerCB` 内存泄漏注释

**文件**：`ble_service.cpp` — `begin` 函数

**修复**：在 `new ServerCB(&_connected)` 上方加一行注释：

```cpp
// 注意：此回调对象生命周期与 BLE server 相同，不需要手动 delete
_server->setCallbacks(new ServerCB(&_connected));
```

---

##     低优先级

### L1 — MPU6050 寄存器地址改为命名常量

**文件**：`firmware.ino`

```cpp
// 替换魔数：
#define MPU6050_GYRO_CONFIG  0x1B
#define MPU6050_ACCEL_CONFIG 0x1C
#define MPU6050_CONFIG       0x1A
```

### L2 — `mpu_read` 的 `(int)` 强制转换改成 `uint8_t`

```cpp
// 旧：
Wire.requestFrom((int)MPU6050_ADDR, 1);
// 新：
Wire.requestFrom(static_cast<uint8_t>(MPU6050_ADDR), 1);
```

### L3 — 代码风格统一

- `.ino` 文件中的 `delay()` 可以换成 `vTaskDelay()` + `pdMS_TO_TICKS()`（更精确的控制）
- `core0_task` 的主循环里 `delay(1)` 改 `vTaskDelay(pdMS_TO_TICKS(1))`

---

## 修复优先级建议

```
1. P2 按键去抖       ← 30 行改动，影响最频繁的用户操作
2. P1 BLE 架构/竞态  ← 推荐方案 A（队列），约 25 行改动
3. P0 扇区迟滞       ← 核心功能，选简化版（时间滞回）约 10 行
4. P3 heading 算法   ← 需实验验证坐标系，不要盲改
5. M1~M4             ← 代码卫生，不影响功能
6. L1~L3             ← 锦上添花
```
