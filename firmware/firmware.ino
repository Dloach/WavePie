/* 蓝牙体感控制器 — ESP32 固件

   功能:
   - BLE GATT 服务（按键/IMU/滚轮/反馈）
   - MPU6050 读取加速度+陀螺仪
   - 互补滤波计算姿态角
   - 多按键去抖+长按检测
   - LED/蜂鸣器反馈控制

   接线:
     MPU6050 VCC → ESP32 3.3V
     MPU6050 GND → ESP32 GND
     MPU6050 SDA → GPIO 21
     MPU6050 SCL → GPIO 22

     主按键 → GPIO 4 (GND 触发)
     副键1  → GPIO 5
     副键2  → GPIO 6
     LED_R  → GPIO 2 (PWM)
     LED_G  → GPIO 3 (PWM)
     蜂鸣器 → GPIO 7

   烧录:
     Arduino IDE → 选择 ESP32 Dev Module → 上传
*/

#include <Arduino.h>
#include "ble_service.h"
#include "mpu6050.h"
#include "imu_filter.h"
#include "buttons.h"
#include "feedback.h"

// ── 引脚定义 ──
constexpr int PIN_BTN_MAIN = 4;
constexpr int PIN_BTN_AUX1 = 5;
constexpr int PIN_BTN_AUX2 = 15; // 不能用6/7/8/9/10/11(Falsh引脚)
constexpr int PIN_LED_R    = 2;  // 板载 LED
constexpr int PIN_LED_G    = 12; // 不能用 GPIO3(RXD0)，冲突串口
constexpr int PIN_BUZZER   = 14; // 不能用6/7(Flash引脚)

// ── 全局对象 ──
BLEServiceManager  ble;
MPU6050            imu;
ComplementaryFilter filter(0.98f);  // 互补滤波系数
ButtonManager      buttons;
FeedbackController feedback(PIN_LED_R, PIN_LED_G, PIN_BUZZER);

// ── 定时器 ──
unsigned long last_imu_ms = 0;
constexpr int IMU_INTERVAL_MS = 15;  // ~66Hz

// ============================================================
// 初始化
// ============================================================

void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("\n===== BLE Gesture Controller =====");

    // 1. 按键初始化
    buttons.add(PIN_BTN_MAIN, "主按钮");
    buttons.add(PIN_BTN_AUX1, "副键1");
    buttons.add(PIN_BTN_AUX2, "副键2");
    Serial.printf("[BTN] %d 个按键已初始化\n", buttons.count());

    // 2. 反馈初始化
    feedback.begin();
    feedback.led_green();
    Serial.println("[LED] 状态灯已初始化");

    // 3. MPU6050 初始化
    if (!imu.begin()) {
        Serial.println("[IMU] ❌ 连接失败！检查接线");
        feedback.led_red();
        delay(2000);
    } else {
        Serial.println("[IMU] ✅ MPU6050 已连接");
        imu.calibrate(200);  // 200 次采样校准
        Serial.println("[IMU] ✅ 校准完成");
        feedback.led_green();
    }

    // 4. BLE 初始化
    ble.begin("BLE Gesture Ctrl");
    Serial.println("[BLE] 服务已启动，等待连接...");
    feedback.led_blink(500);
}

// ============================================================
// 主循环
// ============================================================

void loop() {
    unsigned long now = millis();

    // ── BLE 连接状态监听 ──
    ble.update();
    if (ble.isConnected()) {
        feedback.set_connected(true);
    } else {
        feedback.set_connected(false);
    }

    // ── 处理 BLE 收到的反馈指令 ──
    uint8_t fb_cmd[4];
    if (ble.readFeedback(fb_cmd)) {
        feedback.handle_command(fb_cmd);
    }

    // ── 按键检测（10ms 轮询）──
    ButtonEvent evt;
    while (buttons.read(&evt)) {
        Serial.printf("[BTN] %s %s\n",
            evt.pressed ? "按下" : "松开",
            evt.is_long ? "(长按)" : "");

        // 通过 BLE 发送按键事件
        ble.sendButton(evt.id, evt.pressed, evt.is_long);
    }

    // ── IMU 数据读取（~66Hz）──
    if (now - last_imu_ms >= IMU_INTERVAL_MS) {
        last_imu_ms = now;

        float ax, ay, az, gx, gy, gz;
        if (imu.read(&ax, &ay, &az, &gx, &gy, &gz)) {
            // 互补滤波 → 姿态角
            filter.update(ax, ay, az, gx, gy, gz, IMU_INTERVAL_MS / 1000.0f);

            // BLE 发送 IMU 数据
            ble.sendIMU(filter.roll, filter.pitch, filter.yaw);

            // 调试输出（可注释掉）
            // Serial.printf("IMU: roll=%.1f pitch=%.1f\n", filter.roll, filter.pitch);
        }
    }

    // ── LED 状态更新 ──
    feedback.update(now);
}
