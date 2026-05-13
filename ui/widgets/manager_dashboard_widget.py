"""
v9-6 UI: Дашборд руководителя.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QFrame, QGridLayout, QFileDialog, QMessageBox,
)

from modules.manager_dashboard import kpi_snapshot, export_pdf


class _KPICard(QFrame):
    """Карточка одного KPI: крупный заголовок + значение."""

    def __init__(self, title: str, value: str, *, color: str = '#1976d2',
                 parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f'_KPICard {{border:1px solid #ccc; border-radius:6px;'
            f' background:white;}}'
            f'#title {{color:#666;}}'
            f'#value {{color:{color}; font-weight:700;}}')
        lay = QVBoxLayout(self)
        lt = QLabel(title)
        lt.setObjectName('title')
        f = lt.font()
        f.setPointSize(f.pointSize() + 1)
        lt.setFont(f)

        self.lv = QLabel(value)
        self.lv.setObjectName('value')
        lvf = self.lv.font()
        lvf.setPointSize(max(20, f.pointSize() + 12))
        lvf.setBold(True)
        self.lv.setFont(lvf)
        self.lv.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(lt)
        lay.addWidget(self.lv, 1)

    def set_value(self, v: str):
        self.lv.setText(v)


class ManagerDashboardWidget(QWidget):
    """Главная страница для руководителя."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel('Период, дней:'))
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        self.days.setValue(30)
        self.days.valueChanged.connect(self.refresh)
        top.addWidget(self.days)
        top.addStretch(1)
        b_pdf = QPushButton('📄 Сохранить PDF-отчёт…')
        b_pdf.clicked.connect(self._on_export)
        b_refresh = QPushButton('⟳ Обновить')
        b_refresh.clicked.connect(self.refresh)
        top.addWidget(b_pdf)
        top.addWidget(b_refresh)
        root.addLayout(top)

        # Карточки KPI
        grid = QGridLayout()
        self.c_plan = _KPICard('% выполнения плана', '—', color='#2e7d32')
        self.c_wo = _KPICard('Нарядов в работе', '—', color='#1565c0')
        self.c_over = _KPICard('Просрочено', '—', color='#c62828')
        self.c_scrap = _KPICard('% брака', '—', color='#ef6c00')
        grid.addWidget(self.c_plan, 0, 0)
        grid.addWidget(self.c_wo, 0, 1)
        grid.addWidget(self.c_over, 0, 2)
        grid.addWidget(self.c_scrap, 0, 3)
        root.addLayout(grid)

        # Топы
        bottoms = QHBoxLayout()
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        self.t_ops = QTableWidget(0, 2)
        self.t_ops.setHorizontalHeaderLabels(['Операция', 'Минут'])
        self.t_ops.horizontalHeader().setStretchLastSection(True)
        self.t_eq = QTableWidget(0, 2)
        self.t_eq.setHorizontalHeaderLabels(['Оборудование', 'Загрузка'])
        self.t_eq.horizontalHeader().setStretchLastSection(True)

        for box, title in [(self.t_ops, 'Топ-5 операций по времени'),
                           (self.t_eq, 'Топ-5 оборудования по загрузке')]:
            wrap = QFrame()
            wrap.setFrameShape(QFrame.Shape.StyledPanel)
            wl = QVBoxLayout(wrap)
            t = QLabel(title)
            tf = t.font()
            tf.setBold(True)
            t.setFont(tf)
            wl.addWidget(t)
            wl.addWidget(box)
            bottoms.addWidget(wrap, 1)
        root.addLayout(bottoms, 1)

    def refresh(self):
        with self.db.get_session() as s:
            snap = kpi_snapshot(s, days=self.days.value())
        self._snap = snap
        self.c_plan.set_value(
            f'{snap.plan_completion_percent:.0f} %')
        self.c_wo.set_value(str(snap.wo_in_progress))
        self.c_over.set_value(str(snap.wo_overdue))
        self.c_scrap.set_value(f'{snap.scrap_percent:.1f} %')

        from PyQt6.QtWidgets import QTableWidgetItem
        self.t_ops.setRowCount(len(snap.top_bottleneck_ops))
        for i, (n, m) in enumerate(snap.top_bottleneck_ops):
            self.t_ops.setItem(i, 0, QTableWidgetItem(n))
            self.t_ops.setItem(i, 1, QTableWidgetItem(f'{m:.0f}'))
        self.t_ops.resizeColumnsToContents()
        self.t_eq.setRowCount(len(snap.top_loaded_equipment))
        for i, (n, p) in enumerate(snap.top_loaded_equipment):
            self.t_eq.setItem(i, 0, QTableWidgetItem(n))
            self.t_eq.setItem(i, 1, QTableWidgetItem(f'{p:.0f} %'))
        self.t_eq.resizeColumnsToContents()

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Сохранить PDF-отчёт', 'manager_dashboard.pdf',
            filter='PDF (*.pdf)')
        if not path:
            return
        try:
            export_pdf(self._snap, path)
            QMessageBox.information(
                self, 'PDF', f'Отчёт сохранён:\n{path}')
        except Exception as e:
            QMessageBox.critical(self, 'PDF', f'Ошибка: {e}')
