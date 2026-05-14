#ifndef BUTTONS_H
#define BUTTONS_H

#include <Arduino.h>

/*
  多按键管理（按下=低电平，带去抖+长按检测）。

  每个按键:
    - 去抖时间: 30ms
    - 长按阈值: 600ms
*/

#define DEBOUNCE_MS  30
#define LONG_PRESS_MS 600

struct ButtonEvent {
    uint8_t id;        // 按键编号
    bool    pressed;   // true=按下, false=松开
    bool    is_long;   // 是否为长按事件（仅 pressed=true 时有意义）
};

class ButtonManager {
public:
    ButtonManager() : _count(0) {}

    // 添加一个按键（pin: GPIO 编号, name: 调试用）
    void add(int pin, const char* name = "");

    // 读取已发生的事件，返回 false 表示无事件
    // 需要在 loop 中高频调用（如每 5-10ms）
    bool read(ButtonEvent* evt);

    // 按键数量
    int count() const { return _count; }

private:
    static constexpr int MAX_BUTTONS = 8;

    struct Button {
        int     pin;
        char    name[16];
        bool    last_state;     // 上次稳定状态 (true=按下)
        bool    raw_state;      // 当前原始电平 (LOW=按下)
        unsigned long last_change_ms;
        unsigned long press_start_ms;
        bool    long_reported;
        bool    event_pending;
        bool    event_pressed;
        bool    event_long;
    };

    Button _btns[MAX_BUTTONS];
    int    _count;

    int _read_index = 0;  // 轮询索引（多次调用分摊负载）
};

#endif
