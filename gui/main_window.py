from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QPushButton)
from PyQt5.QtCore import QTimer
from gui.sensor_widget import SensorWidget
from gui.settings_dialog import SettingsDialog
from database.db_manager import init_db, save_test_result, load_settings, save_settings
from backend.rs485_backend import RS485Backend, parse_response, parse_service_parameters, parse_address_response
from datetime import datetime
import os

# ------------------------------------------------------------------
# Главное окно приложения – управление датчиками, тестами, опросом
# ------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Мониторинг датчиков")
        self.setMinimumSize(1100, 750)
        self.showMaximized()

        # Инициализация БД и загрузка сохранённых настроек
        init_db()
        self.sensor_settings = load_settings()
        self.manual_mode = [s.get("manual_testing", False) for s in self.sensor_settings]

        # Состояние тестов для каждого датчика
        self.test_active = [False] * 4
        self.test_remaining_sec = [0] * 4
        self.current_serial = [None] * 4
        self.test_start_time = [None] * 4
        self.measurements = [[] for _ in range(4)]
        self.start_ionistor = [None] * 4
        self.start_battery = [None] * 4
        self.elapsed_seconds = [0] * 4
        self.is_automatic = [False] * 4
        self.test_finished = [False] * 4
        self.auto_started = [False] * 4

        # Инициализация C++ бекенда (DLL)
        dll_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rs485_backend.dll")
        self.backend = RS485Backend(dll_path)

        # Построение GUI
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Верхняя панель управления
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.settings_btn = QPushButton("⚙ Настройки")
        self.settings_btn.setFixedSize(100, 30)
        self.settings_btn.clicked.connect(self.open_settings)
        top_layout.addWidget(self.settings_btn)

        self.db_btn = QPushButton("📂 База данных")
        self.db_btn.setFixedSize(120, 30)
        self.db_btn.clicked.connect(self.open_database_viewer)
        top_layout.addWidget(self.db_btn)

        self.start_all_btn = QPushButton("▶ Запустить все")
        self.start_all_btn.setFixedSize(130, 30)
        self.start_all_btn.clicked.connect(self.start_all_tests)
        top_layout.addWidget(self.start_all_btn)

        self.stop_all_btn = QPushButton("⏹ Остановить все")
        self.stop_all_btn.setFixedSize(140, 30)
        self.stop_all_btn.clicked.connect(self.stop_all_tests)
        top_layout.addWidget(self.stop_all_btn)

        top_layout.addStretch()
        main_layout.addWidget(top_bar)

        # Сетка виджетов датчиков (2×2)
        grid = QGridLayout()
        grid.setSpacing(15)
        grid.setContentsMargins(0, 0, 0, 0)
        self.sensor_widgets = []
        for i in range(4):
            widget = SensorWidget(sensor_id=i+1)
            widget.start_test_clicked.connect(self.start_test_for_sensor)
            widget.stop_test_clicked.connect(self.stop_test_for_sensor)
            widget.repeat_test_clicked.connect(self.repeat_test_for_sensor)
            widget.manual_toggled.connect(lambda checked, idx=i: self.on_manual_toggled(idx, checked))
            row, col = divmod(i, 2)
            grid.addWidget(widget, row, col)
            grid.setRowStretch(row, 1)
            grid.setColumnStretch(col, 1)
            self.sensor_widgets.append(widget)
        main_layout.addLayout(grid)

        # Первичная загрузка информации о портах и длительности
        self.update_port_info_all()
        self.update_total_time_all()

        # Установка начальных режимов кнопок
        for i in range(4):
            self.sensor_widgets[i].set_manual_mode(self.manual_mode[i])
            self.sensor_widgets[i].update_buttons_state(test_active=False, test_finished=False)

        # Таймер для обновления тестов (каждую секунду)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_tests)
        self.timer.start(1000)

        # Таймер для периодического опроса устройств (каждые 10 секунд)
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_all_devices)
        self.poll_timer.start(10000)

        # Первый опрос и запуск автоматических тестов
        self.poll_all_devices()
        self.start_automatic_tests()

    # --------------------------------------------------------------
    # Очистка отображаемых данных датчика (при ошибке опроса)
    # --------------------------------------------------------------
    def clear_sensor_data(self, idx):
        self.sensor_widgets[idx].update_data(None, None, None, None)
        self.sensor_widgets[idx].update_temperature(None)
        self.sensor_widgets[idx].update_voltage_ranges(None, None, None, None)

    # --------------------------------------------------------------
    # Опрос всех датчиков: чтение адреса (при необходимости),
    # серийного номера и служебных параметров
    # --------------------------------------------------------------
    def poll_all_devices(self):
        for i in range(4):
            port = self.sensor_settings[i].get("port", "COM5")
            addr = self.sensor_settings[i].get("address", 0)

            # Если адрес не задан, пытаемся прочитать через широковещательный запрос
            if addr == 0:
                response = self.backend.read_address(port)
                if response:
                    detected_addr = parse_address_response(response)
                    if detected_addr is not None:
                        addr = detected_addr
                        self.sensor_settings[i]["address"] = addr
                        save_settings(self.sensor_settings)
                        print(f"Датчик {i+1}: адрес автоматически определён: {addr}")
                    else:
                        print(f"Датчик {i+1}: не удалось прочитать адрес (неверный ответ)")
                else:
                    print(f"Датчик {i+1}: устройство не ответило на запрос адреса")

            # Теперь опрашиваем устройство по известному адресу
            response = self.backend.read_device(addr, port)
            if response and len(response) >= 12:
                data = parse_response(response)
                if data:
                    self.current_serial[i] = data["serial"]
                    self.sensor_widgets[i].update_serial(data["serial"])
                    self.sensor_widgets[i].update_build_version(data["build"], data["version"])
                    self.sensor_widgets[i].update_device_type(data["device_type"])
                    self.update_service_params(i, addr, port)
                    print(f"Датчик {i+1}: SN={data['serial']}, build={data['build']}, version={data['version']}, type={data['device_type']}")
                else:
                    self.current_serial[i] = None
                    self.sensor_widgets[i].update_serial("--")
                    self.sensor_widgets[i].update_build_version(None, None)
                    self.sensor_widgets[i].update_device_type(None)
                    self.clear_sensor_data(i)
            else:
                self.current_serial[i] = None
                self.sensor_widgets[i].update_serial("--")
                self.sensor_widgets[i].update_build_version(None, None)
                self.sensor_widgets[i].update_device_type(None)
                self.clear_sensor_data(i)
                print(f"Не удалось опросить датчик {i+1} (порт {port}, адрес {addr})")
        self.start_automatic_tests()

    # --------------------------------------------------------------
    # Чтение служебных параметров (напряжения, ток, температура)
    # --------------------------------------------------------------
    def update_service_params(self, idx, addr, port):
        response = self.backend.read_service_params(addr, port)
        if response:
            data = parse_service_parameters(response)
            if data:
                self.sensor_widgets[idx].update_data(
                    data["voltage_supply"],
                    data["current_ma"] / 1000.0,
                    data["voltage_ionistor"],
                    data["voltage_battery"]
                )
                self.sensor_widgets[idx].update_temperature(data["temperature"])
                return data
        self.clear_sensor_data(idx)
        return None

    # --------------------------------------------------------------
    # Запуск автоматических тестов для датчиков без ручного режима
    # --------------------------------------------------------------
    def start_automatic_tests(self):
        for i in range(4):
            if (not self.auto_started[i] and not self.test_active[i] and 
                not self.manual_mode[i] and self.current_serial[i] is not None):
                self.start_test_for_sensor(i+1, automatic=True)
                self.auto_started[i] = True

    # --------------------------------------------------------------
    # Запуск теста для конкретного датчика
    # --------------------------------------------------------------
    def start_test_for_sensor(self, sensor_id, automatic=False):
        idx = sensor_id - 1
        if self.test_active[idx]:
            return
        if self.current_serial[idx] is None:
            print(f"Датчик {sensor_id}: серийный номер не определён, тест не запущен")
            return

        port = self.sensor_settings[idx].get("port", "COM5")
        addr = self.sensor_settings[idx].get("address", 896)
        data = self.update_service_params(idx, addr, port)
        if data is None:
            print(f"Не удалось получить начальные параметры для датчика {sensor_id}, тест не запущен")
            return

        self.start_ionistor[idx] = data["voltage_ionistor"]
        self.start_battery[idx] = data["voltage_battery"]

        self.elapsed_seconds[idx] = 0
        self.measurements[idx] = []
        self.sensor_widgets[idx].clear_graphs()

        self.test_start_time[idx] = datetime.now()
        duration_min = self.sensor_settings[idx]["duration_min"]
        self.test_remaining_sec[idx] = duration_min * 60
        self.test_active[idx] = True
        self.is_automatic[idx] = automatic
        self.test_finished[idx] = False

        self.sensor_widgets[idx].update_time_left(self.test_remaining_sec[idx])
        self.sensor_widgets[idx].update_test_result(None)

        self.measurements[idx].append((0, data["voltage_supply"], data["current_ma"]/1000.0,
                                       data["voltage_ionistor"], data["voltage_battery"]))
        self.sensor_widgets[idx].update_buttons_state(test_active=True)

        if not self.auto_started[idx]:
            self.auto_started[idx] = True

    # --------------------------------------------------------------
    # Остановка теста (по пользователю или по времени)
    # --------------------------------------------------------------
    def stop_test_for_sensor(self, sensor_id, user_initiated=True):
        idx = sensor_id - 1
        if not self.test_active[idx]:
            return

        end_time = datetime.now()
        start_time = self.test_start_time[idx]

        if start_time is not None:
            elapsed_sec = int(round((end_time - start_time).total_seconds()))
        else:
            elapsed_sec = int(self.sensor_settings[idx]["duration_min"] * 60)

        if len(self.measurements[idx]) > 0:
            last = self.measurements[idx][-1]
            end_ion = last[3]
            end_bat = last[4]
            voltage_supply = last[1]
            current_consume = last[2]
            first = self.measurements[idx][0]
            start_ion = first[3]
            start_bat = first[4]
        else:
            start_ion = self.start_ionistor[idx] or 0
            end_ion = start_ion
            start_bat = self.start_battery[idx] or 0
            end_bat = start_bat
            voltage_supply = 0.0
            current_consume = 0.0

        if user_initiated:
            test_result = "Прерван"
        else:
            ionistor_grew = end_ion > start_ion
            battery_grew = end_bat > start_bat
            if ionistor_grew and battery_grew:
                test_result = "Положительный"
            else:
                test_result = "Отрицательный"

        if self.current_serial[idx] is not None:
            serial = self.current_serial[idx]
            save_test_result(
                serial, test_result, start_ion, end_ion,
                start_bat, end_bat, voltage_supply, current_consume,
                elapsed_sec,
                start_time.isoformat() if start_time else None,
                end_time.isoformat(),
                self.measurements[idx]
            )

        self.test_active[idx] = False
        self.test_remaining_sec[idx] = 0
        self.test_finished[idx] = True

        self.sensor_widgets[idx].update_time_left(None)
        self.sensor_widgets[idx].update_test_result(
            test_result,
            start_ion, end_ion,
            start_bat, end_bat
        )
        self.sensor_widgets[idx].update_buttons_state(test_active=False, test_finished=True)

        if user_initiated:
            print(f"Тест датчика {sensor_id} прерван пользователем")
        else:
            print(f"Тест датчика {sensor_id} завершён по времени")

    # --------------------------------------------------------------
    # Повторный запуск теста (кнопка «Повтор»)
    # --------------------------------------------------------------
    def repeat_test_for_sensor(self, sensor_id):
        idx = sensor_id - 1
        if self.current_serial[idx] is None:
            print(f"Датчик {sensor_id}: серийный номер не определён, повтор теста невозможен")
            return
        self.start_test_for_sensor(sensor_id, automatic=False)

    # --------------------------------------------------------------
    # Запуск тестов для всех датчиков, у которых есть серийный номер
    # --------------------------------------------------------------
    def start_all_tests(self):
        started = 0
        for i in range(4):
            if not self.test_active[i] and self.current_serial[i] is not None:
                if self.manual_mode[i]:
                    self.start_test_for_sensor(i+1, automatic=False)
                else:
                    self.start_test_for_sensor(i+1, automatic=True)
                started += 1
        if started == 0:
            print("Нет датчиков для запуска (либо нет серийного номера, либо тесты уже активны)")
        else:
            print(f"Запущено тестов: {started}")

    # --------------------------------------------------------------
    # Остановка всех активных тестов
    # --------------------------------------------------------------
    def stop_all_tests(self):
        any_stopped = False
        for i in range(4):
            if self.test_active[i]:
                self.stop_test_for_sensor(i+1, user_initiated=True)
                any_stopped = True
        if not any_stopped:
            print("Нет активных тестов для остановки")
        else:
            print("Все тесты остановлены")

    # --------------------------------------------------------------
    # Обработка переключения ручного режима (чекбокс «Ручной»)
    # --------------------------------------------------------------
    def on_manual_toggled(self, idx, checked):
        self.manual_mode[idx] = checked
        self.sensor_settings[idx]["manual_testing"] = checked
        save_settings(self.sensor_settings)
        if not checked and not self.test_active[idx] and self.current_serial[idx] is not None and not self.auto_started[idx]:
            self.start_test_for_sensor(idx+1, automatic=True)
            self.auto_started[idx] = True
        else:
            self.sensor_widgets[idx].update_buttons_state(
                test_active=self.test_active[idx],
                test_finished=self.test_finished[idx]
            )

    # --------------------------------------------------------------
    # Опрос датчика во время теста (каждую секунду)
    # --------------------------------------------------------------
    def poll_sensor(self, idx, is_first=False):
        if not self.test_active[idx]:
            return
        self.elapsed_seconds[idx] += 1
        sec = self.elapsed_seconds[idx]
        port = self.sensor_settings[idx].get("port", "COM5")
        addr = self.sensor_settings[idx].get("address", 896)
        data = self.update_service_params(idx, addr, port)
        if data:
            voltage = data["voltage_supply"]
            current = data["current_ma"] / 1000.0
            ionistor = data["voltage_ionistor"]
            battery = data["voltage_battery"]
            temp = data["temperature"]
            self.sensor_widgets[idx].update_data(voltage, current, ionistor, battery)
            self.sensor_widgets[idx].update_temperature(temp)
            self.measurements[idx].append((sec, voltage, current, ionistor, battery))
            self.sensor_widgets[idx].update_graphs(self.measurements[idx])
            if is_first:
                self.start_ionistor[idx] = ionistor
                self.start_battery[idx] = battery
        else:
            print(f"Не удалось получить параметры для датчика {idx+1} на секунде {sec}")

    # --------------------------------------------------------------
    # Обновление состояния всех активных тестов (вызывается по таймеру)
    # --------------------------------------------------------------
    def update_tests(self):
        for i in range(4):
            if self.test_active[i]:
                if self.test_remaining_sec[i] > 0:
                    self.test_remaining_sec[i] -= 1
                    self.sensor_widgets[i].update_time_left(self.test_remaining_sec[i])
                    self.poll_sensor(i)
                    if self.test_remaining_sec[i] == 0:
                        self.stop_test_for_sensor(i+1, user_initiated=False)
                else:
                    self.stop_test_for_sensor(i+1, user_initiated=False)

    # --------------------------------------------------------------
    # Открытие диалога настроек
    # --------------------------------------------------------------
    def open_settings(self):
        self.sensor_settings = load_settings()
        dialog = SettingsDialog(self.sensor_settings, self.current_serial, self)
        dialog.settings_changed.connect(self.save_all_settings)
        if dialog.exec_():
            new_settings = dialog.get_settings()
            for i in range(4):
                self.sensor_settings[i]["port"] = new_settings[i]["port"]
                self.sensor_settings[i]["baud"] = new_settings[i]["baud"]
                self.sensor_settings[i]["duration_min"] = new_settings[i]["duration_min"]
            save_settings(self.sensor_settings)
            self.update_port_info_all()
            self.update_total_time_all()
            self.manual_mode = [s.get("manual_testing", False) for s in self.sensor_settings]
            for i in range(4):
                self.sensor_widgets[i].set_manual_mode(self.manual_mode[i])
                self.sensor_widgets[i].update_buttons_state(
                    test_active=self.test_active[i],
                    test_finished=self.test_finished[i]
                )
                self.sensor_widgets[i].update_test_result(None)
            for i in range(4):
                self.auto_started[i] = False
            self.poll_all_devices()
            print("Настройки обновлены, выполнен опрос устройств")

    # --------------------------------------------------------------
    # Сохранение настроек из сигнала (при изменении в диалоге)
    # --------------------------------------------------------------
    def save_all_settings(self, new_settings):
        self.sensor_settings = new_settings
        save_settings(self.sensor_settings)
        self.update_port_info_all()
        self.update_total_time_all()
        print("Настройки сохранены в БД, порты и время обновлены")

    # --------------------------------------------------------------
    # Обновление информации о портах во всех виджетах
    # --------------------------------------------------------------
    def update_port_info_all(self):
        for i, widget in enumerate(self.sensor_widgets):
            if i < len(self.sensor_settings):
                port = self.sensor_settings[i].get("port", "--")
                baud = self.sensor_settings[i].get("baud", "--")
                widget.update_port_info(port, baud)

    # --------------------------------------------------------------
    # Обновление отображения длительности теста во всех виджетах
    # --------------------------------------------------------------
    def update_total_time_all(self):
        for i, widget in enumerate(self.sensor_widgets):
            if i < len(self.sensor_settings):
                duration_min = self.sensor_settings[i].get("duration_min", None)
                widget.update_total_time(duration_min)

    # --------------------------------------------------------------
    # Открытие окна просмотра базы данных
    # --------------------------------------------------------------
    def open_database_viewer(self):
        from gui.database_viewer import DatabaseViewer
        viewer = DatabaseViewer(self)
        viewer.exec_()