#include "feedback.h"

FeedbackController::FeedbackController(int pinR, int pinG, int pinBuzz)
    : _pinR(pinR), _pinG(pinG), _pinBuzz(pinBuzz) {}

void FeedbackController::begin() {
    pinMode(_pinR, OUTPUT);
    pinMode(_pinG, OUTPUT);
    pinMode(_pinBuzz, OUTPUT);
    digitalWrite(_pinR, LOW);
    digitalWrite(_pinG, LOW);
    digitalWrite(_pinBuzz, LOW);
}

// ── 快捷 LED ──

void FeedbackController::led_off() {
    _led_color = LED_OFF;
    _led_mode  = LED_MODE_OFF;
    _setLED(false, false);
}

void FeedbackController::led_red() {
    _led_color = LED_RED;
    _led_mode  = LED_MODE_SOLID;
    _setLED(true, false);
}

void FeedbackController::led_green() {
    _led_color = LED_GREEN;
    _led_mode  = LED_MODE_SOLID;
    _setLED(false, true);
}

void FeedbackController::led_blink(int ms) {
    _led_mode = LED_MODE_SLOW;
    _led_period = ms * 2;
    _led_last_toggle = millis();
    _led_on = true;
    _setLED(true, true);
}

void FeedbackController::set_connected(bool c) {
    if (c == _connected) return;
    _connected = c;
    if (c) {
        led_green();
    } else {
        led_blink(500);
    }
}

// ── 解析 BLE 指令 ──

void FeedbackController::handle_command(uint8_t* cmd) {
    // Byte 0:  LED 模式
    _led_color = cmd[0] & 0xF0;
    _led_mode  = cmd[0] & 0x0F;

    // Byte 1: 蜂鸣
    if (cmd[1] & BUZZ_SHORT) {
        _buzz(80);
    } else if (cmd[1] & BUZZ_LONG) {
        _buzz(300);
    } else if (cmd[1] & BUZZ_PULSE) {
        _buzz(150);
    }

    // Byte 2: 状态码（预留）
    (void)cmd[2];

    // 立即应用 LED
    _led_last_toggle = millis();
    _led_on = true;
}

// ── 每帧更新 ──

void FeedbackController::update(unsigned long now) {
    switch (_led_mode) {
        case LED_MODE_OFF:
            _setLED(false, false);
            break;

        case LED_MODE_SOLID:
            if (_led_color == LED_RED)       _setLED(true, false);
            else if (_led_color == LED_GREEN) _setLED(false, true);
            else if (_led_color == LED_YELLOW) _setLED(true, true);
            else _setLED(false, false);
            break;

        case LED_MODE_SLOW:
            if (now - _led_last_toggle > 500) {
                _led_on = !_led_on;
                _led_last_toggle = now;
                if (_led_color == LED_RED)       _setLED(_led_on, false);
                else if (_led_color == LED_GREEN) _setLED(false, _led_on);
                else _setLED(_led_on, _led_on);
            }
            break;

        case LED_MODE_FAST:
            if (now - _led_last_toggle > 160) {
                _led_on = !_led_on;
                _led_last_toggle = now;
                if (_led_color == LED_RED)       _setLED(_led_on, false);
                else if (_led_color == LED_GREEN) _setLED(false, _led_on);
                else _setLED(_led_on, _led_on);
            }
            break;

        case LED_MODE_PULSE:
            // 简单的 PWM 呼吸（非阻塞）
            if (now - _led_last_toggle > 5) {
                _led_last_toggle = now;
                _pwm_val += _pwm_dir;
                if (_pwm_val >= 255 || _pwm_val <= 0) _pwm_dir = -_pwm_dir;
                analogWrite(_pinR, _pwm_val);
            }
            break;
    }
}

// ── 底层 ──

void FeedbackController::_setLED(bool r, bool g) {
    digitalWrite(_pinR, r ? HIGH : LOW);
    digitalWrite(_pinG, g ? HIGH : LOW);
}

void FeedbackController::_buzz(int ms) {
    digitalWrite(_pinBuzz, HIGH);
    delay(ms);
    digitalWrite(_pinBuzz, LOW);
}
