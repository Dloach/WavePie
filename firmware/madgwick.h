#ifndef MADGWICK_H
#define MADGWICK_H

#include <Arduino.h>
#include <math.h>

/*
  Madgwick 姿态滤波——输入陀螺仪+加速度计，输出四元数。
  算法参考: S. O. H. Madgwick, "An efficient orientation filter for
  inertial and inertial/magnetic sensor arrays", 2010.
*/

class Madgwick {
public:
    // 初始四元数 [1, 0, 0, 0]（水平静止）
    Madgwick() { reset(); }

    void reset() {
        q0 = 1.0f; q1 = 0.0f; q2 = 0.0f; q3 = 0.0f;
        beta = 0.1f;
    }

    // 核心更新：gyro = °/s, accel = g, dt = 秒
    void update(float gx, float gy, float gz,
                float ax, float ay, float az,
                float dt) {

        // 归一化加速度计测量值
        float norm = sqrtf(ax*ax + ay*ay + az*az);
        if (norm < 0.001f) return;
        ax /= norm; ay /= norm; az /= norm;

        float qw = q[0], qx = q[1], qy = q[2], qz = q[3];

        // 四元数导数 = 0.5 * q ⊗ ω（陀螺仪积分项）
        float qd0 = 0.5f * (-qx*gx - qy*gy - qz*gz);
        float qd1 = 0.5f * ( qw*gx + qz*gy - qy*gz);
        float qd2 = 0.5f * ( qw*gy - qx*gz + qz*gx);
        float qd3 = 0.5f * ( qw*gz + qx*gy - qy*gx);

        // 加速度计辅助校正（梯度下降法）
        // 误差: f = q* ⊗ [0,0,0,1] ⊗ q - [ax,ay,az]
        float f1 = 2.0f*(qx*qz - qw*qy) - ax;
        float f2 = 2.0f*(qw*qx + qy*qz) - ay;
        float f3 = 2.0f*(0.5f - qx*qx - qy*qy) - az;

        // 雅可比矩阵 J = ∂f/∂q
        float J11=-2.0f*qy, J12=2.0f*qz, J13=-2.0f*qw, J14=2.0f*qx;
        float J21=2.0f*qx,  J22=2.0f*qw, J23=2.0f*qz,  J24=2.0f*qy;
        float J31=0.0f,     J32=-4.0f*qx,J33=-4.0f*qy, J34=0.0f;

        // 梯度 ∇ = J^T · f
        float s0 = J11*f1 + J21*f2 + J31*f3;
        float s1 = J12*f1 + J22*f2 + J32*f3;
        float s2 = J13*f1 + J23*f2 + J33*f3;
        float s3 = J14*f1 + J24*f2 + J34*f3;
        norm = sqrtf(s0*s0 + s1*s1 + s2*s2 + s3*s3);
        if (norm > 0.001f) {
            qd0 -= beta * (s0 / norm);
            qd1 -= beta * (s1 / norm);
            qd2 -= beta * (s2 / norm);
            qd3 -= beta * (s3 / norm);
        }

        // 显式积分 q += qDot * dt
        q[0] += qd0 * dt;
        q[1] += qd1 * dt;
        q[2] += qd2 * dt;
        q[3] += qd3 * dt;

        // 归一化
        norm = sqrtf(q[0]*q[0] + q[1]*q[1] + q[2]*q[2] + q[3]*q[3]);
        if (norm > 0.001f) {
            q[0] /= norm; q[1] /= norm; q[2] /= norm; q[3] /= norm;
        }
    }

    // ── 欧拉角（度）──

    float roll()  const {
        return atan2f(2.0f*(q0*q1 + q2*q3), 1.0f - 2.0f*(q1*q1 + q2*q2)) * 180.0f / M_PI;
    }

    float pitch() const {
        return asinf(2.0f*(q0*q2 - q3*q1)) * 180.0f / M_PI;
    }

    float yaw()   const {
        return atan2f(2.0f*(q0*q3 + q1*q2), 1.0f - 2.0f*(q2*q2 + q3*q3)) * 180.0f / M_PI;
    }

    // 原始四元数 [w, x, y, z]
    float q[4];

    void setBeta(float b) { beta = b; }

private:
    float beta;
};

#endif
