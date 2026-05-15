"""
TPCompareDialog — окно сравнения двух вариантов ТП бок-о-бок.

Показывает таблицы операций двух ТП в две колонки. Подсвечивает
различия в названии операции, оборудовании и нормах времени.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QSplitter, QWidget,
)

from database.models import TechProcess, Operation, TPStatus


# Цвета подсветки
COLOR_SAME = QColor('#ffffff')
COLOR_DIFF = QColor('#fff3cd')  # жёлтый — есть различия
COLOR_ONLY_LEFT = QColor('#d4edda')   # зелёный — только в левом
COLOR_ONLY_RIGHT = QColor('#f8d7da')  # красный — только в правом


class TPCompareDialog(QDialog):
    """Диалог сравнения двух вариантов ТП."""

    def __init__(self, db_manager, tp_id_left: int, tp_id_right: int, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.tp_id_left = tp_id_left
        self.tp_id_right = tp_id_right

        self.setWindowTitle("Сравнение вариантов ТП")
        self.resize(1300, 700)
        self._init_ui()
        self._load()

    def _init_ui(self):
        root = QVBoxLayout(self)

        # Заголовок с названиями двух вариантов
        self.header = QLabel("")
        root.addWidget(self.header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tbl_left = self._make_table()
        self.tbl_right = self._make_table()

        # Синхронизация прокрутки
        self.tbl_left.verticalScrollBar().valueChanged.connect(
            self.tbl_right.verticalScrollBar().setValue)
        self.tbl_right.verticalScrollBar().valueChanged.connect(
            self.tbl_left.verticalScrollBar().setValue)

        splitter.addWidget(self._wrap_table("Вариант 1 (левый)", self.tbl_left))
        splitter.addWidget(self._wrap_table("Вариант 2 (правый)", self.tbl_right))
        splitter.setSizes([650, 650])
        root.addWidget(splitter, 1)

        # Подвал с легендой и кнопкой закрытия
        footer = QHBoxLayout()
        legend = QLabel(
            '<span style="background:#fff3cd; padding:2px 6px;">  </span> различия  '
            '<span style="background:#d4edda; padding:2px 6px;">  </span> только в левом  '
            '<span style="background:#f8d7da; padding:2px 6px;">  </span> только в правом'
        )
        footer.addWidget(legend)
        footer.addStretch()

        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        root.addLayout(footer)

    def _wrap_table(self, title: str, tbl: QTableWidget) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(2, 2, 2, 2)
        title_lbl = QLabel(title)
        l.addWidget(title_lbl)
        l.addWidget(tbl)
        return w

    def _make_table(self) -> QTableWidget:
        t = QTableWidget()
        t.setColumnCount(5)
        t.setHorizontalHeaderLabels(
            ["№", "Наименование операции", "Оборудование",
             "Тпз, мин", "Тшт, мин"])
        t.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive)
        t.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        t.setEditTriggers(t.EditTrigger.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.verticalHeader().setVisible(False)
        return t

    def _load(self):
        s = self.db_manager.Session()
        try:
            tp_l = s.get(TechProcess, self.tp_id_left)
            tp_r = s.get(TechProcess, self.tp_id_right)
            if not tp_l or not tp_r:
                self.header.setText("Не удалось загрузить ТП.")
                return

            self.header.setText(
                f"<b>Слева:</b> {tp_l.number} · "
                f"{(tp_l.execution_variant or 'Основной')} · "
                f"v{tp_l.version or '1.0'} · {tp_l.status.value}<br>"
                f"<b>Справа:</b> {tp_r.number} · "
                f"{(tp_r.execution_variant or 'Основной')} · "
                f"v{tp_r.version or '1.0'} · {tp_r.status.value}"
            )

            ops_l = self._collect_ops(s, self.tp_id_left)
            ops_r = self._collect_ops(s, self.tp_id_right)
        finally:
            s.close()

        # Выравниваем по номеру операции
        nums = sorted(set(list(ops_l.keys()) + list(ops_r.keys())),
                      key=lambda x: (len(x), x))
        self.tbl_left.setRowCount(len(nums))
        self.tbl_right.setRowCount(len(nums))

        for i, num in enumerate(nums):
            l = ops_l.get(num)
            r = ops_r.get(num)
            self._fill_row(self.tbl_left, i, num, l, r, side='left')
            self._fill_row(self.tbl_right, i, num, r, l, side='right')

    def _collect_ops(self, session, tp_id: int) -> dict:
        ops = (session.query(Operation)
               .filter(Operation.tech_process_id == tp_id,
                       (Operation.is_deleted == False)
                       | (Operation.is_deleted.is_(None)))
               .order_by(Operation.sort_order)
               .all())
        result = {}
        for op in ops:
            equip = op.equipment.name if op.equipment else ''
            if op.equipment and op.equipment.model:
                equip = f"{equip} {op.equipment.model}"
            result[op.number] = {
                'name': op.name or '',
                'equip': equip,
                't_setup': op.t_setup or 0,
                't_piece': op.t_piece or 0,
            }
        return result

    def _fill_row(self, tbl, row, num, op, other, side):
        if op is None:
            tbl.setItem(row, 0, self._cell(num, COLOR_ONLY_RIGHT
                                           if side == 'right' else COLOR_ONLY_LEFT))
            for c in range(1, 5):
                tbl.setItem(row, c, self._cell('—', COLOR_ONLY_RIGHT
                                               if side == 'right'
                                               else COLOR_ONLY_LEFT))
            return

        # Подсветка по различиям (если other нет — другой стороне)
        if other is None:
            color = COLOR_ONLY_LEFT if side == 'left' else COLOR_ONLY_RIGHT
            color_name = color
            color_equip = color
            color_tsetup = color
            color_tpiece = color
        else:
            color_name = COLOR_DIFF if op['name'] != other['name'] else COLOR_SAME
            color_equip = COLOR_DIFF if op['equip'] != other['equip'] else COLOR_SAME
            color_tsetup = COLOR_DIFF if op['t_setup'] != other['t_setup'] else COLOR_SAME
            color_tpiece = COLOR_DIFF if op['t_piece'] != other['t_piece'] else COLOR_SAME

        tbl.setItem(row, 0, self._cell(num, COLOR_SAME))
        tbl.setItem(row, 1, self._cell(op['name'], color_name))
        tbl.setItem(row, 2, self._cell(op['equip'] or '—', color_equip))
        tbl.setItem(row, 3, self._cell(f"{op['t_setup']:.2f}", color_tsetup))
        tbl.setItem(row, 4, self._cell(f"{op['t_piece']:.2f}", color_tpiece))

    @staticmethod
    def _cell(text, bg) -> QTableWidgetItem:
        it = QTableWidgetItem(str(text))
        it.setBackground(QBrush(bg))
        return it
