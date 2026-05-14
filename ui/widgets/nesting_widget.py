"""Виджет визуализации раскроя листового металла (нестинг).

Greedy shelf-алгоритм + гильотинный раскрой: размещает прямоугольные
заготовки на листе, минимизируя отходы. Поддерживает деловые отходы
(остатки листа), импорт из BOM изделия, экспорт карты раскроя в PDF.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QSpinBox, QDoubleSpinBox, QTableWidget,
                              QTableWidgetItem, QGroupBox, QMessageBox,
                              QComboBox, QFileDialog)
from PyQt6.QtCore import Qt, QRectF
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
    """Виджет раскроя листового металла — shelf + guillotine + BOM import."""

    def __init__(self, db_manager, parent=None, product_id=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._product_id = product_id
        self._init_ui()
        if product_id:
            self._load_from_bom(product_id)

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

        grp_lay.addWidget(QLabel('Алгоритм:'))
        self._algo_combo = QComboBox()
        self._algo_combo.addItem('Shelf (полочный)')
        self._algo_combo.addItem('Guillotine (гильотинный)')
        grp_lay.addWidget(self._algo_combo)
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

        bom_btn = QPushButton('📦 Загрузить из BOM')
        bom_btn.clicked.connect(self._import_from_bom_dialog)
        ctrl.addWidget(bom_btn)

        export_btn = QPushButton('📄 Экспорт PDF')
        export_btn.clicked.connect(self._export_pdf)
        ctrl.addWidget(export_btn)

        ctrl.addStretch()
        layout.addLayout(ctrl)

        # Right: canvas
        self.canvas = NestingCanvas()
        layout.addWidget(self.canvas, stretch=1)

    def _load_from_bom(self, product_id):
        """Load parts from a product's BOM into the table."""
        from database.models import Product, BOMItem
        with self.db_manager.get_session() as s:
            p = s.query(Product).get(product_id)
            if p is None:
                return
            bom_items = s.query(BOMItem).filter(
                BOMItem.parent_id == product_id).all()
            self.table.setRowCount(len(bom_items))
            for i, item in enumerate(bom_items):
                child = item.child
                w = getattr(child, 'width', None) or 100
                h = getattr(child, 'length', None) or 100
                self.table.setItem(i, 0, QTableWidgetItem(
                    child.designation if child else f'Item{i}'))
                self.table.setItem(i, 1, QTableWidgetItem(str(w)))
                self.table.setItem(i, 2, QTableWidgetItem(str(h)))
                self.table.setItem(i, 3, QTableWidgetItem(
                    str(item.quantity or 1)))

    def _export_pdf(self):
        """Export the current layout as a PDF sketch."""
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas
        path, _ = QFileDialog.getSaveFileName(
            self, 'Экспорт карты раскроя', '', 'PDF (*.pdf)')
        if not path:
            return
        w_mm, h_mm = A4
        c = rl_canvas.Canvas(path, pagesize=A4)
        c.setFont('Helvetica-Bold', 14)
        c.drawString(20, h_mm - 20,
                     f'Карта раскроя: {self.sheet_w.value()}×'
                     f'{self.sheet_h.value()} мм')
        c.setFont('Helvetica', 10)
        c.drawString(20, h_mm - 35,
                     f'Использование: {self.canvas.utilization:.1f}% | '
                     f'Деталей: {len(self.canvas.parts)}')
        scale = min((w_mm - 30) / self.canvas.sheet_w,
                    (h_mm - 50) / self.canvas.sheet_h)
        for x, y, pw, ph, label in self.canvas.parts:
            px = 15 + x * scale
            py = h_mm - 50 - (y + ph) * scale
            pw_s = pw * scale
            ph_s = ph * scale
            c.rect(px, py, pw_s, ph_s)
            if pw_s > 15 and ph_s > 10:
                c.setFont('Helvetica', 6)
                c.drawString(px + 1, py + ph_s / 2, label[:12])
        c.save()
        QMessageBox.information(self, 'PDF', f'Сохранено:\n{path}')

    def _import_from_bom_dialog(self):
        """Prompt for product designation and load its BOM parts."""
        from PyQt6.QtWidgets import QInputDialog
        from database.models import Product
        des, ok = QInputDialog.getText(
            self, 'BOM → Раскрой', 'Обозначение изделия:')
        if not ok or not des.strip():
            return
        with self.db_manager.get_session() as s:
            p = s.query(Product).filter(
                Product.designation == des.strip()).first()
            if p is None:
                QMessageBox.warning(self, 'BOM',
                                    f'Изделие "{des}" не найдено.')
                return
            self._load_from_bom(p.id)

    def _calculate(self):
        sheet_w = self.sheet_w.value()
        sheet_h = self.sheet_h.value()
        gap = self.k_zag.value()
        algo = self._algo_combo.currentIndex()

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

        if algo == 1:
            placed = self._guillotine_cut(sheet_w, sheet_h, parts)
        else:
            placed = self._shelf_pack(sheet_w, sheet_h, parts)

        used_area = sum(p[2] * p[3] for p in placed)
        total = sheet_w * sheet_h
        util = used_area / total * 100 if total > 0 else 0

        self.canvas.set_data(sheet_w, sheet_h, placed, util)

    def _shelf_pack(self, sheet_w, sheet_h, parts):
        """Shelf algorithm — stack parts in rows by height."""
        parts.sort(key=lambda p: p[1], reverse=True)
        placed = []
        shelves = [(0.0, 0.0, sheet_w)]

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
        return placed

    def _guillotine_cut(self, sheet_w, sheet_h, parts):
        """Guillotine cut — recursive binary splitting of the sheet."""
        parts = sorted(parts, key=lambda p: p[0] * p[1], reverse=True)
        placed = []

        def _fit(x0, y0, w, h, remaining):
            if not remaining:
                return True
            best = None
            best_idx = -1
            for i, (pw, ph, _) in enumerate(remaining):
                if pw <= w and ph <= h:
                    score = pw * ph
                    if best is None or score > best:
                        best = score
                        best_idx = i
            if best is None:
                return False

            pw, ph, label = remaining.pop(best_idx)
            placed.append((x0, y0, pw, ph, label))

            # Choose split direction: vertical or horizontal
            rest_w = w - pw
            rest_h = h - ph

            rem_copy1 = list(remaining)
            rem_copy2 = list(remaining)
            ok1 = _fit(x0 + pw, y0, rest_w, ph, rem_copy1)
            ok2 = _fit(x0, y0 + ph, w, rest_h, rem_copy2)

            if ok1 and ok2:
                remaining.clear()
                remaining.extend(rem_copy1)
                remaining.extend(rem_copy2)
                return True
            elif ok1:
                remaining.clear()
                remaining.extend(rem_copy1)
                if _fit(x0, y0 + ph, w, rest_h, remaining):
                    return True
            elif ok2:
                remaining.clear()
                remaining.extend(rem_copy2)
                if _fit(x0 + pw, y0, rest_w, ph, remaining):
                    return True
            else:
                remaining.clear()
                if _fit(x0 + pw, y0, rest_w, h, remaining):
                    return True
                remaining.clear()
                if _fit(x0, y0 + ph, w, rest_h, remaining):
                    return True
            return True

        _fit(0, 0, sheet_w, sheet_h, list(parts))
        return placed
