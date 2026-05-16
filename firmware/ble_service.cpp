#include "ble_service.h"

void BLEServiceManager::begin(const char* deviceName) {
    BLEDevice::init(deviceName);
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

void BLEServiceManager::sendSector(uint8_t sector) {
    if (!_connected || !_charState) return;
    uint8_t data[2] = { 0xAA, sector };
    _charState->setValue(data, 2);
    _charState->notify();
}

void BLEServiceManager::sendConfirm(uint8_t sector) {
    if (!_connected || !_charState) return;
    uint8_t data[2] = { 0xBB, sector };
    _charState->setValue(data, 2);
    _charState->notify();
}
