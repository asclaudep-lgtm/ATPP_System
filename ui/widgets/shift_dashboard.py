"""Shift dashboard — цеховой экран: текущие наряды, статусы, брак за смену."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QGroupBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from datetime import datetime


class ShiftDashboard(QWidget):
    """Full-screen shop floor dashboard with live updates."""

    refresh_requested = pyqtSignal()

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._init_ui()
        self.refresh()

        self._timer = QTimer()
        self._timer.timeout.connect(self.refresh)
        self._timer.start(15000)  # Refresh every 15 seconds

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header
        hdr = QHBoxLayout()
        title = QLabel('Дашборд смены')
        tf = QFont()
        tf.setPointSize(18)
        tf.setBold(True)
        title.setFont(tf)
        hdr.addWidget(title)
        hdr.addStretch()

        self._time_label = QLabel()
        self._time_label.setFont(QFont('Consolas', 14))
        hdr.addWidget(self._time_label)

        refresh_btn = QPushButton('↻ Обновить')
        refresh_btn.clicked.connect(self.refresh)
        hdr.addWidget(refresh_btn)
        layout.addLayout(hdr)

        # KPI row
        kpi_row = QHBoxLayout()
        self._kpi_widgets = {}
        for key, label, color in [
            ('active_orders', 'Активных нарядов', '#1976d2'),
            ('ops_in_progress', 'Операций в работе', '#388e3c'),
            ('ops_done_today', 'Выполнено сегодня', '#f9a825'),
            ('scrap_today', 'Брак за смену', '#d32f2f'),
        ]:
            grp = QGroupBox(label)
            grp_lay = QVBoxLayout(grp)
            lbl = QLabel('—')
            lbl.setFont(QFont('Arial', 32, QFont.Weight.Bold))
            lbl.setStyleSheet(f'color: {color};')
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grp_lay.addWidget(lbl)
            kpi_row.addWidget(grp)
            self._kpi_widgets[key] = lbl
        layout.addLayout(kpi_row)

        # Active orders table
        layout.addWidget(QLabel('Текущие наряды:'))
        self._orders_table = QTableWidget(0, 5)
        self._orders_table.setHorizontalHeaderLabels(
            ['Наряд', 'Изделие', 'Статус', 'Выполнено', 'Срок'])
        self._orders_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._orders_table, stretch=1)

    def refresh(self):
        from database.models import WorkOrder, RouteStep, ScrapRecord

        with self.db_manager.get_session() as s:
            # KPI
            active = s.query(WorkOrder).filter(
                WorkOrder.is_deleted == False,
                WorkOrder.status.in_(['RELEASED', 'REGISTERED', 'IN_PROGRESS'])
            ).count()
            self._kpi_widgets['active_orders'].setText(str(active))

            ops_in_progress = s.query(RouteStep).filter(
                RouteStep.status == 'В работе').count()
            self._kpi_widgets['ops_in_progress'].setText(str(ops_in_progress))

            today = datetime.now().strftime('%Y-%m-%d')
            ops_done = s.query(RouteStep).filter(
                RouteStep.status == 'Выполнен',
                RouteStep.actual_end >= today + ' 00:00:00',
            ).count()
            self._kpi_widgets['ops_done_today'].setText(str(ops_done))

            scrap = s.query(ScrapRecord).filter(
                ScrapRecord.created_at >= today).count()
            self._kpi_widgets['scrap_today'].setText(str(scrap))

            # Orders
            orders = s.query(WorkOrder).filter(
                WorkOrder.is_deleted == False,
                WorkOrder.status.in_(['RELEASED', 'REGISTERED', 'IN_PROGRESS'])
            ).order_by(WorkOrder.due_date).limit(50).all()

            self._orders_table.setRowCount(len(orders))
            for i, wo in enumerate(orders):
                self._orders_table.setItem(
                    i, 0, QTableWidgetItem(wo.number))
                prod = wo.product.designation if wo.product else ''
                self._orders_table.setItem(i, 1, QTableWidgetItem(prod))
                status = (wo.status.value
                          if hasattr(wo.status, 'value')
                          else str(wo.status))
                self._orders_table.setItem(i, 2, QTableWidgetItem(status))
                done = f'{wo.qty_done}/{wo.qty_total}'
                self._orders_table.setItem(i, 3, QTableWidgetItem(done))
                due = str(wo.due_date) if wo.due_date else '—'
                self._orders_table.setItem(i, 4, QTableWidgetItem(due))

        self._time_label.setText(datetime.now().strftime('%H:%M:%S'))
        self._orders_table.resizeColumnsToContents()

    def stop_timer(self):
        self._timer.stop()
