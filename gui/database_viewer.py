from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QLineEdit, QLabel, QCheckBox, QMessageBox,
                             QAbstractItemView)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QIntValidator
from database.db_manager import get_all_results
from datetime import datetime

# ------------------------------------------------------------------
# Окно просмотра базы данных тестов с фильтрацией
# ------------------------------------------------------------------
class DatabaseViewer(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("База данных тестов")
        self.setMinimumSize(900, 450)
        self.setModal(False)
        self.installEventFilter(self)

        layout = QVBoxLayout(self)

        # Верхняя панель с фильтрами
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Фильтр по серийному номеру:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Введите номер (до 6 цифр)")
        self.search_edit.returnPressed.connect(self.load_data)
        self.search_edit.setMaxLength(6)
        validator = QIntValidator(1, 999999, self)
        self.search_edit.setValidator(validator)
        top_layout.addWidget(self.search_edit)

        self.search_btn = QPushButton("Поиск")
        self.search_btn.clicked.connect(self.load_data)
        top_layout.addWidget(self.search_btn)

        self.valid_check = QCheckBox("Только актуальные")
        self.valid_check.stateChanged.connect(self.load_data)
        top_layout.addWidget(self.valid_check)

        self.positive_check = QCheckBox("Только положительные")
        self.positive_check.stateChanged.connect(self.load_data)
        top_layout.addWidget(self.positive_check)

        self.negative_check = QCheckBox("Только отрицательные")
        self.negative_check.stateChanged.connect(self.load_data)
        top_layout.addWidget(self.negative_check)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Таблица для отображения записей
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.load_data()
        self.showMaximized()

    # --------------------------------------------------------------
    # Обработка клавиш F11 (полноэкранный режим) и Escape (закрыть)
    # --------------------------------------------------------------
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_F11:
                if self.isMaximized():
                    self.showNormal()
                else:
                    self.showMaximized()
                return True
            elif event.key() == Qt.Key_Escape:
                self.accept()
                return True
        return super().eventFilter(obj, event)

    # --------------------------------------------------------------
    # Загрузка данных из БД с применением всех фильтров
    # --------------------------------------------------------------
    def load_data(self):
        # Получаем серийный номер из поля поиска
        serial_text = self.search_edit.text().strip()
        serial_filter = None
        if serial_text:
            try:
                val = int(serial_text)
                if 1 <= val <= 999999:
                    serial_filter = val
                else:
                    QMessageBox.warning(self, "Ошибка", "Номер должен быть от 1 до 999999.")
                    return
            except ValueError:
                QMessageBox.warning(self, "Ошибка", "Введите корректное целое число.")
                return

        # Загружаем все записи (или отфильтрованные по номеру)
        rows = get_all_results(serial_filter)

        # Фильтр "Только актуальные"
        if self.valid_check.isChecked():
            rows = [r for r in rows if r[12] == 1]  # is_valid на позиции 12

        # Фильтр по результату (положительные / отрицательные)
        positive_filter = self.positive_check.isChecked()
        negative_filter = self.negative_check.isChecked()
        if positive_filter and not negative_filter:
            rows = [r for r in rows if r[2] == "Положительный"]
        elif negative_filter and not positive_filter:
            rows = [r for r in rows if r[2] == "Отрицательный"]
        # Если оба чекбокса включены или оба выключены – фильтр не применяется

        # Если данных нет – выводим сообщение
        if not rows:
            self.table.setRowCount(0)
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels(["Нет данных"])
            self.table.setItem(0, 0, QTableWidgetItem("Записи отсутствуют. Проведите тест или измените фильтр."))
            return

        # Настройка заголовков таблицы
        headers = [
            "Серийный номер", "Напряжение питания (В)",
            "Потребляемый ток (мА)", "Ионистор (В)",
            "Аккумулятор (В)", "Длительность (мм:сс)",
            "Начало теста", "Конец теста", "Результат", "Актуально"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            # row: (id, serial, test_result, start_ionistor, end_ionistor,
            #       start_battery, end_battery, voltage_supply, current_consume,
            #       test_duration_sec, start_time, end_time, is_valid)

            # 1. Серийный номер
            item = QTableWidgetItem(str(row[1]))
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 0, item)

            # 2. Напряжение питания (В)
            v_supply = row[7] if row[7] is not None else 0
            item = QTableWidgetItem(f"{v_supply:.2f}")
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 1, item)

            # 3. Потребляемый ток (А) – значение уже в амперах
            current = row[8] if row[8] is not None else 0
            item = QTableWidgetItem(f"{current:.3f}")
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 2, item)

            # 4. Ионистор (начало → конец)
            start_ion = row[3] if row[3] is not None else 0
            end_ion = row[4] if row[4] is not None else 0
            item = QTableWidgetItem(f"{start_ion:.2f} → {end_ion:.2f}")
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 3, item)

            # 5. Аккумулятор (начало → конец)
            start_bat = row[5] if row[5] is not None else 0
            end_bat = row[6] if row[6] is not None else 0
            item = QTableWidgetItem(f"{start_bat:.2f} → {end_bat:.2f}")
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 4, item)

            # 6. Длительность (вычисляем из start_time и end_time)
            start_time_str = row[10]
            end_time_str = row[11]
            duration_sec = 0
            if start_time_str and end_time_str and isinstance(start_time_str, str) and isinstance(end_time_str, str):
                try:
                    start_dt = datetime.fromisoformat(start_time_str)
                    end_dt = datetime.fromisoformat(end_time_str)
                    duration_sec = int(round((end_dt - start_dt).total_seconds()))
                except:
                    duration_sec = 0
            minutes = duration_sec // 60
            seconds = duration_sec % 60
            duration_str = f"{minutes:02d}:{seconds:02d}"
            item = QTableWidgetItem(duration_str)
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 5, item)

            # 7. Начало теста
            start_time = row[10]
            if start_time and isinstance(start_time, str):
                if 'T' in start_time:
                    start_time = start_time.replace('T', ' ')[:19]
            else:
                start_time = "--"
            item = QTableWidgetItem(str(start_time))
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 6, item)

            # 8. Конец теста
            end_time = row[11]
            if end_time and isinstance(end_time, str):
                if 'T' in end_time:
                    end_time = end_time.replace('T', ' ')[:19]
            else:
                end_time = "--"
            item = QTableWidgetItem(str(end_time))
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 7, item)

            # 9. Результат – цветовая индикация
            result = row[2] if row[2] is not None else "Неизвестно"
            item = QTableWidgetItem(result)
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)
            if result == "Положительный":
                item.setBackground(Qt.green)
            elif result == "Отрицательный":
                item.setBackground(Qt.red)
            elif result == "Прерван":
                item.setBackground(Qt.yellow)
            self.table.setItem(i, 8, item)

            # 10. Актуальность (is_valid)
            is_valid = row[12] if row[12] is not None else 0
            item = QTableWidgetItem("Да" if is_valid == 1 else "Нет")
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)
            if is_valid == 1:
                item.setBackground(Qt.green)
            else:
                item.setBackground(Qt.lightGray)
            self.table.setItem(i, 9, item)