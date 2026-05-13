"""
v9-1 UI: Gantt-доска планирования.

Визуализирует ScheduledOp на оси времени по оборудованию.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict, Optional

from PyQt6.QtCore import Qt, QRectF, QPointF, QSizeF
from PyQt6.QtGui import (
    QBrush, QColor, QPen, QPainter, QFont,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QComboBox, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsSimpleTextItem,
    QMessageBox, QFileDialog,
)

from modules.scheduler import (
    schedule_open_orders, detect_conflicts, ScheduledOp,
    schedule_aps, APSResult,
)


PIXELS_PER_HOUR = 30  # масштаб оси X
ROW_HEIGHT = 28
HEADER_HEIGHT = 50
LEFT_PANEL_WIDTH = 200
# Палитра для нарядов
WO_COLORS = [
    '#1976d2', '#388e3c', '#d32f2f', '#f9a825', '#7b1fa2',
    '#00838f', '#5d4037', '#c2185b', '#0288d1', '#689f38',
]


class GanttScene(QGraphicsScene):

    def __init__(self, parent=None):
        super().__init__(parent)


class GanttWidget(QWidget):
    """Виджет планировщика."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel('Горизонт, дней:'))
        self.horizon = QSpinBox()
        self.horizon.setRange(1, 90)
        self.horizon.setValue(14)
        self.horizon.valueChanged.connect(self.refresh)
        top.addWidget(self.horizon)
        top.addStretch(1)
        self.lbl_info = QLabel('—')
        top.addWidget(self.lbl_info)
        # APS/FIFO mode
        self.mode_cb = QComboBox()
        self.mode_cb.addItem('FIFO (по сроку)', 'fifo')
        self.mode_cb.addItem('APS (приоритет+сроки+переналадки)', 'aps')
        self.mode_cb.currentIndexChanged.connect(self.refresh)
        top.addWidget(self.mode_cb)
        top.addSpacing(12)
        b_export = QPushButton('💾 Экспорт PNG…')
        b_export.clicked.connect(self._on_export)
        top.addWidget(b_export)
        b_refresh = QPushButton('⟳ Перепланировать')
        b_refresh.clicked.connect(self.refresh)
        top.addWidget(b_refresh)
        b_shift_left = QPushButton('◀ Сдвинуть')
        b_shift_left.clicked.connect(lambda: self._shift_selected(-60))
        top.addWidget(b_shift_left)
        b_shift_right = QPushButton('Сдвинуть ▶')
        b_shift_right.clicked.connect(lambda: self._shift_selected(60))
        top.addWidget(b_shift_right)
        root.addLayout(top)

        # Подсказка
        hint = QLabel(
            'Жадная FIFO-раскладка по due_date. Один цвет = один наряд. '
            'Конфликтные операции выделены красной рамкой.')
        hint.setStyleSheet('color:#666;')
        root.addWidget(hint)

        self.scene = GanttScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(
            QGraphicsView.DragMode.ScrollHandDrag)
        root.addWidget(self.view, 1)

    def refresh(self):
        horizon = self.horizon.value()
        mode = self.mode_cb.currentData()
        with self.db.get_session() as s:
            if mode == 'aps':
                result = schedule_aps(s, horizon_days=horizon)
                sched = result.schedule
                conflicts = result.conflicts
                metrics = result.metrics
                self.lbl_info.setText(
                    f'Нарядов: {metrics.total_orders_scheduled}   ·   '
                    f'Операций: {metrics.total_operations_scheduled}   ·   '
                    f'Конфликтов: {len(conflicts)}   ·   '
                    f'Переналадок: {metrics.total_setup_time_min:.0f} мин   ·   '
                    f'Загрузка: {metrics.avg_equipment_load_pct:.1f}%')
            else:
                sched = schedule_open_orders(s, horizon_days=horizon)
                conflicts = detect_conflicts(sched)
                wos = len({s.work_order_id for s in sched})
                eq_count = len({s.equipment_id for s in sched if s.equipment_id})
                self.lbl_info.setText(
                    f'Нарядов: {wos}   ·   Оборудования: {eq_count}   ·   '
                    f'Операций: {len(sched)}   ·   Конфликтов: {len(conflicts)}')
        self._render(sched, conflicts)

    # ── Рендер ────────────────────────────────────────────────────
    def _render(self, sched: List[ScheduledOp], conflicts):
        self.scene.clear()
        if not sched:
            self.scene.addText('Нет открытых нарядов в горизонте планирования.')
            return

        # Группировка по eq
        rows: Dict[Optional[int], List[ScheduledOp]] = {}
        for op in sched:
            rows.setdefault(op.equipment_id, []).append(op)

        eq_order = sorted(rows.keys(), key=lambda k: (k is None, k or 0))
        # Цвета по wo
        wo_color: Dict[int, QColor] = {}

        # Найдём общий начальный момент
        t0 = min(op.start for op in sched).replace(
            hour=8, minute=0, second=0, microsecond=0)
        t1 = max(op.finish for op in sched)
        total_hours = max(1, int((t1 - t0).total_seconds() / 3600) + 8)

        # Заголовок шкалы времени
        scale_pen = QPen(QColor(200, 200, 200))
        scene_w = LEFT_PANEL_WIDTH + total_hours * PIXELS_PER_HOUR
        scene_h = HEADER_HEIGHT + ROW_HEIGHT * len(eq_order) + 20
        self.scene.setSceneRect(0, 0, scene_w, scene_h)

        # Сетка дней
        cur = t0
        day_count = 0
        while cur <= t1:
            x = LEFT_PANEL_WIDTH + (cur - t0).total_seconds() / 3600 \
                * PIXELS_PER_HOUR
            line = QGraphicsLineItem(x, 0, x, scene_h)
            line.setPen(QPen(QColor(220, 220, 220)))
            self.scene.addItem(line)
            txt = QGraphicsSimpleTextItem(cur.strftime('%d.%m %a'))
            txt.setPos(x + 4, 4)
            f = QFont()
            f.setPointSize(9)
            f.setBold(True)
            txt.setFont(f)
            self.scene.addItem(txt)
            cur += timedelta(days=1)
            day_count += 1

        # Заголовки строк по оборудованию + горизонтальные линии
        for ri, eq_id in enumerate(eq_order):
            y = HEADER_HEIGHT + ri * ROW_HEIGHT
            txt = QGraphicsSimpleTextItem(
                rows[eq_id][0].equipment_name[:28])
            txt.setPos(6, y + 4)
            f = QFont()
            f.setPointSize(9)
            txt.setFont(f)
            self.scene.addItem(txt)
            line = QGraphicsLineItem(0, y + ROW_HEIGHT,
                                     scene_w, y + ROW_HEIGHT)
            line.setPen(QPen(QColor(230, 230, 230)))
            self.scene.addItem(line)

        # Прямоугольники операций
        conflict_set = set()
        for a, b in conflicts:
            conflict_set.add(id(a))
            conflict_set.add(id(b))

        for ri, eq_id in enumerate(eq_order):
            y = HEADER_HEIGHT + ri * ROW_HEIGHT + 2
            for op in rows[eq_id]:
                color = wo_color.setdefault(
                    op.work_order_id,
                    QColor(WO_COLORS[len(wo_color) % len(WO_COLORS)]))
                x1 = LEFT_PANEL_WIDTH + (op.start - t0).total_seconds() \
                    / 3600 * PIXELS_PER_HOUR
                x2 = LEFT_PANEL_WIDTH + (op.finish - t0).total_seconds() \
                    / 3600 * PIXELS_PER_HOUR
                w = max(8.0, x2 - x1)
                rect = QGraphicsRectItem(x1, y, w, ROW_HEIGHT - 4)
                rect.setBrush(QBrush(color))
                if id(op) in conflict_set:
                    rect.setPen(QPen(QColor('#d32f2f'), 2))
                else:
                    rect.setPen(QPen(color.darker(120), 1))
                tip = (f'{op.work_order_number} · '
                       f'{op.operation_number} {op.operation_name}\n'
                       f'{op.start.strftime("%d.%m %H:%M")}'
                       f' — {op.finish.strftime("%d.%m %H:%M")}'
                       f'  ({op.duration_min:.0f} мин)')
                rect.setToolTip(tip)
                self.scene.addItem(rect)
                # Подпись наряда внутри (если поместится)
                if w > 60:
                    lbl = QGraphicsSimpleTextItem(op.work_order_number)
                    lbl.setBrush(QBrush(QColor('white')))
                    f = QFont()
                    f.setPointSize(8)
                    lbl.setFont(f)
                    lbl.setPos(x1 + 4, y + 4)
                    self.scene.addItem(lbl)

    def _on_export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Экспорт Gantt', 'gantt.png',
            filter='PNG (*.png)')
        if not path:
            return
        from PyQt6.QtGui import QImage
        rect = self.scene.sceneRect()
        img = QImage(int(rect.width()) + 20, int(rect.height()) + 20,
                     QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scene.render(p)
        p.end()
        img.save(path)
        QMessageBox.information(self, 'Gantt', f'Сохранено: {path}')

    def _shift_selected(self, delta_minutes: int):
        """Сдвинуть выбранную операцию влево/вправо."""
        items = self.view.scene().selectedItems()
        if not items:
            return
        for item in items:
            if hasattr(item, 'moveBy'):
                item.moveBy(delta_minutes * PIXELS_PER_HOUR / 60.0, 0)
