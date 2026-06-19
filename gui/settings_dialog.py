from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QComboBox,
                             QPushButton, QHBoxLayout, QGroupBox,
                             QGridLayout, QLabel, QSpinBox,
                             QDialogButtonBox)
from PyQt5.QtCore import pyqtSignal
import serial.tools.list_ports

# ------------------------------------------------------------------
# Диалог настроек для каждого датчика: COM-порт, скорость, длительность,
# а также отображение серийного номера (только для чтения).
# ------------------------------------------------------------------
class SettingsDialog(QDialog):
    # Сигнал, отправляемый главному окну при изменении настроек
    settings_changed = pyqtSignal(list)

    def __init__(self, sensor_settings, serial_numbers, parent=None):
        """
        sensor_settings: список словарей с ключами port, baud, duration_min
        serial_numbers: список из 4 серийных номеров (int или None)
        """
        super().__init__(parent)
        self.setWindowTitle("Настройки датчиков")
        self.setMinimumWidth(650)
        self.sensor_settings = sensor_settings[:]
        self.serial_numbers = serial_numbers[:] if serial_numbers else [None]*4

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Настройка COM-порта, скорости и длительности теста:"))

        self.port_combos = []
        self.baud_combos = []
        self.minute_spins = []
        self.second_spins = []
        self.serial_labels = []

        # Создание групп для каждого датчика
        for i in range(4):
            group = QGroupBox(f"Датчик {i+1}")
            group_layout = QGridLayout(group)

            # ---------- Выбор COM-порта ----------
            label_port = QLabel("COM-порт:")
            port_combo = QComboBox()
            port_combo.setEditable(False)
            port_combo.setCurrentText(sensor_settings[i]["port"])
            refresh_btn = QPushButton("Обновить")
            refresh_btn.clicked.connect(lambda checked, pc=port_combo: self.refresh_ports(pc))

            # ---------- Выбор скорости ----------
            label_baud = QLabel("Скорость (бод):")
            baud_combo = QComboBox()
            baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
            baud_combo.setCurrentText(str(sensor_settings[i]["baud"]))

            # ---------- Настройка длительности (минуты и секунды) ----------
            label_duration = QLabel("Длительность теста:")
            minute_spin = QSpinBox()
            minute_spin.setRange(0, 120)
            minute_spin.setSuffix(" мин")
            minute_spin.setSingleStep(1)
            second_spin = QSpinBox()
            second_spin.setRange(0, 59)
            second_spin.setSuffix(" сек")
            second_spin.setSingleStep(1)
            dur_min = sensor_settings[i].get("duration_min", 1.5)
            minutes = int(dur_min)
            seconds = int(round((dur_min - minutes) * 60))
            minute_spin.setValue(minutes)
            second_spin.setValue(seconds)

            # ---------- Отображение серийного номера (только для чтения) ----------
            label_serial = QLabel("Серийный номер:")
            serial_label = QLabel(str(serial_numbers[i]) if serial_numbers[i] is not None else "--")
            serial_label.setStyleSheet("font-weight: bold; color: #333;")
            serial_label.setWordWrap(True)

            # Размещение элементов в сетке
            row = 0
            group_layout.addWidget(label_port, row, 0)
            group_layout.addWidget(port_combo, row, 1)
            group_layout.addWidget(refresh_btn, row, 2)
            row += 1
            group_layout.addWidget(label_baud, row, 0)
            group_layout.addWidget(baud_combo, row, 1)
            row += 1
            group_layout.addWidget(label_duration, row, 0)
            group_layout.addWidget(minute_spin, row, 1)
            group_layout.addWidget(second_spin, row, 2)
            row += 1
            group_layout.addWidget(label_serial, row, 0)
            group_layout.addWidget(serial_label, row, 1, 1, 2)

            layout.addWidget(group)

            # Сохранение ссылок на виджеты
            self.port_combos.append(port_combo)
            self.baud_combos.append(baud_combo)
            self.minute_spins.append(minute_spin)
            self.second_spins.append(second_spin)
            self.serial_labels.append(serial_label)

        # ---------- Кнопки OK и Cancel ----------
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("Сохранить")
        button_box.button(QDialogButtonBox.Cancel).setText("Отмена")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Первоначальное заполнение списков портов
        self.refresh_all_ports()

    # --------------------------------------------------------------
    # Обновление списка доступных COM-портов для одного комбобокса
    # --------------------------------------------------------------
    def refresh_ports(self, port_combo):
        current_text = port_combo.currentText()
        port_combo.clear()
        ports = serial.tools.list_ports.comports()
        port_names = [port.device for port in ports]
        if current_text and current_text not in port_names:
            port_names.append(current_text)
        port_names.sort()
        for name in port_names:
            port_combo.addItem(name)
        idx = port_combo.findText(current_text)
        if idx >= 0:
            port_combo.setCurrentIndex(idx)
        elif port_combo.count() > 0:
            port_combo.setCurrentIndex(0)

    # --------------------------------------------------------------
    # Обновление списков портов для всех комбобоксов
    # --------------------------------------------------------------
    def refresh_all_ports(self):
        for combo in self.port_combos:
            self.refresh_ports(combo)

    # --------------------------------------------------------------
    # Возврат текущих настроек (без серийных номеров, они только для чтения)
    # --------------------------------------------------------------
    def get_settings(self):
        new_settings = []
        for i in range(4):
            minutes = self.minute_spins[i].value()
            seconds = self.second_spins[i].value()
            duration_min = minutes + seconds / 60.0
            new_settings.append({
                "port": self.port_combos[i].currentText().strip(),
                "baud": int(self.baud_combos[i].currentText()),
                "duration_min": duration_min
            })
        return new_settings