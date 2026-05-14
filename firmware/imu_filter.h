#ifndef IMU_FILTER_H
#define IMU_FILTER_H

#include <Arduino.h>
#include <math.h>

/*
  互补滤波——融合加速度计和陀螺仪数据，输出 roll/pitch/yaw。

  原理:
    - 陀螺仪短期准确但有漂移（高通）
    - 加速度计长期稳定但有噪声（低通）
    - 互补: 角度 = α × (角度 + 陀螺仪×dt) + (1-α) × 加速度计角度

  α 越接近 1 → 陀螺仪权重越大（响应快，但漂移多）
  α 越接近 0 → 加速度计权重越大（稳定，但响应慢）
  推荐 α = 0.96 ~ 0.98
*/

class ComplementaryFilter {
public:
    ComplementaryFilter(float alpha = 0.98f)
        : _alpha(alpha), roll(0), pitch(0), yaw(0) {}

    // 更新滤波器，dt 为时间步长（秒）
    void update(float ax, float ay, float az,
                float gx, float gy, float gz,
                float dt) {

        // 陀螺仪积分（角度增量）
        roll  += gx * dt;
        pitch += gy * dt;
        yaw   += gz * dt;

        // 从加速度计计算姿态（仅 roll, pitch）
        float accel_pitch = atan2f(-ax, sqrtf(ay * ay + az * az)) * 180.0f / M_PI;
        float accel_roll  = atan2f(ay, az) * 180.0f / M_PI;

        // 互补融合
        roll  = _alpha * roll  + (1.0f - _alpha) * accel_roll;
        pitch = _alpha * pitch + (1.0f - _alpha) * accel_pitch;

        // yaw 没有加速度计辅助，只用陀螺仪
        // （需要磁力计才能绝对定北）
    }

    // 重置
    void reset() {
        roll = pitch = yaw = 0;
    }

    // 输出姿态角（度）
    float roll;
    float pitch;
    float yaw;

private:
    float _alpha;
};

#endif
