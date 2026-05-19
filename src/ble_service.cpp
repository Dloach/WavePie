#include "ble_service.h"

void BLEServiceManager::begin(const char* deviceName) {
    BLEDevice::init(deviceName);
    Serial.printf("[BLE] 设备名: %s\n", deviceName);
    _server = BLEDevice::createServer();
    _server->setCallbacks(new ServerCB(&_connected));

    BLEService* svc = _server->createService(SERVICE_UUID);

    _charState = svc->createCharacteristic(
        CHAR_STATE_UUID,
        BLECharacteristic::PROPERTY_NOTIFY
    );
    _charState->addDescriptor(new BLE2902());

    svc->start();

    BLEAdvertising* adv = BLEDevice::getAdvertising();
    adv->addServiceUUID(SERVICE_UUID);
    adv->start();
}



void BLEServiceManager::sendAim(int8_t roll, int8_t pitch) {
    if (!_connected || !_charState) return;
    // 限速 ~100Hz（10ms 间隔）
    static unsigned long last = 0;
    unsigned long now = millis();
    if (now - last < 10) return;
    last = now;
    uint8_t data[3] = { 0xAA, (uint8_t)roll, (uint8_t)pitch };
    _charState->setValue(data, 3);
    _charState->notify();
}

void BLEServiceManager::sendConfirm(uint8_t sector) {
    if (!_connected || !_charState) return;
    uint8_t data[2] = { 0xBB, sector };
    _charState->setValue(data, 2);
    _charState->notify();
}

void BLEServiceManager::sendSector(uint8_t sector) {
    if (!_connected || !_charState) return;
    uint8_t data[2] = { 0xAA, sector };
    _charState->setValue(data, 2);
    _charState->notify();
}
