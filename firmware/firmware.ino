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
  从四元数提取水平指向角（度）
  将前向向量 [0,0,1] 旋转到世界坐标，投影到水平面。

  注意：无磁力计辅助，无法消除 Z 轴漂移（yaw 漂移）。
        同时 pitch ±90° 时 heading 会奇异（gimbal lock）。
        手枪式握把 pitch 范围小（±45°），影响可接受。
*/
static float quat_heading(const float q[4]) {
    float x = 2.0f*(q[1]*q[3] - q[0]*q[2]);
    float y = 2.0f*(q[2]*q[3] + q[0]*q[1]);
    return atan2f(y, x) * 180.0f / M_PI;
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

    DebouncedButton btn;
    btn.begin(PIN_BUTTON);

    int16_t ax, ay, az, gx, gy, gz;
    unsigned long last_imu = 0;

    float q_zero[4] = {1,0,0,0};
    bool  locked = false;
    int   current_sector = -1;
    int   hyst_counter = 0;       // 扇区切换后计数，防抖动

    while (true) {
        unsigned long now = millis();
        int32_t diff = (int32_t)(now - last_imu);
        if (diff < IMU_INTERVAL_MS) {
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }
        last_imu = now;
        float dt = IMU_INTERVAL_MS / 1000.0f;

        // 读取 IMU
        if (!mpu_read_raw(&ax, &ay, &az, &gx, &gy, &gz)) continue;

        float fax = ax / ACCEL_SCALE;
        float fay = ay / ACCEL_SCALE;
        float faz = az / ACCEL_SCALE;
        float fgx = gx / GYRO_SCALE;
        float fgy = gy / GYRO_SCALE;
        float fgz = gz / GYRO_SCALE;

        filter.update(fgx, fgy, fgz, fax, fay, faz, dt);

        // 按键去抖 + 边缘检测
        bool btn_state = btn.read();
        static bool prev_btn = false;
        bool pressed  =  btn_state && !prev_btn;   // 下降沿（LOW=按下）
        bool released = !btn_state &&  prev_btn;    // 上升沿（HIGH=松开）
        prev_btn = btn_state;

        if (pressed && !locked) {
            memcpy(q_zero, filter.q, sizeof(q_zero));
            locked = true;
            current_sector = -1;
            hyst_counter = 0;
            digitalWrite(PIN_LED, HIGH);
        }

        if (locked) {
            float q_conj_zero[4];
            q_conj(q_zero, q_conj_zero);

            float q_rel[4];
            q_mul(q_conj_zero, filter.q, q_rel);

            float angle = quat_heading(q_rel);
            int sector = angle_to_sector(angle, NUM_SECTORS);

            // 时间滞回：切换后 HYSTERESIS_TICKS 帧内不允许再次切换
            if (hyst_counter > 0) {
                hyst_counter--;
            } else if (sector != current_sector) {
                current_sector = sector;
                hyst_counter = HYSTERESIS_TICKS;
                queue_ble(BLEEvent::SECTOR, (uint8_t)sector);
            }
        }

        if (released && locked) {
            locked = false;
            digitalWrite(PIN_LED, LOW);
            if (current_sector >= 0) {
                queue_ble(BLEEvent::CONFIRM, (uint8_t)current_sector);
            }
            current_sector = -1;
        }
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
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    if (!mpu_begin()) {
        while (true) {
            digitalWrite(PIN_LED, !digitalRead(PIN_LED));
            vTaskDelay(pdMS_TO_TICKS(100));
        }
    }

    filter.setBeta(0.1f);

    g_bleQueue = xQueueCreate(8, sizeof(BLEEvent));

    xTaskCreatePinnedToCore(core1_task, "BLE", 8192, NULL, 1, NULL, 1);
    core0_task(NULL);
}

void loop() {}
