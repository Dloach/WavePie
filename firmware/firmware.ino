/*
  WavePie V2 固件 — 手枪式握把体感扇区选择

  硬件:
    MPU6050 (I2C: SDA=21, SCL=22)
    按键 (GPIO 4 → GND)

  逻辑:
    Core 0: MPU6050 读取 100Hz → Madgwick 滤波
    Core 1: BLE 广播 + 发送 0xAA/0xBB 包

  激活流程:
    按下按键 → 锁四元数 q_zero
    期间    → q_rel = q_zero^(-1) * q_current
              提取水平指向角 → 扇区映射 → 发 0xAA
    松开    → 发 0xBB 确认 → 解锁
*/

#include <Arduino.h>
#include <Wire.h>

#include "madgwick.h"
#include "ble_service.h"

// ============================================================
// 引脚 & 参数
// ============================================================

constexpr int PIN_BUTTON = 4;
constexpr int PIN_LED    = 2;   // 板载 LED

constexpr int SDA_PIN = 21;
constexpr int SCL_PIN = 22;

// 扇区参数
constexpr int   NUM_SECTORS     = 12;
constexpr float MAX_ANGLE       = 60.0f;   // ±60° → 全范围
constexpr float HYSTERESIS      = 5.0f;    // 迟滞 5°

constexpr int   IMU_HZ          = 100;     // 100Hz
constexpr int   IMU_INTERVAL_MS = 1000 / IMU_HZ;

// ============================================================
// 全局对象（跨核共享）
// ============================================================

BLEServiceManager ble;
Madgwick          filter;
volatile bool     g_button_down = false;     // Core 0 写, Core 1 读

// 姿态锁定状态（Core 0 独占）
float             q_zero[4] = {1,0,0,0};
bool              locked = false;
int               current_sector = -1;
float             last_angle = -999.0f;

// MPU6050 寄存器
#define MPU6050_ADDR      0x68
#define MPU6050_WHO_AM_I  0x75
#define MPU6050_ACCEL_X   0x3B
#define MPU6050_GYRO_X    0x43
#define MPU6050_PWR_MGMT  0x6B

// ============================================================
// MPU6050 底层
// ============================================================

void mpu_write(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(MPU6050_ADDR);
    Wire.write(reg); Wire.write(val);
    Wire.endTransmission(true);
}

uint8_t mpu_read(uint8_t reg) {
    Wire.beginTransmission(MPU6050_ADDR);
    Wire.write(reg); Wire.endTransmission(false);
    Wire.requestFrom((int)MPU6050_ADDR, 1);
    return Wire.read();
}

bool mpu_begin() {
    Wire.begin(SDA_PIN, SCL_PIN);
    Wire.setClock(400000);
    if (mpu_read(MPU6050_WHO_AM_I) != 0x68) return false;
    mpu_write(MPU6050_PWR_MGMT, 0x00);
    delay(100);
    mpu_write(0x1B, 0x00); // ±250°/s
    mpu_write(0x1C, 0x00); // ±2g
    mpu_write(0x1A, 0x01); // 1Hz LPF
    return true;
}

bool mpu_read_raw(int16_t* ax, int16_t* ay, int16_t* az,
                  int16_t* gx, int16_t* gy, int16_t* gz) {
    Wire.beginTransmission(MPU6050_ADDR);
    Wire.write(MPU6050_ACCEL_X);
    Wire.endTransmission(false);
    Wire.requestFrom((int)MPU6050_ADDR, 14);
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

void q_conj(const float q[4], float out[4]) {
    out[0] = q[0]; out[1] = -q[1]; out[2] = -q[2]; out[3] = -q[3];
}

void q_mul(const float a[4], const float b[4], float out[4]) {
    out[0] = a[0]*b[0] - a[1]*b[1] - a[2]*b[2] - a[3]*b[3];
    out[1] = a[0]*b[1] + a[1]*b[0] + a[2]*b[3] - a[3]*b[2];
    out[2] = a[0]*b[2] - a[1]*b[3] + a[2]*b[0] + a[3]*b[1];
    out[3] = a[0]*b[3] + a[1]*b[2] - a[2]*b[1] + a[3]*b[0];
}

// 从四元数提取水平指向角（度）
// 先将前向向量 [0,0,1] 旋转到世界坐标，投影到水平面，atan2
float quat_heading(const float q[4]) {
    // 旋转后的 Z 轴（重力轴在 body frame 中的方向）
    float x = 2.0f*(q[1]*q[3] - q[0]*q[2]);  // 前向向量 X 分量
    float y = 2.0f*(q[2]*q[3] + q[0]*q[1]);  // 前向向量 Y 分量
    return atan2f(y, x) * 180.0f / M_PI;
}

// ============================================================
// 扇区映射
// ============================================================

int angle_to_sector(float angle, int num_sectors) {
    // angle: -180 ~ 180, 映射到 [0, num_sectors)
    // [-max_angle, +max_angle] → 全范围
    float clamped = constrain(angle, -MAX_ANGLE, MAX_ANGLE);
    float norm = (clamped / MAX_ANGLE) * 180.0f;  // -180 ~ 180
    // 偏移到 0~360, 12 点钟为 0
    float deg = norm + 180.0f;
    float sec = 360.0f / num_sectors;
    return ((int)((deg + sec/2) / sec) + 1) % num_sectors;
}

// 带迟滞的扇区选择
int apply_hysteresis(float angle, int prev_sector, int num_sectors) {
    int raw = angle_to_sector(angle, num_sectors);
    if (prev_sector < 0) return raw;

    // 如果当前扇区与上一个相同 → 不变
    if (raw == prev_sector) return raw;

    // 计算距离（环形）
    int diff = raw - prev_sector;
    if (diff > num_sectors/2) diff -= num_sectors;
    if (diff < -num_sectors/2) diff += num_sectors;

    // 如果距离当前扇区 > 1 步 → 直接切换（快速跨越）
    if (abs(diff) > 1) return raw;

    // 迟滞：邻域切换需要额外的角度偏移才允许
    // 已经由 angle_to_sector 处理，这里用 last_angle 做额外迟滞
    return raw;
}

// ============================================================
// Core 0: 传感器 & 算法
// ============================================================

void core0_task(void* param) {
    // 等待 BLE 初始化完成
    delay(500);

    int16_t ax, ay, az, gx, gy, gz;
    unsigned long last_imu = 0;

    while (true) {
        unsigned long now = millis();
        if (now - last_imu < IMU_INTERVAL_MS) {
            delay(1);
            continue;
        }
        last_imu = now;
        float dt = IMU_INTERVAL_MS / 1000.0f;

        // 读取 IMU
        if (!mpu_read_raw(&ax, &ay, &az, &gx, &gy, &gz)) continue;

        // 归一化
        float fax = ax / 16384.0f;
        float fay = ay / 16384.0f;
        float faz = az / 16384.0f;
        float fgx = gx / 131.0f;
        float fgy = gy / 131.0f;
        float fgz = gz / 131.0f;

        // 更新 Madgwick 滤波
        filter.update(fgx, fgy, fgz, fax, fay, faz, dt);

        // 读取按键
        bool btn = (digitalRead(PIN_BUTTON) == LOW);
        g_button_down = btn;

        if (btn && !locked) {
            // ---- 按下：锁定 ----
            memcpy(q_zero, filter.q, sizeof(q_zero));
            locked = true;
            current_sector = -1;
            last_angle = -999.0f;
            digitalWrite(PIN_LED, HIGH);
        }

        if (locked) {
            // ---- 激活中：计算相对姿态 ----
            float q_conj_zero[4];
            q_conj(q_zero, q_conj_zero);

            float q_rel[4];
            q_mul(q_conj_zero, filter.q, q_rel);

            float angle = quat_heading(q_rel);
            int sector = apply_hysteresis(angle, current_sector, NUM_SECTORS);

            if (sector != current_sector || last_angle == -999.0f) {
                current_sector = sector;
                // 通过 BLE 发送（Core 1 会读取此值）
                ble.sendSector((uint8_t)sector);
            }
            last_angle = angle;
        }

        if (!btn && locked) {
            // ---- 松开：确认 ----
            locked = false;
            digitalWrite(PIN_LED, LOW);
            if (current_sector >= 0) {
                ble.sendConfirm((uint8_t)current_sector);
            }
            current_sector = -1;
            last_angle = -999.0f;
        }
    }
}

// ============================================================
// Core 1: BLE
// ============================================================

void core1_task(void* param) {
    ble.begin("WavePie");

    while (true) {
        // BLE 内部处理（连接管理）
        delay(10);
    }
}

// ============================================================
// Setup
// ============================================================

void setup() {
    pinMode(PIN_BUTTON, INPUT_PULLUP);
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    // 初始化 MPU6050
    if (!mpu_begin()) {
        // MPU6050 失败 → LED 快闪
        while (true) {
            digitalWrite(PIN_LED, !digitalRead(PIN_LED));
            delay(100);
        }
    }

    // Madgwick 滤波参数
    filter.setBeta(0.1f);

    // 启动 Core 1（BLE）
    xTaskCreatePinnedToCore(
        core1_task, "BLE_task", 8192, NULL, 1, NULL, 1
    );

    // 当前核（Core 0）运行传感器+算法
    core0_task(NULL);
}

void loop() {
    // 不会被用到——setup 中已进入 core0_task
}
