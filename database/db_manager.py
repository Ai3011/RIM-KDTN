import sqlite3
import os
import sys
from datetime import datetime

# ------------------------------------------------------------------
# Определение пути к базе данных (рядом с .exe или в папке database)
# ------------------------------------------------------------------
def get_db_path():
    """Определяет путь к БД в зависимости от режима запуска (exe или исходник)"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(__file__)
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "sensors.db")

DB_PATH = get_db_path()

# ------------------------------------------------------------------
# Инициализация базы данных: создание таблиц и миграция
# ------------------------------------------------------------------
def init_db():
    """Создаёт таблицы test_results, measurements, settings, если их нет, и выполняет миграцию"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # ---------- Таблица test_results ----------
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_results'")
    table_exists = cursor.fetchone() is not None
    
    if not table_exists:
        cursor.execute('''
            CREATE TABLE test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial_number INTEGER NOT NULL,
                test_result TEXT,
                start_ionistor REAL,
                end_ionistor REAL,
                start_battery REAL,
                end_battery REAL,
                voltage_supply REAL,
                current_consume REAL,
                test_duration_sec INTEGER,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                is_valid INTEGER DEFAULT 0
            )
        ''')
    else:
        cursor.execute("PRAGMA table_info(test_results)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'test_result' not in columns: cursor.execute("ALTER TABLE test_results ADD COLUMN test_result TEXT")
        if 'start_ionistor' not in columns: cursor.execute("ALTER TABLE test_results ADD COLUMN start_ionistor REAL")
        if 'end_ionistor' not in columns: cursor.execute("ALTER TABLE test_results ADD COLUMN end_ionistor REAL")
        if 'start_battery' not in columns: cursor.execute("ALTER TABLE test_results ADD COLUMN start_battery REAL")
        if 'end_battery' not in columns: cursor.execute("ALTER TABLE test_results ADD COLUMN end_battery REAL")
        if 'voltage_supply' not in columns: cursor.execute("ALTER TABLE test_results ADD COLUMN voltage_supply REAL")
        if 'current_consume' not in columns: cursor.execute("ALTER TABLE test_results ADD COLUMN current_consume REAL")
        if 'test_duration_min' in columns and 'test_duration_sec' not in columns:
            cursor.execute("ALTER TABLE test_results ADD COLUMN test_duration_sec INTEGER")
            cursor.execute("UPDATE test_results SET test_duration_sec = CAST(test_duration_min * 60 AS INTEGER)")
        elif 'test_duration_sec' not in columns:
            cursor.execute("ALTER TABLE test_results ADD COLUMN test_duration_sec INTEGER")
        if 'end_time' not in columns and 'timestamp' not in columns:
            cursor.execute("ALTER TABLE test_results ADD COLUMN end_time TEXT")
            cursor.execute("UPDATE test_results SET end_time = start_time")
    
    # ---------- Таблица measurements (замеры по секундам) ----------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER,
            timestamp_sec INTEGER,
            voltage_supply REAL,
            current_consume REAL,
            voltage_ionistor REAL,
            voltage_battery REAL,
            FOREIGN KEY (test_id) REFERENCES test_results (id)
        )
    ''')
    
    # ---------- Таблица settings (настройки датчиков) ----------
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
    settings_exists = cursor.fetchone() is not None
    if not settings_exists:
        cursor.execute('''
            CREATE TABLE settings (
                sensor_id INTEGER PRIMARY KEY,
                port TEXT NOT NULL,
                baud INTEGER NOT NULL,
                duration_min REAL NOT NULL,
                manual_testing INTEGER DEFAULT 0,
                address INTEGER DEFAULT 0
            )
        ''')
    else:
        cursor.execute("PRAGMA table_info(settings)")
        cols = [col[1] for col in cursor.fetchall()]
        if 'manual_testing' not in cols:
            cursor.execute("ALTER TABLE settings ADD COLUMN manual_testing INTEGER DEFAULT 0")
        if 'address' not in cols:
            cursor.execute("ALTER TABLE settings ADD COLUMN address INTEGER DEFAULT 0")
    
    conn.commit()
    conn.close()

# ------------------------------------------------------------------
# Сохранение результатов теста и всех замеров
# ------------------------------------------------------------------
def save_test_result(serial_number, test_result, start_ionistor, end_ionistor, 
                     start_battery, end_battery, voltage_supply, current_consume,
                     duration_sec, start_time, end_time, measurements):
    """Сохраняет завершённый тест, обновляет is_valid, вставляет замеры"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE test_results SET is_valid = 0 WHERE serial_number = ?", (serial_number,))
    cursor.execute('''
        INSERT INTO test_results 
        (serial_number, test_result, start_ionistor, end_ionistor, 
         start_battery, end_battery, voltage_supply, current_consume,
         test_duration_sec, start_time, end_time, is_valid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    ''', (serial_number, test_result, start_ionistor, end_ionistor, 
          start_battery, end_battery, voltage_supply, current_consume,
          duration_sec, start_time, end_time))
    test_id = cursor.lastrowid
    for sec, v_supply, current, v_ion, v_bat in measurements:
        cursor.execute('''
            INSERT INTO measurements 
            (test_id, timestamp_sec, voltage_supply, current_consume, 
             voltage_ionistor, voltage_battery)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (test_id, sec, v_supply, current, v_ion, v_bat))
    conn.commit()
    conn.close()
    return test_id

# ------------------------------------------------------------------
# Получение последнего актуального результата для серийного номера
# ------------------------------------------------------------------
def get_last_valid_result(serial_number):
    """Возвращает последнюю запись с is_valid=1 для данного серийного номера"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, serial_number, test_result, start_ionistor, end_ionistor,
               start_battery, end_battery, voltage_supply, current_consume,
               test_duration_sec, start_time, end_time
        FROM test_results
        WHERE serial_number = ? AND is_valid = 1
        ORDER BY start_time DESC LIMIT 1
    ''', (serial_number,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "serial_number": row[1],
            "test_result": row[2],
            "start_ionistor": row[3],
            "end_ionistor": row[4],
            "start_battery": row[5],
            "end_battery": row[6],
            "voltage_supply": row[7],
            "current_consume": row[8],
            "test_duration_sec": row[9],
            "start_time": row[10],
            "end_time": row[11]
        }
    return None

# ------------------------------------------------------------------
# Получение всех результатов (опционально по серийному номеру)
# ------------------------------------------------------------------
def get_all_results(serial_number=None):
    """Возвращает все записи из test_results, сортированные по времени"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if serial_number is None:
        cursor.execute("SELECT * FROM test_results ORDER BY start_time DESC")
    else:
        cursor.execute("SELECT * FROM test_results WHERE serial_number = ? ORDER BY start_time DESC", (serial_number,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ------------------------------------------------------------------
# Получение замеров для конкретного теста
# ------------------------------------------------------------------
def get_measurements(test_id):
    """Возвращает все замеры (по секундам) для заданного test_id"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM measurements WHERE test_id = ? ORDER BY timestamp_sec", (test_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ------------------------------------------------------------------
# Загрузка настроек из таблицы settings
# ------------------------------------------------------------------
def load_settings():
    """Загружает настройки для всех датчиков (порт, скорость, длительность, ручной режим, адрес)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT sensor_id, port, baud, duration_min, manual_testing, address FROM settings ORDER BY sensor_id")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        cursor.execute("SELECT sensor_id, port, baud, duration_min, manual_testing FROM settings ORDER BY sensor_id")
        rows = [(row[0], row[1], row[2], row[3], row[4], 0) for row in cursor.fetchall()]
    conn.close()
    
    default_settings = [
        {"port": "", "baud": 0, "duration_min": 0, "manual_testing": False, "address": 0},
        {"port": "", "baud": 0, "duration_min": 0, "manual_testing": False, "address": 0},
        {"port": "", "baud": 0, "duration_min": 0, "manual_testing": False, "address": 0},
        {"port": "", "baud": 0, "duration_min": 0, "manual_testing": False, "address": 0},
    ]
    if not rows:
        return default_settings
    settings = []
    for row in rows:
        sensor_id, port, baud, duration_min, manual, address = row
        settings.append({
            "port": port,
            "baud": baud,
            "duration_min": duration_min,
            "manual_testing": bool(manual),
            "address": address
        })
    while len(settings) < 4:
        settings.append(default_settings[len(settings)])
    return settings

# ------------------------------------------------------------------
# Сохранение настроек в таблицу settings
# ------------------------------------------------------------------
def save_settings(settings_list):
    """Сохраняет настройки всех датчиков в БД (перезаписывает)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM settings")
    for idx, s in enumerate(settings_list, start=1):
        cursor.execute('''
            INSERT INTO settings (sensor_id, port, baud, duration_min, manual_testing, address)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (idx, s["port"], s["baud"], s["duration_min"], 
              1 if s.get("manual_testing", False) else 0,
              s.get("address", 0)))
    conn.commit()
    conn.close()