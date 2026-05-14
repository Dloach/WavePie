#ifndef BLE_SERVICE_H
#define BLE_SERVICE_H

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>

/*
  BLE GATT 服务:
  自定义服务 UUID:   FF00...
  
  特征值:
  - Button:  FF01 (Notify)   2 bytes: 按键状态
  - IMU:     FF02 (Notify)   12 bytes: roll(float)+pitch(float)+yaw(float)
  - Scroll:  FF03 (Notify)   1 byte:   滚轮增量
  - Feedback: FF10 (Write)   4 bytes:  LED/蜂鸣/状态码
*/

// ── UUID ──
#define SERVICE_UUID        "0000FF00-0000-1000-8000-00805F9B34FB"
#define CHAR_BUTTON_UUID    "0000FF01-0000-1000-8000-00805F9B34FB"
#define CHAR_IMU_UUID       "0000FF02-0000-1000-8000-00805F9B34FB"
#define CHAR_SCROLL_UUID    "0000FF03-0000-1000-8000-00805F9B34FB"
#define CHAR_FEEDBACK_UUID  "0000FF10-0000-1000-8000-00805F9B34FB"

// ── 回调：处理 BLE 写入（PC→设备）──
class FeedbackCallback : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* c) override;
};

class BLEServiceManager {
public:
    void begin(const char* deviceName);
    void update();

    // 连接状态
    bool isConnected() const { return _connected; }

    // ── 发送（设备→PC）──
    void sendButton(uint8_t id, bool pressed, bool isLong);
    void sendIMU(float roll, float pitch, float yaw);
    void sendScroll(int8_t delta);

    // ── 接收（PC→设备）──
    bool readFeedback(uint8_t* out);

private:
    BLEServer*           _server = nullptr;
    BLECharacteristic*   _charButton   = nullptr;
    BLECharacteristic*   _charIMU      = nullptr;
    BLECharacteristic*   _charScroll   = nullptr;
    BLECharacteristic*   _charFeedback = nullptr;
    FeedbackCallback     _fbCallback;
    bool                 _connected = false;

    // 反馈数据缓冲区
    uint8_t _feedback_buf[4] = {0};
    bool    _feedback_pending = false;

    friend class FeedbackCallback;
};

#endif
