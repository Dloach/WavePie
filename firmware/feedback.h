#ifndef FEEDBACK_H
#define FEEDBACK_H

#include <Arduino.h>

/*
  LED + 蜂鸣器反馈控制。

  LED 模式:
    - 关闭
    - 常亮（红/绿/黄）
    - 慢闪（1Hz）/ 快闪（3Hz）
    - 呼吸（PWM 渐变）

  蜂鸣器:
    - 短鸣 / 长鸣 / 脉冲

  接收 PC 发来的 4 字节指令:
    Byte 0: LED 模式 (高4位=颜色, 低4位=模式)
    Byte 1: 蜂鸣 (bit0=单鸣, bit1=脉冲)
    Byte 2: 状态码 (0=正常)
    Byte 3: 预留
*/

// LED 颜色
#define LED_OFF   0x00
#define LED_RED   0x10
#define LED_GREEN 0x20
#define LED_BLUE  0x30
#define LED_YELLOW 0x40

// LED 模式
#define LED_MODE_OFF    0x0
#define LED_MODE_SOLID  0x1
#define LED_MODE_SLOW   0x2   // 1Hz
#define LED_MODE_FAST   0x3   // 3Hz
#define LED_MODE_PULSE  0x4   // 呼吸

// 蜂鸣
#define BUZZ_SHORT  0x01
#define BUZZ_LONG   0x02
#define BUZZ_PULSE  0x04

class FeedbackController {
public:
    FeedbackController(int pinR, int pinG, int pinBuzz);

    void begin();

    // 快捷方法
    void led_off();
    void led_red();
    void led_green();
    void led_blink(int ms = 500);  // 闪烁一次

    // 连接状态（空闲时慢闪）
    void set_connected(bool connected);

    // 解析并执行 4 字节 BLE 指令
    void handle_command(uint8_t* cmd);

    // 每帧调用更新 LED（在 loop 中调用）
    void update(unsigned long now_ms);

private:
    int _pinR, _pinG, _pinBuzz;
    bool _connected = false;

    // LED 状态
    uint8_t _led_color = LED_OFF;
    uint8_t _led_mode  = LED_MODE_OFF;
    unsigned long _led_period = 0;  // ms
    unsigned long _led_last_toggle = 0;
    bool _led_on = false;

    // PWM 呼吸
    int _pwm_val = 0;
    int _pwm_dir = 1;

    void _setLED(bool r, bool g);
    void _buzz(int ms);
};

#endif
