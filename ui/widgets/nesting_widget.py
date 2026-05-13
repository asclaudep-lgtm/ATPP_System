"""Виджет визуализации раскроя листового металла (нестинг).

Greedy shelf-алгоритм: размещает прямоугольные заготовки на листе,
минимизируя отходы. Поддерживает деловые отходы (остатки листа).
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QSpinBox, QDoubleSpinBox, QTableWidget,
                              QTableWidgetItem, QGroupBox, QMessageBox)
from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                          QPaintEvent)


class NestingCanvas(QWidget):
    """Холст раскроя — рисует лист и размещённые заготовки."""

    COLORS = ['#1976d2', '#388e3c', '#d32f2f', '#f9a825', '#7b1fa2',
              '#00838f', '#c2185b', '#0288d1', '#689f38', '#f57c00']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sheet_w = 1500
        self.sheet_h = 3000
        self.parts = []  # [(x, y, w, h, label)]
        self.utilization = 0.0
        self.setMinimumSize(400, 600)

    def set_data(self, sheet_w, sheet_h, parts, utilization):
        self.sheet_w = sheet_w
        self.sheet_h = sheet_h
        self.parts = parts
        self.utilization = utilization
        self.update()

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        scale = min(
            (self.width() - 20) / self.sheet_w,
            (self.height() - 20) / self.sheet_h)

        offset_x = 10
        offset_y = 10
        draw_w = int(self.sheet_w * scale)
        draw_h = int(self.sheet_h * scale)

        # Лист
        p.setPen(QPen(QColor('#333'), 2))
        p.setBrush(QBrush(QColor('#f5f5f5')))
        p.drawRect(offset_x, offset_y, draw_w, draw_h)

        # Заготовки
        for i, (x, y, w, h, label) in enumerate(self.parts):
            color = QColor(self.COLORS[i % len(self.COLORS)])
            color.setAlpha(180)
            px = offset_x + int(x * scale)
            py = offset_y + int(y * scale)
            pw = max(int(w * scale), 2)
            ph = max(int(h * scale), 2)

            p.setPen(QPen(color.darker(130), 1))
            p.setBrush(QBrush(color))
            p.drawRect(px, py, pw, ph)

            if pw > 30 and ph > 15:
                p.setPen(QColor('#fff'))
                p.setFont(QFont('sans', 8))
                p.drawText(QRectF(px, py, pw, ph),
                           Qt.AlignmentFlag.AlignCenter,
                           label[:15])

        # Статистика
        p.setPen(QColor('#333'))
        p.setFont(QFont('sans', 10))
        p.drawText(offset_x, offset_y + draw_h + 18,
                   f'Использование: {self.utilization:.1f}% | '
                   f'Лист: {self.sheet_w}×{self.sheet_h} мм | '
                   f'Деталей: {len(self.parts)}')


class NestingWidget(QWidget):
    """Виджет раскроя листового металла."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # Left: controls
        ctrl = QVBoxLayout()
        grp = QGroupBox('Параметры листа:')
        grp_lay = QVBoxLayout(grp)

        self.sheet_w = QSpinBox()
        self.sheet_w.setRange(100, 6000)
        self.sheet_w.setValue(1500)
        self.sheet_w.setSuffix(' мм')
        grp_lay.addWidget(QLabel('Ширина:'))
        grp_lay.addWidget(self.sheet_w)

        self.sheet_h = QSpinBox()
        self.sheet_h.setRange(100, 12000)
        self.sheet_h.setValue(3000)
        self.sheet_h.setSuffix(' мм')
        grp_lay.addWidget(QLabel('Длина:'))
        grp_lay.addWidget(self.sheet_h)

        self.k_zag = QDoubleSpinBox()
        self.k_zag.setRange(1.0, 3.0)
        self.k_zag.setValue(1.05)
        self.k_zag.setSingleStep(0.05)
        grp_lay.addWidget(QLabel('Коэф. зазора:'))
        grp_lay.addWidget(self.k_zag)
        ctrl.addWidget(grp)

        # Parts table
        parts_grp = QGroupBox('Заготовки:')
        parts_lay = QVBoxLayout(parts_grp)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ['Обозначение', 'Ширина', 'Длина', 'Кол-во'])
        self.table.setColumnWidth(0, 120)
        self.table.setColumnWidth(1, 60)
        self.table.setColumnWidth(2, 60)
        self.table.setColumnWidth(3, 50)
        parts_lay.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton('+')
        add_btn.clicked.connect(lambda: self.table.insertRow(
            self.table.rowCount()))
        btn_row.addWidget(add_btn)
        del_btn = QPushButton('−')
        del_btn.clicked.connect(lambda: self.table.removeRow(
            self.table.currentRow()))
        btn_row.addWidget(del_btn)
        parts_lay.addLayout(btn_row)
        ctrl.addWidget(parts_grp)

        calc_btn = QPushButton('▶ Рассчитать раскрой')
        calc_btn.clicked.connect(self._calculate)
        ctrl.addWidget(calc_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # Right: canvas
        self.canvas = NestingCanvas()
        layout.addWidget(self.canvas, stretch=1)

    def _calculate(self):
        sheet_w = self.sheet_w.value()
        sheet_h = self.sheet_h.value()
        gap = self.k_zag.value()

        parts = []
        for r in range(self.table.rowCount()):
            des = self.table.item(r, 0)
            w_item = self.table.item(r, 1)
            h_item = self.table.item(r, 2)
            qty_item = self.table.item(r, 3)
            if not w_item or not h_item:
                continue
            try:
                w = float(w_item.text())
                h = float(h_item.text())
                qty = int(qty_item.text()) if qty_item else 1
                label = des.text() if des else f'Дет.{r + 1}'
            except ValueError:
                continue
            for _ in range(qty):
                parts.append((w * gap, h * gap, label))

        if not parts:
            QMessageBox.warning(self, 'Раскрой', 'Добавьте заготовки.')
            return

        # Shelf-алгоритм
        parts.sort(key=lambda p: p[1], reverse=True)  # по высоте
        placed = []
        shelves = [(0.0, 0.0, sheet_w)]  # [(y, next_x, remaining_w)]

        for pw, ph, label in parts:
            placed_flag = False
            for si in range(len(shelves)):
                sy, sx, sw = shelves[si]
                if pw <= sw and sy + ph <= sheet_h:
                    placed.append((sx, sy, pw, ph, label))
                    shelves[si] = (sy, sx + pw, sw - pw)
                    placed_flag = True
                    break
            if not placed_flag:
                # Новый shelf
                prev_y = max(s[0] + max(p[3] for p in placed
                            if abs(p[1] - s[0]) < 0.1) if placed else 0
                             for s in shelves)
                # Упрощённо: берём max y из существующих shelves
                max_y = 0.0
                for s in shelves:
                    shelf_parts = [p for p in placed
                                   if abs(p[1] - s[0]) < 0.1]
                    if shelf_parts:
                        max_y = max(max_y, s[0] + max(p[3] for p in shelf_parts))
                new_y = max_y
                if new_y + ph > sheet_h:
                    continue
                placed.append((0.0, new_y, pw, ph, label))
                shelves.append((new_y, pw, sheet_w - pw))

        used_area = sum(p[2] * p[3] for p in placed)
        total = sheet_w * sheet_h
        util = used_area / total * 100 if total > 0 else 0

        self.canvas.set_data(sheet_w, sheet_h, placed, util)
