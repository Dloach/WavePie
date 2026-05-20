/*
  WavePie V2 固件 — 手枪式握把体感扇区选择

  Core 0: MPU6050 (100Hz) → Madgwick → 激活锁定 → 扇区映射 → 队列发事件
  Core 1: BLE 广播 + FreeRTOS 队列接收 → 发送 0xAA/0xBB

  按键去抖: 10ms 边缘检测，滤波噪声
  扇区迟滞: 时间滞回（切换后 30ms 内不再次切换）
  BLE 跨核: xQueue 解耦，无竞态
*/

#include <Arduino.h>
#include <Wire.h>
#include <freertos/queue.h>

#include "madgwick.h"
#include "ble_service.h"

BLEServiceManager ble;  // 全局，setup 中初始化

// ============================================================
// 引脚 & 参数
// ============================================================

constexpr int PIN_BUTTON = 25;
constexpr int PIN_LED    = 2;

constexpr int SDA_PIN = 32;
constexpr int SCL_PIN = 33;

constexpr int   NUM_SECTORS      = 12;
constexpr float MAX_ANGLE        = 60.0f;     // ±60° → 全范围
constexpr int   HYSTERESIS_TICKS = 3;          // 切换后 3 帧不重复切换

constexpr int   IMU_HZ           = 250;
constexpr int   IMU_INTERVAL_MS  = 1000 / IMU_HZ;

// 按键去抖参数
constexpr int   DEBOUNCE_MS      = 15;

// MPU6050 寄存器
#define MPU6050_ADDR          0x68
#define MPU6050_WHO_AM_I      0x75
#define MPU6050_ACCEL_X       0x3B
#define MPU6050_GYRO_X        0x43
#define MPU6050_PWR_MGMT      0x6B
#define MPU6050_GYRO_CONFIG   0x1B
#define MPU6050_ACCEL_CONFIG  0x1C
#define MPU6050_CONFIG        0x1A

// Madgwick 缩放常量
constexpr float ACCEL_SCALE = 16384.0f;
constexpr float GYRO_SCALE  = 131.0f;

// ============================================================
// BLE 事件队列（Core 0 → Core 1 解耦）
// ============================================================

struct BLEEvent {
    enum Type : uint8_t { SECTOR = 0xAA, CONFIRM = 0xBB, AIM = 0xCC };
    Type  type;
    uint8_t sector;
    int8_t  roll;
    int8_t  pitch;
};

QueueHandle_t g_bleQueue = nullptr;

static void queue_ble(BLEEvent::Type t, uint8_t s) {
    if (!g_bleQueue) return;
    BLEEvent ev = { t, s, 0, 0 };
    xQueueSend(g_bleQueue, &ev, 0);
}

static void queue_ble_aim(int8_t r, int8_t p) {
    if (!g_bleQueue) return;
    BLEEvent ev = { BLEEvent::AIM, 0, r, p };
    xQueueSend(g_bleQueue, &ev, 0);
}

// ============================================================
// 全局对象
// ============================================================

Madgwick filter;
// BLE 对象只由 Core 1 访问

// ============================================================
// MPU6050 底层
// ============================================================

static void mpu_write(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(MPU6050_ADDR);
    Wire.write(reg);
    Wire.write(val);
    Wire.endTransmission(true);
}

static uint8_t mpu_read(uint8_t reg) {
    Wire.beginTransmission(MPU6050_ADDR);
    Wire.write(reg);
    Wire.endTransmission(false);
    Wire.requestFrom(static_cast<uint8_t>(MPU6050_ADDR), 1);
    return Wire.read();
}

static bool mpu_begin() {
    Wire.begin(SDA_PIN, SCL_PIN);
    Wire.setClock(400000);
    delay(10);
    if (mpu_read(MPU6050_WHO_AM_I) != 0x68) return false;
    mpu_write(MPU6050_PWR_MGMT, 0x00);
    vTaskDelay(pdMS_TO_TICKS(100));
    mpu_write(MPU6050_GYRO_CONFIG, 0x00);   // ±250°/s
    mpu_write(MPU6050_ACCEL_CONFIG, 0x00);  // ±2g
    mpu_write(MPU6050_CONFIG, 0x01);        // 1Hz LPF
    return true;
}

static bool mpu_read_raw(int16_t* ax, int16_t* ay, int16_t* az,
                         int16_t* gx, int16_t* gy, int16_t* gz) {
    Wire.beginTransmission(MPU6050_ADDR);
    Wire.write(MPU6050_ACCEL_X);
    Wire.endTransmission(false);
    Wire.requestFrom(static_cast<uint8_t>(MPU6050_ADDR), 14);
    if (Wire.available() < 14) return false;
    uint8_t buf[14];
    for (int i = 0; i < 14; i++) buf[i] = Wire.read();
    *ax = (buf[0]  << 8) | buf[1];
    *ay = (buf[2]  << 8) | buf[3];
    *az = (buf[4]  << 8) | buf[5];
    *gx = (buf[8]  << 8) | buf[9];
    *gy = (buf[10] << 8) | buf[11];
    *gz = (buf[12] << 8) | buf[13];
    return true;
}

// ============================================================
// 四元数数学
// ============================================================

static void q_conj(const float q[4], float out[4]) {
    out[0] = q[0]; out[1] = -q[1]; out[2] = -q[2]; out[3] = -q[3];
}

static void q_mul(const float a[4], const float b[4], float out[4]) {
    out[0] = a[0]*b[0] - a[1]*b[1] - a[2]*b[2] - a[3]*b[3];
    out[1] = a[0]*b[1] + a[1]*b[0] + a[2]*b[3] - a[3]*b[2];
    out[2] = a[0]*b[2] - a[1]*b[3] + a[2]*b[0] + a[3]*b[1];
    out[3] = a[0]*b[3] + a[1]*b[2] - a[2]*b[1] + a[3]*b[0];
}

/*
  从相对四元数提取水平指向角（度）
  使用标准 yaw 公式：绕世界坐标系 Z 轴（重力方向）的旋转。
  手枪式握把（X 竖直向上），绕重力轴旋转 = 左右瞄准。
*/
static float quat_heading(const float q[4]) {
    return atan2f(2.0f*(q[0]*q[3] + q[1]*q[2]),
                  1.0f - 2.0f*(q[2]*q[2] + q[3]*q[3])) * 180.0f / M_PI;
}

// ============================================================
// 扇区映射（时间滞回）
// ============================================================

static int angle_to_sector(float angle, int num_sectors) {
    float clamped = constrain(angle, -MAX_ANGLE, MAX_ANGLE);
    float norm = (clamped / MAX_ANGLE) * 180.0f;
    float deg = norm + 180.0f;
    float sec = 360.0f / num_sectors;
    return ((int)((deg + sec/2) / sec) + 1) % num_sectors;
}

// ============================================================
// 按键去抖
// ============================================================

struct DebouncedButton {
    int  pin;
    bool stable_state;       // 确认后的稳定状态
    bool last_raw;           // 上次读到的原始电平
    unsigned long last_toggle_ms;  // 最后一次电平变化的时间

    void begin(int p) {
        pin = p;
        pinMode(pin, INPUT_PULLUP);
        stable_state = (digitalRead(pin) == LOW);
        last_raw = stable_state;
        last_toggle_ms = millis();
    }

    // 轮询去抖，返回更新后的稳定状态
    bool read() {
        bool raw = (digitalRead(pin) == LOW);
        unsigned long now = millis();
        if (raw != last_raw) {
            last_raw = raw;
            last_toggle_ms = now;
        }
        if (now - last_toggle_ms >= DEBOUNCE_MS) {
            stable_state = raw;
        }
        return stable_state;
    }
};

// ============================================================
// Core 0: 传感器 & 算法
// ============================================================

void core0_task(void* param) {
    vTaskDelay(pdMS_TO_TICKS(500));

    pinMode(PIN_BUTTON, INPUT_PULLUP);

    int16_t ax, ay, az, gx, gy, gz;
    unsigned long last_imu = 0;

    float accum_roll = 0.0f;    // Z 轴旋转（左右瞄准）
    float accum_pitch = 0.0f;   // Y 轴旋转（上下瞄准）
    bool  locked = false;
    int   current_sector = -1;
    int   hyst_counter = 0;
    unsigned long last_motion = 0;   // 最后一次检测到运动（毫秒）
    bool  mpu_sleeping = false;      // MPU6050 是否休眠

    // 按键去抖状态
    bool  btn_stable = false;
    bool  prev_btn = false;
    unsigned long btn_last_change = 0;

    while (true) {
        // ★ 按键去抖（始终运行，不依赖 IMU）
        bool raw = (digitalRead(PIN_BUTTON) == LOW);
        if (raw != btn_stable) {
            btn_stable = raw;
            btn_last_change = millis();
        }
        bool stable = (millis() - btn_last_change >= 15) ? btn_stable : prev_btn;

        bool pressed  =  stable && !prev_btn;
        bool released = !stable &&  prev_btn;
        prev_btn = stable;



        // ── 状态机（独立于 IMU）──
        // Debug: 按键原始电平（每次循环）
        if (btn_stable != prev_btn) {
            Serial.printf("[DBG] btn=%d raw=%d stable=%d pressed=%d released=%d\n",
                          btn_stable, raw, stable, pressed, released);
        }

        if (pressed && !locked) {
            Serial.println("[BTN] 按下 🔒");
            accum_roll = 0.0f;
            accum_pitch = 0.0f;
            locked = true;
            current_sector = -1;
            hyst_counter = 0;
            digitalWrite(PIN_LED, HIGH);
        }

        if (released && locked) {
            Serial.println("[BTN] 松开 🔓");
            locked = false;
            digitalWrite(PIN_LED, LOW);
            if (current_sector >= 0) {
                queue_ble(BLEEvent::CONFIRM, (uint8_t)current_sector);
            }
            current_sector = -1;
        }

        // ── MPU6050 休眠管理 ──
        if (mpu_sleeping) {
            if (pressed) {  // 按钮按下时唤醒
                mpu_sleeping = false;
                mpu_begin();
                last_motion = millis();
            }
        } else if (!locked && millis() - last_motion > 180000) {  // 3分钟无运动 → 休眠
            mpu_write(MPU6050_PWR_MGMT, 0x40);  // SLEEP 位
            mpu_sleeping = true;
        }

        // ── IMU 读取（100Hz，锁定有效时）──
        unsigned long now = millis();
        if (now - last_imu >= IMU_INTERVAL_MS && locked) {
            last_imu = now;
            float dt = IMU_INTERVAL_MS / 1000.0f;

            if (mpu_read_raw(&ax, &ay, &az, &gx, &gy, &gz)) {
                // ★ 2D 陀螺仪积分：芯片逆时针旋转90°摆放
                //   原始: X→右手  Y→正前  Z→竖直
                //   旋转后: X→左后  Y→右手  Z→竖直
                //   物理左右瞄准(yaw)   = 传感器 Z = gz
                //   物理上下瞄准(pitch) = 传感器 -X = -gx
                float gz_dps = gz / GYRO_SCALE;
                float gx_dps = gx / GYRO_SCALE;
                if (fabsf(gz_dps) < 2.0f) gz_dps = 0;
                if (fabsf(gx_dps) < 2.0f) gx_dps = 0;
                // 运动检测
                if (gz_dps != 0 || gx_dps != 0) last_motion = millis();
                accum_roll  += gz_dps * dt;
                accum_pitch += gx_dps * dt;

                // 钳位到 ±30°（对应 int8 -127~+127）
                accum_roll  = constrain(accum_roll, -30.0f, 30.0f);
                accum_pitch = constrain(accum_pitch, -30.0f, 30.0f);

                int8_t roll_byte  = (int8_t)(accum_roll  / 30.0f * 127.0f);
                int8_t pitch_byte = (int8_t)(accum_pitch / 30.0f * 127.0f);

                // 计算扇区（用于 0xBB 确认）
                float angle = atan2f(accum_roll, accum_pitch) * 180.0f / M_PI;
                int sector = angle_to_sector(angle, NUM_SECTORS);

                // 送 2D 瞄准数据
                queue_ble_aim(roll_byte, pitch_byte);
                current_sector = sector;

            }
        }

        vTaskDelay(pdMS_TO_TICKS(1));
    }
}

// ============================================================
// Core 1: BLE
// ============================================================

void core1_task(void* param) {
    BLEEvent ev;
    while (true) {
        if (xQueueReceive(g_bleQueue, &ev, pdMS_TO_TICKS(50))) {
            if (ev.type == BLEEvent::AIM) {
                ble.sendAim(ev.roll, ev.pitch);
            } else if (ev.type == BLEEvent::CONFIRM) {
                ble.sendConfirm(ev.sector);
            }
        }
    }
}

// ============================================================
// Setup
// ============================================================

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("\n[Boot] WavePie V3");

    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    g_bleQueue = xQueueCreate(8, sizeof(BLEEvent));
    ble.begin("WavePie");
    Serial.println("[BLE] ✅ 广播中");
    xTaskCreatePinnedToCore(core1_task, "BLE", 8192, NULL, 1, NULL, 1);
    Serial.println("[BLE] ✅ Core 1 启动");

    if (!mpu_begin()) {
        Serial.println("[Boot] ❌ MPU6050 失败");
        pinMode(PIN_LED, OUTPUT);
        while (true) {
            digitalWrite(PIN_LED, !digitalRead(PIN_LED));
            delay(100);
        }
    }
    Serial.println("[Boot] ✅ MPU6050 OK");

    filter.setBeta(0.1f);
    core0_task(NULL);
}

void loop() {}
