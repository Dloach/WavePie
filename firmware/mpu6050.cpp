#include "mpu6050.h"

MPU6050::MPU6050(uint8_t addr) : _addr(addr) {}

bool MPU6050::begin() {
    Wire.begin(21, 22);  // SDA=GPIO21, SCL=GPIO22
    Wire.setClock(400000);

    // 验证设备
    uint8_t who = readReg(MPU6050_WHO_AM_I);
    if (who != 0x68) {
        Serial.printf("[MPU6050] WHO_AM_I=0x%02X (期望 0x68)\n", who);
        return false;
    }

    // 唤醒（清除休眠位）
    writeReg(MPU6050_PWR_MGMT, 0x00);
    delay(100);

    // 配置：陀螺仪 ±250°/s, 加速度 ±2g
    writeReg(MPU6050_GYRO_CFG,  0x00); // ±250°/s → 131 LSB/°/s
    writeReg(MPU6050_ACCEL_CFG, 0x00); // ±2g → 16384 LSB/g
    writeReg(MPU6050_CONFIG,    0x01); // 1Hz 低通滤波

    _accel_scale = 16384.0f;
    _gyro_scale  = 131.0f;

    return true;
}

void MPU6050::calibrate(int samples) {
    float ax = 0, ay = 0, az = 0;
    float gx = 0, gy = 0, gz = 0;

    for (int i = 0; i < samples; i++) {
        float tax, tay, taz, tgx, tgy, tgz;
        if (read(&tax, &tay, &taz, &tgx, &tgy, &tgz)) {
            ax += tax; ay += tay; az += taz;
            gx += tgx; gy += tgy; gz += tgz;
        }
        delay(3);
    }

    _aox = ax / samples;
    _aoy = ay / samples;
    _aoz = az / samples - 1.0f;  // Z 轴期望 1g（重力）
    _gox = gx / samples;
    _goy = gy / samples;
    _goz = gz / samples;

    Serial.printf("[MPU6050] 校准偏移: accel=(%.3f,%.3f,%.3f) gyro=(%.3f,%.3f,%.3f)\n",
        _aox, _aoy, _aoz, _gox, _goy, _goz);
}

bool MPU6050::read(float* ax, float* ay, float* az,
                   float* gx, float* gy, float* gz) {
    uint8_t buf[14];
    readRegs(MPU6050_ACCEL_X, buf, 14);

    // 加速度（原始值 → g）
    int16_t raw_ax = (buf[0]  << 8) | buf[1];
    int16_t raw_ay = (buf[2]  << 8) | buf[3];
    int16_t raw_az = (buf[4]  << 8) | buf[5];
    // 温度（跳过 buf[6-7]）
    // 陀螺仪（原始值 → °/s）
    int16_t raw_gx = (buf[8]  << 8) | buf[9];
    int16_t raw_gy = (buf[10] << 8) | buf[11];
    int16_t raw_gz = (buf[12] << 8) | buf[13];

    *ax = raw_ax / _accel_scale - _aox;
    *ay = raw_ay / _accel_scale - _aoy;
    *az = raw_az / _accel_scale - _aoz;
    *gx = raw_gx / _gyro_scale  - _gox;
    *gy = raw_gy / _gyro_scale  - _goy;
    *gz = raw_gz / _gyro_scale  - _goz;

    return true;
}

// ── I2C 底层 ──

void MPU6050::writeReg(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(_addr);
    Wire.write(reg);
    Wire.write(val);
    Wire.endTransmission(true);
}

uint8_t MPU6050::readReg(uint8_t reg) {
    Wire.beginTransmission(_addr);
    Wire.write(reg);
    Wire.endTransmission(false);
    Wire.requestFrom((int)_addr, 1);
    return Wire.read();
}

void MPU6050::readRegs(uint8_t reg, uint8_t* buf, size_t len) {
    Wire.beginTransmission(_addr);
    Wire.write(reg);
    Wire.endTransmission(false);
    Wire.requestFrom((int)_addr, len);
    for (size_t i = 0; i < len; i++) {
        buf[i] = Wire.read();
    }
}
