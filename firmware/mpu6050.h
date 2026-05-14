#ifndef MPU6050_H
#define MPU6050_H

#include <Arduino.h>
#include <Wire.h>

/*
  MPU6050 6 轴 IMU 驱动（I2C）。

  接线:
    VCC → 3.3V
    GND → GND
    SDA → GPIO 21
    SCL → GPIO 22
*/

// MPU6050 寄存器地址
#define MPU6050_ADDR      0x68
#define MPU6050_WHO_AM_I  0x75
#define MPU6050_PWR_MGMT  0x6B
#define MPU6050_ACCEL_X   0x3B
#define MPU6050_GYRO_X    0x43
#define MPU6050_CONFIG    0x1A
#define MPU6050_GYRO_CFG  0x1B
#define MPU6050_ACCEL_CFG 0x1C

class MPU6050 {
public:
    MPU6050(uint8_t addr = MPU6050_ADDR);

    // 初始化，返回是否成功
    bool begin();

    // 校准（静止时调用，samples 次采样）
    void calibrate(int samples = 200);

    // 读取加速度 (g) 和陀螺仪 (度/秒)
    // 返回 true 表示成功
    bool read(float* ax, float* ay, float* az,
              float* gx, float* gy, float* gz);

    // 获取校准偏移（调试用）
    float getAccelOffsetX() const { return _aox; }
    float getGyroOffsetX()  const { return _gox; }

private:
    uint8_t _addr;
    float _aox = 0, _aoy = 0, _aoz = 0;  // 加速度零偏
    float _gox = 0, _goy = 0, _goz = 0;  // 陀螺仪零偏
    float _accel_scale = 16384.0f;        // ±2g
    float _gyro_scale  = 131.0f;          // ±250°/s

    // I2C 读写
    void writeReg(uint8_t reg, uint8_t val);
    uint8_t readReg(uint8_t reg);
    void readRegs(uint8_t reg, uint8_t* buf, size_t len);
};

#endif
