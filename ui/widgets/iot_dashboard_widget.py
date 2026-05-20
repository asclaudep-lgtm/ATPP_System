"""IoT-дашборд: мониторинг станков в реальном времени."""
from datetime import datetime

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.iot_collector import get_all_machine_statuses


class IoTDashboardWidget(QWidget):
    """Дашборд телеметрии станков."""

    def __init__(self, db_manager, current_user_id=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._simulator = None
        self._collector = None
        self._init_ui()
        self._start_auto_refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Controls
        ctrl = QHBoxLayout()

        self.start_btn = QPushButton('▶ Запустить симулятор')
        self.start_btn.clicked.connect(self._toggle_simulator)
        ctrl.addWidget(self.start_btn)

        ctrl.addWidget(QLabel('Ускорение:'))
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 600)
        self.speed_spin.setValue(60)
        self.speed_spin.setSuffix('x')
        ctrl.addWidget(self.speed_spin)

        ctrl.addStretch()
        self.refresh_label = QLabel('')
        ctrl.addWidget(self.refresh_label)
        layout.addLayout(ctrl)

        # Machine table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            'Станок', 'Статус', 'Обороты', 'Мощность',
            'Программа', 'Обновлено'])
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 150)
        layout.addWidget(self.table)

        # Summary
        sum_grp = QGroupBox('Сводка:')
        sum_lay = QHBoxLayout(sum_grp)
        self.running_lbl = QLabel('🟢 Работает: 0')
        self.idle_lbl = QLabel('🟡 Простаивает: 0')
        self.offline_lbl = QLabel('⚫ Отключено: 0')
        self.alarm_lbl = QLabel('🔴 Авария: 0')
        sum_lay.addWidget(self.running_lbl)
        sum_lay.addWidget(self.idle_lbl)
        sum_lay.addWidget(self.offline_lbl)
        sum_lay.addWidget(self.alarm_lbl)
        sum_lay.addStretch()
        layout.addWidget(sum_grp)

    def _start_auto_refresh(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)

    def refresh(self):
        try:
            with self.db_manager.get_session() as s:
                machines = get_all_machine_statuses(s)
        except Exception:
            return

        self.table.setRowCount(len(machines))
        counts = {'running': 0, 'idle': 0, 'offline': 0, 'alarm': 0}

        for i, m in enumerate(machines):
            name_item = QTableWidgetItem(m['equipment_name'])
            self.table.setItem(i, 0, name_item)

            status = m['status']
            status_item = QTableWidgetItem(status)
            color = {'running': '#4CAF50', 'idle': '#FFC107',
                     'offline': '#9E9E9E', 'alarm': '#F44336'}.get(status, '')
            if color:
                status_item.setBackground(QColor(color))
            self.table.setItem(i, 1, status_item)

            self.table.setItem(i, 2, QTableWidgetItem(''))
            self.table.setItem(i, 3, QTableWidgetItem(''))
            self.table.setItem(i, 4, QTableWidgetItem(''))
            self.table.setItem(i, 5, QTableWidgetItem(
                m['last_update'] or ''))

            counts[status] = counts.get(status, 0) + 1

        self.running_lbl.setText(f'🟢 Работает: {counts["running"]}')
        self.idle_lbl.setText(f'🟡 Простаивает: {counts["idle"]}')
        self.offline_lbl.setText(f'⚫ Отключено: {counts["offline"]}')
        self.alarm_lbl.setText(f'🔴 Авария: {counts["alarm"]}')
        self.refresh_label.setText(
            f'Обновлено: {datetime.now().strftime("%H:%M:%S")}')

    def _toggle_simulator(self):
        if self._simulator is not None:
            self._simulator.stop()
            self._simulator = None
            self.start_btn.setText('▶ Запустить симулятор')
        else:
            from modules.iot_simulator import TelemetrySimulator
            self._simulator = TelemetrySimulator(self.db_manager)
            self._simulator.speedup_factor = self.speed_spin.value()
            with self.db_manager.get_session() as s:
                self._simulator.load_from_db(s)
            self._simulator.start()
            self.start_btn.setText('■ Остановить симулятор')

    def closeEvent(self, event):
        if self._simulator:
            self._simulator.stop()
        if self._timer:
            self._timer.stop()
        super().closeEvent(event)
