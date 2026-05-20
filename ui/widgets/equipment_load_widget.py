"""
v9-2 UI: Загрузка оборудования %.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.equipment_load import equipment_load, planned_equipment_load


class EquipmentLoadWidget(QWidget):
    """Дашборд «Загрузка оборудования»."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.mode_cb = QComboBox()
        self.mode_cb.addItem('Факт (RouteStep)', 'fact')
        self.mode_cb.addItem('План (открытые наряды)', 'plan')
        self.mode_cb.currentIndexChanged.connect(self.refresh)
        top.addWidget(QLabel('Режим:'))
        top.addWidget(self.mode_cb)

        self.days_sp = QSpinBox()
        self.days_sp.setRange(1, 365)
        self.days_sp.setValue(30)
        self.days_sp.valueChanged.connect(self.refresh)
        top.addWidget(QLabel('   Период, дней:'))
        top.addWidget(self.days_sp)

        top.addStretch(1)
        b_refresh = QPushButton('⟳ Обновить')
        b_refresh.clicked.connect(self.refresh)
        top.addWidget(b_refresh)
        root.addLayout(top)

        self.hint = QLabel(
            'Загрузка = реальное время работы / доступное время '
            '(8-час. смена × рабочие дни). 100 % = занят непрерывно.')
        self.hint.setStyleSheet('color:#666;')
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            'Оборудование', 'Модель', 'Занято, мин',
            'Доступно, мин', 'Загрузка'])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setStretchLastSection(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self.table, 1)

        self.summary = QLabel('—')
        self.summary.setStyleSheet('font-weight:600;')
        root.addWidget(self.summary)

    def refresh(self):
        days = self.days_sp.value()
        mode = self.mode_cb.currentData()
        with self.db.get_session() as s:
            if mode == 'plan':
                rows = planned_equipment_load(s, horizon_days=days)
            else:
                rows = equipment_load(s, days=days)
        self._fill(rows)
        if rows:
            avg = sum(r.load_percent for r in rows) / len(rows)
            over = sum(1 for r in rows if r.load_percent >= 90)
            idle = sum(1 for r in rows if r.load_percent < 5)
            self.summary.setText(
                f'Средняя загрузка: {avg:.0f}%   '
                f'·   Перегружено (≥ 90 %): {over}   '
                f'·   Простаивает (< 5 %): {idle}')
        else:
            self.summary.setText('Нет данных.')

    def _fill(self, rows):
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(r.equipment_name))
            self.table.setItem(i, 1, QTableWidgetItem(r.equipment_model))
            self.table.setItem(i, 2, QTableWidgetItem(f'{r.busy_minutes:.0f}'))
            self.table.setItem(i, 3, QTableWidgetItem(
                f'{r.available_minutes:.0f}'))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(min(int(r.load_percent), 100))
            bar.setFormat(f'{r.load_percent:.0f} %')
            if r.load_percent >= 90:
                bar.setStyleSheet(
                    'QProgressBar::chunk{background:#d32f2f;}')
            elif r.load_percent >= 50:
                bar.setStyleSheet(
                    'QProgressBar::chunk{background:#fbc02d;}')
            elif r.load_percent < 5:
                bar.setStyleSheet(
                    'QProgressBar::chunk{background:#9e9e9e;}')
            else:
                bar.setStyleSheet(
                    'QProgressBar::chunk{background:#388e3c;}')
            self.table.setCellWidget(i, 4, bar)
        self.table.resizeColumnsToContents()
