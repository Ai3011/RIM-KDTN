#include <cstdint>
#include <vector>
#include <windows.h>
#include <iostream>
#include <cstring>

#ifdef BUILD_DLL
    #define EXPORT __declspec(dllexport)
#else
    #define EXPORT __declspec(dllimport)
#endif

using namespace std;

// ------------------------------------------------------------------
// Возвращает паузу между отправкой и приёмом для RS-485
// ------------------------------------------------------------------
DWORD calculate_timeout() { return 5; }

// ------------------------------------------------------------------
// Вычисление CRC-16 Modbus (полином 0xA001)
// ------------------------------------------------------------------
uint16_t crc16(const uint8_t* data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) {
            if (crc & 0x0001) {
                crc = (crc >> 1) ^ 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc;
}

// ------------------------------------------------------------------
// Запрос 0x00 – получение серийного номера, сборки, версии и типа устройства
// ------------------------------------------------------------------
void make_read_device_info_request(uint32_t device_addr, vector<uint8_t>& out_packet) {
    out_packet.clear();
    out_packet.resize(7);
    out_packet[0] = static_cast<uint8_t>(device_addr & 0xFF);
    out_packet[1] = static_cast<uint8_t>((device_addr >> 8) & 0xFF);
    out_packet[2] = static_cast<uint8_t>((device_addr >> 16) & 0xFF);
    out_packet[3] = 0x00;
    out_packet[4] = 0x02;
    uint16_t crc = crc16(out_packet.data(), 5);
    out_packet[5] = static_cast<uint8_t>(crc & 0xFF);
    out_packet[6] = static_cast<uint8_t>((crc >> 8) & 0xFF);
}

// ------------------------------------------------------------------
// Запрос 0x7E – чтение напряжений, тока и температуры
// ------------------------------------------------------------------
void make_service_request(uint32_t device_addr, vector<uint8_t>& out_packet) {
    out_packet.clear();
    out_packet.resize(7);
    out_packet[0] = static_cast<uint8_t>(device_addr & 0xFF);
    out_packet[1] = static_cast<uint8_t>((device_addr >> 8) & 0xFF);
    out_packet[2] = static_cast<uint8_t>((device_addr >> 16) & 0xFF);
    out_packet[3] = 0x7E;
    out_packet[4] = 0x02;
    uint16_t crc = crc16(out_packet.data(), 5);
    out_packet[5] = static_cast<uint8_t>(crc & 0xFF);
    out_packet[6] = static_cast<uint8_t>((crc >> 8) & 0xFF);
}

// ------------------------------------------------------------------
// Широковещательный запрос 0x7F для чтения текущего адреса устройства
// ------------------------------------------------------------------
void make_read_address_request(vector<uint8_t>& out_packet) {
    out_packet.clear();
    out_packet.resize(7);
    out_packet[0] = 0x00;
    out_packet[1] = 0x00;
    out_packet[2] = 0x00;
    out_packet[3] = 0x7F;
    out_packet[4] = 0x02;
    uint16_t crc = crc16(out_packet.data(), 5);
    out_packet[5] = static_cast<uint8_t>(crc & 0xFF);
    out_packet[6] = static_cast<uint8_t>((crc >> 8) & 0xFF);
}

// ------------------------------------------------------------------
// Запрос 0x7F для записи нового адреса устройства
// ------------------------------------------------------------------
void make_write_address_request(uint32_t new_addr, vector<uint8_t>& out_packet) {
    out_packet.clear();
    out_packet.resize(7);
    out_packet[0] = static_cast<uint8_t>(new_addr & 0xFF);
    out_packet[1] = static_cast<uint8_t>((new_addr >> 8) & 0xFF);
    out_packet[2] = static_cast<uint8_t>((new_addr >> 16) & 0xFF);
    out_packet[3] = 0x7F;
    out_packet[4] = 0x02;
    uint16_t crc = crc16(out_packet.data(), 5);
    out_packet[5] = static_cast<uint8_t>(crc & 0xFF);
    out_packet[6] = static_cast<uint8_t>((crc >> 8) & 0xFF);
}

// ------------------------------------------------------------------
// Отправка запроса и чтение ответа через COM-порт
// ------------------------------------------------------------------
bool send_and_receive(const vector<uint8_t>& request, vector<uint8_t>& response, const char* com_port) {
    HANDLE hCom = CreateFileA(com_port,
                              GENERIC_READ | GENERIC_WRITE,
                              FILE_SHARE_READ | FILE_SHARE_WRITE,
                              NULL,
                              OPEN_EXISTING,
                              0,
                              NULL);
    if (hCom == INVALID_HANDLE_VALUE) return false;

    DCB dcb = {};
    dcb.DCBlength = sizeof(DCB);
    if (!GetCommState(hCom, &dcb)) { CloseHandle(hCom); return false; }
    dcb.BaudRate = CBR_57600;
    dcb.ByteSize = 8;
    dcb.Parity = NOPARITY;
    dcb.StopBits = ONESTOPBIT;
    dcb.fRtsControl = RTS_CONTROL_DISABLE;
    dcb.fDtrControl = DTR_CONTROL_DISABLE;
    if (!SetCommState(hCom, &dcb)) { CloseHandle(hCom); return false; }

    COMMTIMEOUTS timeouts = {};
    timeouts.ReadIntervalTimeout = 10;
    timeouts.ReadTotalTimeoutConstant = 200;
    timeouts.ReadTotalTimeoutMultiplier = 0;
    timeouts.WriteTotalTimeoutConstant = 100;
    timeouts.WriteTotalTimeoutMultiplier = 0;
    if (!SetCommTimeouts(hCom, &timeouts)) { CloseHandle(hCom); return false; }

    PurgeComm(hCom, PURGE_RXCLEAR | PURGE_TXCLEAR);
    Sleep(50);

    DWORD bytesWritten;
    if (!WriteFile(hCom, request.data(), request.size(), &bytesWritten, NULL) || bytesWritten != request.size()) {
        CloseHandle(hCom);
        return false;
    }

    Sleep(calculate_timeout());

    response.resize(32);
    DWORD bytesRead = 0;
    if (!ReadFile(hCom, response.data(), response.size(), &bytesRead, NULL)) {
        CloseHandle(hCom);
        return false;
    }
    response.resize(bytesRead);
    CloseHandle(hCom);
    return bytesRead > 0;
}

// ------------------------------------------------------------------
// Экспортируемые функции для вызова из Python
// ------------------------------------------------------------------
extern "C" {

    // Чтение информации об устройстве (0x00)
    EXPORT bool __cdecl read_device_info(uint32_t device_addr, const char* com_port, uint8_t* out_buffer, int* out_len) {
        vector<uint8_t> request;
        make_read_device_info_request(device_addr, request);
        vector<uint8_t> response;
        bool success = send_and_receive(request, response, com_port);
        if (success && !response.empty() && response.size() >= 12) {
            if (response.size() > *out_len) {
                *out_len = response.size();
                return false;
            }
            memcpy(out_buffer, response.data(), response.size());
            *out_len = static_cast<int>(response.size());
            return true;
        }
        *out_len = 0;
        return false;
    }

    // Чтение служебных параметров (0x7E)
    EXPORT bool __cdecl read_service_parameters(uint32_t device_addr, const char* com_port, uint8_t* out_buffer, int* out_len) {
        vector<uint8_t> request;
        make_service_request(device_addr, request);
        vector<uint8_t> response;
        bool success = send_and_receive(request, response, com_port);
        if (success && !response.empty() && response.size() >= 13) {
            if (response.size() > *out_len) {
                *out_len = response.size();
                return false;
            }
            memcpy(out_buffer, response.data(), response.size());
            *out_len = static_cast<int>(response.size());
            return true;
        }
        *out_len = 0;
        return false;
    }

    // Чтение адреса устройства (широковещательный 0x7F)
    EXPORT bool __cdecl read_device_address(const char* com_port, uint8_t* out_buffer, int* out_len) {
        vector<uint8_t> request;
        make_read_address_request(request);
        vector<uint8_t> response;
        bool success = send_and_receive(request, response, com_port);
        if (success && !response.empty() && response.size() >= 10) {
            if (response.size() > *out_len) {
                *out_len = response.size();
                return false;
            }
            memcpy(out_buffer, response.data(), response.size());
            *out_len = static_cast<int>(response.size());
            return true;
        }
        *out_len = 0;
        return false;
    }

    // Запись адреса устройства (0x7F)
    EXPORT bool __cdecl write_device_address(uint32_t new_addr, const char* com_port, uint8_t* out_buffer, int* out_len) {
        vector<uint8_t> request;
        make_write_address_request(new_addr, request);
        vector<uint8_t> response;
        bool success = send_and_receive(request, response, com_port);
        if (success && !response.empty() && response.size() >= 7) {
            if (response.size() > *out_len) {
                *out_len = response.size();
                return false;
            }
            memcpy(out_buffer, response.data(), response.size());
            *out_len = static_cast<int>(response.size());
            return true;
        }
        *out_len = 0;
        return false;
    }
}