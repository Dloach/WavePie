#include "ble_service.h"

// ── 服务端回调：连接/断开 ──
class ServerCB : public BLEServerCallbacks {
public:
    ServerCB(bool* connected) : _conn(connected) {}
    void onConnect(BLEServer*) override {
        *_conn = true;
        Serial.println("[BLE] ✅ PC 已连接");
    }
    void onDisconnect(BLEServer* srv) override {
        *_conn = false;
        Serial.println("[BLE] ❌ PC 断开，开始广播...");
        srv->startAdvertising();
    }
private:
    bool* _conn;
};

// ── 反馈特征值写入回调 ──
void FeedbackCallback::onWrite(BLECharacteristic* c) {
    // 由 BLEServiceManager::readFeedback 读取
}

// ── 初始化 BLE ──
void BLEServiceManager::begin(const char* deviceName) {
    BLEDevice::init(deviceName);
    _server = BLEDevice::createServer();
    _server->setCallbacks(new ServerCB(&_connected));

    // 创建服务
    BLEService* svc = _server->createService(SERVICE_UUID);

    // 1. 按键特征值 (Notify)
    _charButton = svc->createCharacteristic(
        CHAR_BUTTON_UUID,
        BLECharacteristic::PROPERTY_NOTIFY
    );
    _charButton->addDescriptor(new BLE2902());
    _charButton->setValue((uint8_t*)"\x00\x00", 2);

    // 2. IMU 特征值 (Notify)
    _charIMU = svc->createCharacteristic(
        CHAR_IMU_UUID,
        BLECharacteristic::PROPERTY_NOTIFY
    );
    _charIMU->addDescriptor(new BLE2902());

    // 3. 滚轮特征值 (Notify)
    _charScroll = svc->createCharacteristic(
        CHAR_SCROLL_UUID,
        BLECharacteristic::PROPERTY_NOTIFY
    );
    _charScroll->addDescriptor(new BLE2902());

    // 4. 反馈特征值 (Write)
    _charFeedback = svc->createCharacteristic(
        CHAR_FEEDBACK_UUID,
        BLECharacteristic::PROPERTY_WRITE
    );
    _charFeedback->setCallbacks(&_fbCallback);

    // 启动服务
    svc->start();

    // 广播
    BLEAdvertising* adv = BLEDevice::getAdvertising();
    adv->addServiceUUID(SERVICE_UUID);
    adv->setScanResponse(true);
    adv->setMinPreferred(0x06);
    adv->setMinPreferred(0x12);
    BLEDevice::startAdvertising();

    Serial.printf("[BLE] 设备名: %s\n", deviceName);
    Serial.println("[BLE] 等待 PC 连接...");
}

// ── 更新（连接状态检查）──
void BLEServiceManager::update() {
    if (_charFeedback && _charFeedback->getValue().length() >= 4) {
        auto val = _charFeedback->getValue();
        memcpy(_feedback_buf, val.data(), min((size_t)4, val.length()));
        _feedback_pending = true;
        // 清空缓冲区，避免重复读取
        _charFeedback->setValue((uint8_t*)"\x00\x00\x00\x00", 4);
        _charFeedback->notify();
    }
}

// ── 发送按键事件 ──
void BLEServiceManager::sendButton(uint8_t id, bool pressed, bool isLong) {
    if (!_connected || !_charButton) return;
    uint8_t data[2] = { id, (uint8_t)(pressed | (isLong << 1)) };
    _charButton->setValue(data, 2);
    _charButton->notify();
}

// ── 发送 IMU 数据 ──
void BLEServiceManager::sendIMU(float roll, float pitch, float yaw) {
    if (!_connected || !_charIMU) return;
    uint8_t data[12];
    memcpy(data,      &roll,  4);
    memcpy(data + 4,  &pitch, 4);
    memcpy(data + 8,  &yaw,   4);
    _charIMU->setValue(data, 12);
    _charIMU->notify();
}

// ── 发送滚轮 ──
void BLEServiceManager::sendScroll(int8_t delta) {
    if (!_connected || !_charScroll) return;
    _charScroll->setValue((uint8_t*)&delta, 1);
    _charScroll->notify();
}

// ── 读取 PC 发来的反馈指令 ──
bool BLEServiceManager::readFeedback(uint8_t* out) {
    if (!_feedback_pending) return false;
    memcpy(out, _feedback_buf, 4);
    _feedback_pending = false;
    return true;
}
