"""PDO analytics — bottleneck report, stuck orders, Gantt timeline."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QGroupBox, QTabWidget,
)
from PyQt6.QtGui import QFont, QColor
from modules import pdo_analytics


class PDOAnalyticsWidget(QWidget):
    """Tabbed PDO analytics: bottlenecks, stuck orders, Gantt data."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel('Аналитика ПДО')
        tf = QFont()
        tf.setPointSize(13)
        tf.setBold(True)
        title.setFont(tf)
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_bottleneck_tab(), 'Узкие места')
        tabs.addTab(self._build_stuck_tab(), 'Застрявшие заказы')
        tabs.addTab(self._build_gantt_tab(), 'График (данные)')
        layout.addWidget(tabs)

    def _build_bottleneck_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self._bn_table = QTableWidget(0, 5)
        self._bn_table.setHorizontalHeaderLabels(
            ['Отдел', 'Заказов', 'Сред.дней', 'Макс.дней', 'Узкое место'])
        self._bn_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._bn_table)
        return w

    def _build_stuck_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self._stuck_table = QTableWidget(0, 5)
        self._stuck_table.setHorizontalHeaderLabels(
            ['Заказ', 'Изделие', 'Статус', 'Дней', 'Где застрял'])
        self._stuck_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._stuck_table)
        return w

    def _build_gantt_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self._gantt_table = QTableWidget(0, 4)
        self._gantt_table.setHorizontalHeaderLabels(
            ['Заказ', 'Изделие', 'Статус', 'Этапы'])
        self._gantt_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._gantt_table)
        return w

    def refresh(self):
        with self.db_manager.get_session() as s:
            # Bottlenecks
            bn = pdo_analytics.average_time_per_status(s)
            self._bn_table.setRowCount(len(bn))
            for i, r in enumerate(bn):
                self._bn_table.setItem(i, 0, QTableWidgetItem(r['status']))
                self._bn_table.setItem(i, 1, QTableWidgetItem(str(r['count'])))
                self._bn_table.setItem(i, 2, QTableWidgetItem(str(r['avg_days'])))
                self._bn_table.setItem(i, 3, QTableWidgetItem(str(r['max_days'])))
                bt = '⚠ Да' if r['bottleneck'] else ''
                item = QTableWidgetItem(bt)
                if r['bottleneck']:
                    item.setForeground(QColor('#c0392b'))
                self._bn_table.setItem(i, 4, item)
            self._bn_table.resizeColumnsToContents()

            # Stuck
            stuck = pdo_analytics.orders_stuck(s)
            self._stuck_table.setRowCount(len(stuck))
            for i, r in enumerate(stuck):
                self._stuck_table.setItem(i, 0, QTableWidgetItem(r['number']))
                self._stuck_table.setItem(i, 1, QTableWidgetItem(r['product']))
                self._stuck_table.setItem(i, 2, QTableWidgetItem(r['status']))
                days_item = QTableWidgetItem(str(r['days_stuck']))
                if r['days_stuck'] >= 30:
                    days_item.setForeground(QColor('#c0392b'))
                self._stuck_table.setItem(i, 3, days_item)
                self._stuck_table.setItem(i, 4, QTableWidgetItem(r['dept']))
            self._stuck_table.resizeColumnsToContents()

            # Gantt
            gantt = pdo_analytics.gantt_data(s)
            self._gantt_table.setRowCount(len(gantt))
            for i, r in enumerate(gantt):
                self._gantt_table.setItem(i, 0, QTableWidgetItem(r['number']))
                self._gantt_table.setItem(i, 1, QTableWidgetItem(r['product']))
                self._gantt_table.setItem(i, 2, QTableWidgetItem(r['status']))
                phases_str = ' → '.join(
                    f'{p["dept"]}({p["start"]})' for p in r['phases'])
                self._gantt_table.setItem(i, 3, QTableWidgetItem(phases_str))
            self._gantt_table.resizeColumnsToContents()
