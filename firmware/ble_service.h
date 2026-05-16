#ifndef BLE_SERVICE_H
#define BLE_SERVICE_H

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>

/*
  V2 BLE 服务 — 单特征值协议
  
  服务 UUID: FF00
  特征值:    FF01 (Notify) — 状态包
    0xAA + 扇区索引(1B)  激活期间实时扇区
    0xBB + 最终扇区(1B)  确认执行
  
  注意：所有 BLE 操作只在 Core 1 上执行。
*/

#define SERVICE_UUID     "0000FF00-0000-1000-8000-00805F9B34FB"
#define CHAR_STATE_UUID  "0000FF01-0000-1000-8000-00805F9B34FB"


class BLEServiceManager {
public:
    void begin(const char* deviceName);
    
    // 线程安全发送（由 Core 1 调用）
    void sendSector(uint8_t sector);
    void sendAim(int8_t roll, int8_t pitch);  // 2D 瞄准
    void sendConfirm(uint8_t sector);
    
    bool isConnected() const { return _connected; }

private:
    BLEServer*           _server = nullptr;
    BLECharacteristic*   _charState = nullptr;
    volatile bool        _connected = false;

    class ServerCB : public BLEServerCallbacks {
    public:
        ServerCB(volatile bool* flag) : _flag(flag) {}
        void onConnect(BLEServer* s) override { *_flag = true; }
        void onDisconnect(BLEServer* s) override { *_flag = false; }
    private:
        volatile bool* _flag;
    };
};

#endif
