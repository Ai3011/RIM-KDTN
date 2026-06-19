import ctypes
from ctypes import c_uint32, c_int, c_bool, c_char_p, POINTER, c_ubyte

# ------------------------------------------------------------------
# Класс для работы с C++ DLL: загрузка, настройка типов аргументов,
# методы-обёртки для каждой экспортируемой функции.
# ------------------------------------------------------------------
class RS485Backend:
    def __init__(self, dll_path="rs485_backend.dll"):
        self.dll = ctypes.CDLL(dll_path)
        # Указываем типы аргументов и возвращаемые значения для функций DLL
        self.dll.read_device_info.argtypes = [c_uint32, c_char_p, POINTER(c_ubyte), POINTER(c_int)]
        self.dll.read_device_info.restype = c_bool

        self.dll.read_service_parameters.argtypes = [c_uint32, c_char_p, POINTER(c_ubyte), POINTER(c_int)]
        self.dll.read_service_parameters.restype = c_bool

        self.dll.read_device_address.argtypes = [c_char_p, POINTER(c_ubyte), POINTER(c_int)]
        self.dll.read_device_address.restype = c_bool

        self.dll.write_device_address.argtypes = [c_uint32, c_char_p, POINTER(c_ubyte), POINTER(c_int)]
        self.dll.write_device_address.restype = c_bool

    # ----- Обёртки для вызова функций DLL -----

    def read_device(self, addr, port):
        """Вызов read_device_info (команда 0x00) – возвращает сырые байты ответа"""
        buf = (ctypes.c_ubyte * 32)()
        length = c_int(32)
        if self.dll.read_device_info(addr, port.encode('utf-8'), buf, ctypes.byref(length)):
            return bytes(buf)[:length.value]
        return None

    def read_service_params(self, addr, port):
        """Вызов read_service_parameters (команда 0x7E) – служебные параметры"""
        buf = (ctypes.c_ubyte * 32)()
        length = c_int(32)
        if self.dll.read_service_parameters(addr, port.encode('utf-8'), buf, ctypes.byref(length)):
            return bytes(buf)[:length.value]
        return None

    def read_address(self, port):
        """Читает текущий адрес устройства через широковещательный запрос 0x7F"""
        buf = (ctypes.c_ubyte * 32)()
        length = c_int(32)
        if self.dll.read_device_address(port.encode('utf-8'), buf, ctypes.byref(length)):
            return bytes(buf)[:length.value]
        return None

    def write_address(self, new_addr, port):
        """Записывает новый адрес устройства через команду 0x7F"""
        buf = (ctypes.c_ubyte * 32)()
        length = c_int(32)
        if self.dll.write_device_address(new_addr, port.encode('utf-8'), buf, ctypes.byref(length)):
            return bytes(buf)[:length.value]
        return None


# ------------------------------------------------------------------
# Парсеры ответов от устройства
# ------------------------------------------------------------------

def parse_response(buffer):
    """
    Разбирает ответ на команду 0x00 (информация об устройстве).
    Возвращает словарь с серийным номером, сборкой, версией и типом.
    """
    if len(buffer) < 12:
        return None
    device_addr = buffer[0] | (buffer[1] << 8) | (buffer[2] << 16)
    build = buffer[5]
    version = buffer[6]
    device_type = (buffer[9] << 16) | (buffer[8] << 8) | buffer[7]
    type_num = 0
    type_num += ((buffer[9] >> 4) & 0x0F) * 100000
    type_num += (buffer[9] & 0x0F) * 10000
    type_num += ((buffer[8] >> 4) & 0x0F) * 1000
    type_num += (buffer[8] & 0x0F) * 100
    type_num += ((buffer[7] >> 4) & 0x0F) * 10
    type_num += (buffer[7] & 0x0F)
    return {
        "serial": device_addr,
        "build": ((build >> 4) & 0x0F) * 10 + (build & 0x0F),
        "version": ((version >> 4) & 0x0F) * 10 + (version & 0x0F),
        "device_type": type_num
    }

def parse_service_parameters(buffer):
    """
    Разбирает ответ на команду 0x7E (служебные параметры).
    Возвращает словарь с напряжениями, током (мА) и температурой.
    """
    if len(buffer) < 13:
        return None
    ionistor_raw = buffer[5]
    voltage_ionistor = ionistor_raw * 0.1
    supply_raw = buffer[6]
    voltage_supply = supply_raw * 0.1
    temp_raw = buffer[7]
    temp = temp_raw - 256 if temp_raw > 127 else temp_raw
    current_raw = buffer[8] | (buffer[9] << 8)
    current_ma = current_raw
    battery_raw = buffer[10]
    voltage_battery = battery_raw * 0.1
    return {
        "voltage_ionistor": voltage_ionistor,
        "voltage_supply": voltage_supply,
        "temperature": temp,
        "current_ma": current_ma,
        "voltage_battery": voltage_battery
    }

def parse_address_response(buffer):
    """
    Разбирает ответ на широковещательный запрос 0x7F (чтение адреса).
    Извлекает и возвращает адрес устройства как целое число.
    """
    if len(buffer) < 10:
        return None
    if buffer[3] != 0x7F or buffer[4] != 0x02:
        return None
    addr = buffer[5] | (buffer[6] << 8) | (buffer[7] << 16)
    return addr

def parse_write_address_response(buffer):
    """
    Проверяет ответ на команду 0x7F (запись адреса).
    Возвращает True при успехе, иначе None.
    """
    if len(buffer) < 7:
        return None
    if buffer[3] != 0x7F or buffer[4] != 0x02:
        return None
    return True