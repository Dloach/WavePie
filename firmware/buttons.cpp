#include "buttons.h"

void ButtonManager::add(int pin, const char* name) {
    if (_count >= MAX_BUTTONS) return;

    pinMode(pin, INPUT_PULLUP);
    Button& b = _btns[_count];
    b.pin = pin;
    strncpy(b.name, name, sizeof(b.name) - 1);
    b.last_state = false;          // 初始=松开
    b.raw_state = false;
    b.last_change_ms = 0;
    b.press_start_ms = 0;
    b.long_reported = false;
    b.event_pending = false;
    b.event_pressed = false;
    b.event_long = false;
    _count++;
}

bool ButtonManager::read(ButtonEvent* evt) {
    unsigned long now = millis();

    // 一次只处理一个按键（分摊到多次调用）
    for (int r = 0; r < _count; r++) {
        int i = _read_index % _count;
        _read_index++;

        Button& b = _btns[i];
        bool raw = (digitalRead(b.pin) == LOW);

        // 电平变化 → 开始去抖计时
        if (raw != b.raw_state) {
            b.raw_state = raw;
            b.last_change_ms = now;
        }

        // 去抖稳定
        bool stable = (now - b.last_change_ms >= DEBOUNCE_MS);

        if (stable && raw != b.last_state) {
            b.last_state = raw;

            if (raw) {
                // 按下
                b.press_start_ms = now;
                b.long_reported = false;
                b.event_pending = true;
                b.event_pressed = true;
                b.event_long = false;
            } else {
                // 松开
                bool was_long = (now - b.press_start_ms >= LONG_PRESS_MS);
                b.event_pending = true;
                b.event_pressed = false;
                b.event_long = was_long;
                b.long_reported = false;
            }
        }

        // 长按检测（持续按住超过阈值）
        if (stable && raw && b.last_state && !b.long_reported) {
            if (now - b.press_start_ms >= LONG_PRESS_MS) {
                b.long_reported = true;
                b.event_pending = true;
                b.event_pressed = true;
                b.event_long = true;
            }
        }

        // 如果有待处理事件，返回
        if (b.event_pending) {
            b.event_pending = false;
            evt->id      = i;
            evt->pressed = b.event_pressed;
            evt->is_long = b.event_long;
            return true;
        }
    }

    return false;
}
