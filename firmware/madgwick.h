#ifndef MADGWICK_H
#define MADGWICK_H

#include <Arduino.h>
#include <math.h>

/*
  Madgwick 姿态滤波——输入陀螺仪+加速度计，输出四元数。

  使用方式:
    Madgwick filter;
    filter.update(gx, gy, gz, ax, ay, az, dt);
    float roll  = filter.roll();    // 度
    float pitch = filter.pitch();
    float yaw   = filter.yaw();
    // 或直接操作 q[4]
*/

class Madgwick {
public:
    // 初始四元数 [1, 0, 0, 0]（水平静止）
    Madgwick() { reset(); }

    void reset() {
        q[0] = 1.0f; q[1] = 0.0f; q[2] = 0.0f; q[3] = 0.0f;
        beta = 0.1f;  // 增益——越大越依赖加速度计，0.1 是典型值
    }

    // 核心更新：gyro = °/s, accel = g, dt = 秒
    void update(float gx, float gy, float gz,
                float ax, float ay, float az,
                float dt) {

        // 归一化加速度计
        float norm = sqrtf(ax*ax + ay*ay + az*az);
        if (norm < 0.001f) return;
        ax /= norm; ay /= norm; az /= norm;

        // 四元数导数（陀螺仪积分项）
        float q0 = q[0], q1 = q[1], q2 = q[2], q3 = q[3];
        float qDot1 = 0.5f * (-q1*gx - q2*gy - q3*gz);
        float qDot2 = 0.5f * ( q0*gx + q2*gz - q3*gy);
        float qDot3 = 0.5f * ( q0*gy - q1*gz + q3*gx);
        float qDot4 = 0.5f * ( q0*gz + q1*gy - q2*gx);

        // 加速度计校正（梯度下降法）
        float f1 = 2.0f*(q1*q3 - q0*q2) - ax;
        float f2 = 2.0f*(q0*q1 + q2*q3) - ay;
        float f3 = 2.0f*(0.5f - q1*q1 - q2*q2) - az;

        float J11 = -2.0f*q2, J12 = 2.0f*q3, J13 = -2.0f*q0, J14 = 2.0f*q1;
        float J21 = 2.0f*q1,  J22 = 2.0f*q0,  J23 = 2.0f*q3,  J24 = 2.0f*q2;
        float J31 = 0.0f,     J32 = -4.0f*q1, J33 = -4.0f*q2, J34 = 0.0f;

        float s0 = J11*f1 + J21*f2 + J31*f3;
        float s1 = J12*f1 + J22*f2 + J32*f3;
        float s2 = J13*f1 + J23*f2 + J33*f3;
        float s3 = J14*f1 + J24*f2 + J34*f3;
        norm = sqrtf(s0*s0 + s1*s1 + s2*s2 + s3*s3);
        if (norm > 0.001f) {
            s0 /= norm; s1 /= norm; s2 /= norm; s3 /= norm;
            qDot1 -= beta * s0;
            qDot2 -= beta * s1;
            qDot3 -= beta * s2;
            qDot4 -= beta * s3;
        }

        // 积分
        q[0] += qDot1 * dt;
        q[1] += qDot2 * dt;
        q[2] += qDot3 * dt;
        q[3] += qDot4 * dt;
        norm = sqrtf(q[0]*q[0] + q[1]*q[1] + q[2]*q[2] + q[3]*q[3]);
        if (norm > 0.001f) {
            q[0] /= norm; q[1] /= norm; q[2] /= norm; q[3] /= norm;
        }
    }

    // 从四元数提取欧拉角（度）
    float roll()  const { return atan2f(2.0f*(q[0]*q[1] + q[2]*q[3]), 1.0f - 2.0f*(q[1]*q[1] + q[2]*q[2])) * 180.0f / M_PI; }
    float pitch() const { return asinf(2.0f*(q[0]*q[2] - q[3]*q[1])) * 180.0f / M_PI; }
    float yaw()   const { return atan2f(2.0f*(q[0]*q[3] + q[1]*q[2]), 1.0f - 2.0f*(q[2]*q[2] + q[3]*q[3])) * 180.0f / M_PI; }

    // 从四元数提取"水平指向角"——绕重力轴的旋转（yaw），但基于 q 计算
    float heading() const {
        return atan2f(2.0f*(q[0]*q[3] + q[1]*q[2]),
                      1.0f - 2.0f*(q[2]*q[2] + q[3]*q[3])) * 180.0f / M_PI;
    }

    // 原始四元数
    float q[4];

    // 设置增益
    void setBeta(float b) { beta = b; }

private:
    float beta;
};

#endif
