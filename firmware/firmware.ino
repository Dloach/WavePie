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

// ============================================================
// 引脚 & 参数
// ============================================================

constexpr int PIN_BUTTON = 4;
constexpr int PIN_LED    = 2;

constexpr int SDA_PIN = 21;
constexpr int SCL_PIN = 22;

constexpr int   NUM_SECTORS      = 12;
constexpr float MAX_ANGLE        = 60.0f;     // ±60° → 全范围
constexpr int   HYSTERESIS_TICKS = 3;          // 切换后 3 帧不重复切换

constexpr int   IMU_HZ           = 100;
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
    enum Type : uint8_t { SECTOR = 0xAA, CONFIRM = 0xBB };
    Type  type;
    uint8_t sector;
};

QueueHandle_t g_bleQueue = nullptr;

static void queue_ble(BLEEvent::Type t, uint8_t s) {
    if (!g_bleQueue) return;
    BLEEvent ev = { t, s };
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

    float q_zero[4] = {1,0,0,0};
    bool  locked = false;
    int   current_sector = -1;
    int   hyst_counter = 0;

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

        if (pressed)  Serial.printf("[BTN] 按下\n");
        if (released) Serial.printf("[BTN] 松开\n");

        // ── 状态机（独立于 IMU）──
        if (pressed && !locked) {
            // 锁当前姿态
            memcpy(q_zero, filter.q, sizeof(q_zero));
            locked = true;
            current_sector = -1;
            hyst_counter = 0;
            digitalWrite(PIN_LED, HIGH);
        }

        if (released && locked) {
            locked = false;
            digitalWrite(PIN_LED, LOW);
            if (current_sector >= 0) {
                queue_ble(BLEEvent::CONFIRM, (uint8_t)current_sector);
            }
            current_sector = -1;
        }

        // ── IMU 读取（100Hz）──
        unsigned long now = millis();
        if (now - last_imu >= IMU_INTERVAL_MS && locked) {
            last_imu = now;
            if (mpu_read_raw(&ax, &ay, &az, &gx, &gy, &gz)) {
                float dt = IMU_INTERVAL_MS / 1000.0f;
                filter.update(ax / ACCEL_SCALE, ay / ACCEL_SCALE, az / ACCEL_SCALE,
                              gx / GYRO_SCALE, gy / GYRO_SCALE, gz / GYRO_SCALE, dt);

                // 计算扇区
                float q_conj_zero[4];
                q_conj(q_zero, q_conj_zero);
                float q_rel[4];
                q_mul(q_conj_zero, filter.q, q_rel);
                float angle = quat_heading(q_rel);
                int sector = angle_to_sector(angle, NUM_SECTORS);

                Serial.printf("[IMU] angle=%.1f sector=%d\n", angle, sector);
                if (hyst_counter > 0) {
                    hyst_counter--;
                } else if (sector != current_sector) {
                    current_sector = sector;
                    hyst_counter = HYSTERESIS_TICKS;
                    queue_ble(BLEEvent::SECTOR, (uint8_t)sector);
                }
            }
        }

        vTaskDelay(pdMS_TO_TICKS(1));
    }
}

// ============================================================
// Core 1: BLE
// ============================================================

void core1_task(void* param) {
    BLEServiceManager ble;
    ble.begin("WavePie");

    BLEEvent ev;
    while (true) {
        if (xQueueReceive(g_bleQueue, &ev, pdMS_TO_TICKS(50))) {
            if (ev.type == BLEEvent::SECTOR) {
                ble.sendSector(ev.sector);
                Serial.printf("[BLE] → 0xAA sector=%d\n", ev.sector);
            } else if (ev.type == BLEEvent::CONFIRM) {
                ble.sendConfirm(ev.sector);
                Serial.printf("[BLE] → 0xBB confirm=%d\n", ev.sector);
            }
        }
    }
}

// ============================================================
// Setup
// ============================================================

void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("\n[Boot] WavePie V2");

    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    g_bleQueue = xQueueCreate(8, sizeof(BLEEvent));
    xTaskCreatePinnedToCore(core1_task, "BLE", 8192, NULL, 1, NULL, 1);

    if (!mpu_begin()) {
        Serial.println("[Boot] ❌ MPU6050 失败");
        pinMode(PIN_LED, OUTPUT);
        while (true) {
            digitalWrite(PIN_LED, !digitalRead(PIN_LED));
            delay(100);
        }
    }

    filter.setBeta(0.1f);
    core0_task(NULL);
}

void loop() {}
