"""Детализация одного станка с историей телеметрии."""
from datetime import datetime, timedelta

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.models import Equipment
from modules.iot_collector import get_latest_status, get_status_history


class MachineDetailWidget(QWidget):
    """Детальный просмотр статуса одного станка."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Equipment selector
        sel = QHBoxLayout()
        sel.addWidget(QLabel('Станок:'))
        self.eq_combo = QComboBox()
        self.eq_combo.currentIndexChanged.connect(self._on_eq_changed)
        with self.db_manager.get_session() as s:
            for eq in s.query(Equipment).order_by(Equipment.name).all():
                self.eq_combo.addItem(eq.name, eq.id)
        sel.addWidget(self.eq_combo, stretch=1)

        self.refresh_btn = QPushButton('↻ Обновить')
        self.refresh_btn.clicked.connect(self.refresh)
        sel.addWidget(self.refresh_btn)
        layout.addLayout(sel)

        # Current status
        st_grp = QGroupBox('Текущий статус:')
        st_lay = QHBoxLayout(st_grp)
        self.status_label = QLabel('—')
        self.status_label.setStyleSheet('font-size: 16px; font-weight: bold;')
        st_lay.addWidget(self.status_label)
        self.uptime_label = QLabel('')
        st_lay.addWidget(self.uptime_label)
        st_lay.addStretch()
        layout.addWidget(st_grp)

        # History table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            'Время', 'Статус', 'Обороты', 'Мощность'])
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 80)
        layout.addWidget(self.table)

        # Auto-refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5000)

    def _on_eq_changed(self):
        self.refresh()

    def refresh(self):
        eq_id = self.eq_combo.currentData()
        if eq_id is None:
            return

        try:
            with self.db_manager.get_session() as s:
                latest = get_latest_status(s, equipment_id=eq_id)
                since = datetime.now() - timedelta(hours=24)
                history = get_status_history(s, equipment_id=eq_id,
                                              since=since, limit=50)
        except Exception:
            return

        if latest:
            self.status_label.setText(latest['status'].upper())
            self.uptime_label.setText(
                f'Наработка сегодня: {latest.get("uptime_today_min", 0):.0f} мин')
        else:
            self.status_label.setText('Нет данных')

        self.table.setRowCount(len(history))
        for i, h in enumerate(history):
            self.table.setItem(i, 0, QTableWidgetItem(h['recorded_at'] or ''))
            self.table.setItem(i, 1, QTableWidgetItem(h['status']))
            self.table.setItem(i, 2, QTableWidgetItem(
                str(h['spindle_speed'] or '')))
            self.table.setItem(i, 3, QTableWidgetItem(
                str(h['power'] or '')))

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
