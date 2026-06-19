from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QPushButton, QHBoxLayout, QGridLayout, QCheckBox
from PyQt5.QtCore import Qt, pyqtSignal
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class SensorWidget(QFrame):
    start_test_clicked = pyqtSignal(int)
    stop_test_clicked = pyqtSignal(int)
    repeat_test_clicked = pyqtSignal(int)
    manual_toggled = pyqtSignal(bool)

    def __init__(self, sensor_id, parent=None):
        super().__init__(parent)
        self.sensor_id = sensor_id
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(2)
        self.default_color = "#f0f0f0"
        self._manual_mode = False

        # Главный вертикальный контейнер
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # --- Верхняя часть: информация (слева) и графики (справа) ---
        top_layout = QHBoxLayout()
        top_layout.setSpacing(15)

        # Левая колонка (информация)
        left_col = QVBoxLayout()
        left_col.setSpacing(5)

        self.label_name = QLabel(f"<b>Датчик {sensor_id}</b>")
        self.label_name.setStyleSheet("font-size: 14pt; font-weight: bold;")
        left_col.addWidget(self.label_name)

        self.label_serial = QLabel("Серийный номер: --")
        self.label_serial.setStyleSheet("font-size: 12pt; font-weight: bold; color: #333;")
        left_col.addWidget(self.label_serial)

        self.label_build_version = QLabel("Сборка: --, Версия: --")
        self.label_build_version.setStyleSheet("font-size: 10pt;")
        left_col.addWidget(self.label_build_version)

        self.label_device_type = QLabel("Тип: --")
        self.label_device_type.setStyleSheet("font-size: 10pt;")
        left_col.addWidget(self.label_device_type)

        self.label_temperature = QLabel("Температура: -- °C")
        self.label_temperature.setStyleSheet("font-size: 10pt; font-weight: bold;")
        left_col.addWidget(self.label_temperature)

        info_layout = QHBoxLayout()
        self.label_port_info = QLabel("Порт: --, Скорость: --")
        self.label_port_info.setStyleSheet("font-size: 10pt;")
        info_layout.addWidget(self.label_port_info)
        info_layout.addStretch()
        self.label_total_time = QLabel("Длительность: --")
        self.label_total_time.setStyleSheet("font-size: 10pt;")
        info_layout.addWidget(self.label_total_time)
        info_layout.addSpacing(10)
        self.manual_check = QCheckBox("Ручной")
        self.manual_check.stateChanged.connect(self.on_manual_toggled)
        info_layout.addWidget(self.manual_check)
        left_col.addLayout(info_layout)

        self.label_time_left = QLabel("Тест не активен")
        self.label_time_left.setStyleSheet("color: gray; font-size: 14pt; font-weight: bold;")
        left_col.addWidget(self.label_time_left)

        param_grid = QGridLayout()
        param_grid.setSpacing(4)
        self.label_voltage = QLabel("Напр: -- В")
        self.label_voltage.setStyleSheet("font-size: 12pt; font-weight: bold;")
        self.label_current = QLabel("Ток: -- А")
        self.label_current.setStyleSheet("font-size: 12pt; font-weight: bold;")
        self.label_ionistor = QLabel("Ионистор: -- В")
        self.label_ionistor.setStyleSheet("font-size: 12pt; font-weight: bold;")
        self.label_battery = QLabel("Аккум: -- В")
        self.label_battery.setStyleSheet("font-size: 12pt; font-weight: bold;")
        param_grid.addWidget(self.label_voltage, 0, 0)
        param_grid.addWidget(self.label_current, 0, 1)
        param_grid.addWidget(self.label_ionistor, 1, 0)
        param_grid.addWidget(self.label_battery, 1, 1)
        left_col.addLayout(param_grid)

        range_layout = QHBoxLayout()
        self.label_ionistor_range = QLabel("Ионистор: --→-- В")
        self.label_ionistor_range.setStyleSheet("font-size: 10pt;")
        self.label_battery_range = QLabel("Аккум: --→-- В")
        self.label_battery_range.setStyleSheet("font-size: 10pt;")
        range_layout.addWidget(self.label_ionistor_range)
        range_layout.addStretch()
        range_layout.addWidget(self.label_battery_range)
        left_col.addLayout(range_layout)

        left_col.addStretch()
        top_layout.addLayout(left_col, stretch=2)

        # Правая колонка (графики)
        right_col = QVBoxLayout()
        right_col.setSpacing(5)

        self.figure = Figure(figsize=(4, 3), dpi=80)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(200)

        self.ax_ionistor = self.figure.add_subplot(2, 1, 1)
        self.ax_battery = self.figure.add_subplot(2, 1, 2)

        self.ax_ionistor.set_title("Напряжение ионистора", fontsize=9)
        self.ax_ionistor.set_xlabel("Время, с", fontsize=8)
        self.ax_ionistor.set_ylabel("В", fontsize=8)
        self.ax_ionistor.tick_params(labelsize=7)
        self.ax_ionistor.grid(True, linestyle='--', alpha=0.5)

        self.ax_battery.set_title("Напряжение аккумулятора", fontsize=9)
        self.ax_battery.set_xlabel("Время, с", fontsize=8)
        self.ax_battery.set_ylabel("В", fontsize=8)
        self.ax_battery.tick_params(labelsize=7)
        self.ax_battery.grid(True, linestyle='--', alpha=0.5)

        self.line_ion, = self.ax_ionistor.plot([], [], 'b-', linewidth=1.5)
        self.line_bat, = self.ax_battery.plot([], [], 'r-', linewidth=1.5)

        self.figure.tight_layout(pad=0.8)
        right_col.addWidget(self.canvas)
        top_layout.addLayout(right_col, stretch=3)

        main_layout.addLayout(top_layout)

        # --- Нижняя часть: кнопки "Начать", "Стоп" и "Повтор" (по центру) ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)
        btn_layout.addStretch()

        # Кнопка "Начать" (синяя рамка) – такая же, как "Стоп" и "Повтор"
        self.start_btn = QPushButton("Начать")
        self.start_btn.setFixedSize(120, 50)
        self.start_btn.setStyleSheet("""
            font-size: 14pt; 
            font-weight: bold; 
            color: #2196F3; 
            background-color: transparent; 
            border: 2px solid #2196F3;
            border-radius: 6px;
        """)
        self.start_btn.setVisible(False)   # по умолчанию скрыта
        btn_layout.addWidget(self.start_btn)

        # Кнопка "Стоп" (красная рамка)
        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setFixedSize(120, 50)
        self.stop_btn.setStyleSheet("""
            font-size: 14pt; 
            font-weight: bold; 
            color: #f44336; 
            background-color: transparent; 
            border: 2px solid #f44336;
            border-radius: 6px;
        """)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        # Кнопка "Повтор" (зелёная рамка)
        self.repeat_btn = QPushButton("Повтор")
        self.repeat_btn.setFixedSize(120, 50)
        self.repeat_btn.setStyleSheet("""
            font-size: 14pt; 
            font-weight: bold; 
            color: #4CAF50; 
            background-color: transparent; 
            border: 2px solid #4CAF50;
            border-radius: 6px;
        """)
        self.repeat_btn.setEnabled(False)
        btn_layout.addWidget(self.repeat_btn)

        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # Подключение сигналов кнопок
        self.start_btn.clicked.connect(self.on_start_clicked)
        self.stop_btn.clicked.connect(self.on_stop_clicked)
        self.repeat_btn.clicked.connect(self.on_repeat_clicked)

        self.setStyleSheet(f"background-color: {self.default_color};")

    # --------------------------------------------------------------
    # Обработчики сигналов кнопок
    # --------------------------------------------------------------
    def on_start_clicked(self):
        self.start_test_clicked.emit(self.sensor_id)

    def on_stop_clicked(self):
        self.stop_test_clicked.emit(self.sensor_id)

    def on_repeat_clicked(self):
        self.repeat_test_clicked.emit(self.sensor_id)

    def on_manual_toggled(self, state):
        self.manual_toggled.emit(state == Qt.Checked)

    # --------------------------------------------------------------
    # Установка ручного режима и обновление состояния кнопок
    # --------------------------------------------------------------
    def set_manual_mode(self, manual):
        self._manual_mode = manual
        self.manual_check.blockSignals(True)
        self.manual_check.setChecked(manual)
        self.manual_check.blockSignals(False)
        # После изменения режима обновляем видимость и активность кнопок
        self.update_buttons_state(test_active=False, test_finished=False)

    def update_buttons_state(self, test_active=False, test_finished=False):
        """
        Обновляет состояние кнопок в зависимости от активности теста и режима.
        - test_active: идёт ли тест
        - test_finished: завершён ли тест (показывает, нужна ли кнопка "Повтор")
        """
        if test_active:
            # Во время теста: "Начать" отключена, "Стоп" активна, "Повтор" отключена
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.repeat_btn.setEnabled(False)
        else:
            # Тест не активен
            self.stop_btn.setEnabled(False)
            if self._manual_mode:
                # Ручной режим: показываем "Начать", скрываем "Повтор"
                self.start_btn.setVisible(True)
                self.start_btn.setEnabled(True)
                self.repeat_btn.setEnabled(False)
            else:
                # Автоматический режим: скрываем "Начать", показываем "Повтор" только если тест завершён
                self.start_btn.setVisible(False)
                self.start_btn.setEnabled(False)
                if test_finished:
                    self.repeat_btn.setEnabled(True)
                else:
                    self.repeat_btn.setEnabled(False)

    # --------------------------------------------------------------
    # Методы обновления информации в виджете
    # --------------------------------------------------------------
    def update_port_info(self, port, baud):
        self.label_port_info.setText(f"Порт: {port}, Скорость: {baud}")

    def update_total_time(self, duration_min):
        if duration_min is None:
            self.label_total_time.setText("Длительность: --")
        else:
            minutes = int(duration_min)
            seconds = int(round((duration_min - minutes) * 60))
            self.label_total_time.setText(f"Длительность: {minutes}м {seconds}с")

    def update_serial(self, serial):
        self.label_serial.setText(f"Серийный номер: {serial}")

    def update_build_version(self, build, version):
        if build is not None and version is not None:
            self.label_build_version.setText(f"Сборка: {build}, Версия: {version}")
        else:
            self.label_build_version.setText("Сборка: --, Версия: --")

    def update_device_type(self, dev_type):
        if dev_type is not None:
            self.label_device_type.setText(f"Тип: {dev_type}")
        else:
            self.label_device_type.setText("Тип: --")

    def update_temperature(self, temp):
        if temp is not None:
            self.label_temperature.setText(f"Температура: {temp:.1f} °C")
        else:
            self.label_temperature.setText("Температура: -- °C")

    def update_data(self, voltage, current, ionistor, battery):
        self.label_voltage.setText(f"Напр: {voltage:.2f} В" if voltage is not None else "Напр: -- В")
        self.label_current.setText(f"Ток: {current:.3f} мА" if current is not None else "Ток: -- мА")
        self.label_ionistor.setText(f"Ионистор: {ionistor:.2f} В" if ionistor is not None else "Ионистор: -- В")
        self.label_battery.setText(f"Аккум: {battery:.2f} В" if battery is not None else "Аккум: -- В")

    def update_voltage_ranges(self, start_ionistor, end_ionistor, start_battery, end_battery):
        if start_ionistor is not None and end_ionistor is not None:
            self.label_ionistor_range.setText(f"Ионистор: {start_ionistor:.2f}→{end_ionistor:.2f} В")
        else:
            self.label_ionistor_range.setText("Ионистор: --→-- В")
        if start_battery is not None and end_battery is not None:
            self.label_battery_range.setText(f"Аккум: {start_battery:.2f}→{end_battery:.2f} В")
        else:
            self.label_battery_range.setText("Аккум: --→-- В")

    def update_time_left(self, seconds_left):
        if seconds_left is None or seconds_left <= 0:
            self.label_time_left.setText("Тест не активен")
            self.label_time_left.setStyleSheet("color: gray; font-size: 14pt; font-weight: bold;")
        else:
            minutes = int(seconds_left // 60)
            seconds = int(seconds_left % 60)
            self.label_time_left.setText(f"{minutes:02d}:{seconds:02d}")
            self.label_time_left.setStyleSheet("color: blue; font-size: 14pt; font-weight: bold;")

    def update_test_result(self, result, start_ionistor=None, end_ionistor=None,
                           start_battery=None, end_battery=None):
        if result is None:
            self.setStyleSheet(f"background-color: {self.default_color};")
            self.update_voltage_ranges(None, None, None, None)
        else:
            self.update_voltage_ranges(start_ionistor, end_ionistor, start_battery, end_battery)
            if result == "Положительный":
                self.setStyleSheet("background-color: #90ee90;")
            elif result == "Отрицательный":
                self.setStyleSheet("background-color: #ff6b6b;")
            elif result == "Прерван":
                self.setStyleSheet("background-color: #ffd700;")

    def update_graphs(self, measurements):
        if not measurements:
            self.clear_graphs()
            return
        times = [m[0] for m in measurements]
        ionistor_vals = [m[3] for m in measurements]
        battery_vals = [m[4] for m in measurements]
        self.line_ion.set_data(times, ionistor_vals)
        self.line_bat.set_data(times, battery_vals)
        self.ax_ionistor.relim()
        self.ax_ionistor.autoscale_view()
        self.ax_battery.relim()
        self.ax_battery.autoscale_view()
        self.canvas.draw()

    def clear_graphs(self):
        self.line_ion.set_data([], [])
        self.line_bat.set_data([], [])
        self.ax_ionistor.relim()
        self.ax_ionistor.autoscale_view()
        self.ax_battery.relim()
        self.ax_battery.autoscale_view()
        self.canvas.draw()

    def reset_widget(self):
        self.update_serial("--")
        self.update_build_version(None, None)
        self.update_device_type(None)
        self.update_temperature(None)
        self.update_data(None, None, None, None)
        self.update_time_left(None)
        self.update_test_result(None)
        self.update_voltage_ranges(None, None, None, None)
        self.clear_graphs()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.repeat_btn.setEnabled(False)
        self.start_btn.setVisible(self._manual_mode)