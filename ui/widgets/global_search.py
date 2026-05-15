"""
Глобальный поиск по сущностям БД.

Ищет по: ТП (number, version), изделия (designation, name),
операции (name, code, note), переходы (text, code), материалы (name, brand).
Двойной клик по строке — пытается открыть соответствующий ТП.
"""
from typing import List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)

from database.models import (
    TechProcess, Product, Operation, Transition, Material, Equipment,
    WorkOrder, WorkOrderItem,
)


class GlobalSearchWidget(QWidget):

    tp_open = pyqtSignal(int)

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        top = QHBoxLayout()
        top.addWidget(QLabel('<b>Глобальный поиск</b>'))
        self.q_in = QLineEdit()
        self.q_in.setPlaceholderText(
            'Введите часть текста: обозначение, номер ТП, название операции, '
            'марка материала, модель станка…'
        )
        self.q_in.returnPressed.connect(self._search)
        top.addWidget(self.q_in, 1)
        b = QPushButton('🔎 Искать')
        b.setDefault(True)
        b.clicked.connect(self._search)
        top.addWidget(b)
        layout.addLayout(top)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(
            ['Тип', 'Идентификация', 'Описание', 'ТП', 'Действие']
        )
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.horizontalHeader().setStretchLastSection(False)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.doubleClicked.connect(self._on_dbl)
        layout.addWidget(self.tbl, 1)

        self._info = QLabel('—')
        layout.addWidget(self._info)

    def _search(self):
        q = self.q_in.text().strip()
        if len(q) < 2:
            self._info.setText('Введите минимум 2 символа.')
            return
        like = f'%{q}%'
        self.tbl.setRowCount(0)
        with self.db.get_session() as s:
            # ТП по номеру
            for tp in (s.query(TechProcess)
                       .filter(TechProcess.number.ilike(like) |
                               TechProcess.version.ilike(like) |
                               TechProcess.execution_variant.ilike(like))
                       .filter((TechProcess.is_deleted == False) |
                               (TechProcess.is_deleted.is_(None)))
                       .limit(100).all()):
                self._add(
                    'ТП', tp.number,
                    f'Версия {tp.version or "—"} '
                    f'Вариант: {tp.execution_variant or "—"} '
                    f'Изделие: {tp.product.designation if tp.product else "—"}',
                    tp.id, tp.id,
                )
            # Изделия по designation/name (только живые)
            for p in (s.query(Product)
                      .filter(Product.designation.ilike(like) |
                              Product.name.ilike(like))
                      .filter((Product.is_deleted == False) |
                              (Product.is_deleted.is_(None)))
                      .limit(100).all()):
                tp = s.query(TechProcess).filter_by(product_id=p.id).first()
                tp_id = tp.id if tp else None
                self._add('Изделие', p.designation,
                          p.name or '', tp_id, tp_id)
            # Операции
            for op in (s.query(Operation)
                       .filter(Operation.name.ilike(like) |
                               Operation.code.ilike(like) |
                               Operation.note.ilike(like))
                       .filter((Operation.is_deleted == False) |
                               (Operation.is_deleted.is_(None)))
                       .limit(200).all()):
                tp = op.tech_process
                self._add('Операция', f'{op.number}  {op.name or ""}',
                          (op.note or '')[:100],
                          (tp.number if tp else ''),
                          (tp.id if tp else None))
            # Переходы
            for t in (s.query(Transition)
                      .filter(Transition.text.ilike(like) |
                              Transition.code.ilike(like))
                      .limit(200).all()):
                op = t.operation
                tp = op.tech_process if op else None
                self._add('Переход', f'№{t.number}',
                          (t.text or '')[:140],
                          (tp.number if tp else ''),
                          (tp.id if tp else None))
            # Материалы
            for m in (s.query(Material)
                      .filter(Material.name.ilike(like) |
                              Material.grade.ilike(like) |
                              Material.gost.ilike(like))
                      .limit(50).all()):
                self._add('Материал', m.grade or m.name or '',
                          f'{m.name or ""}  ГОСТ {m.gost or "—"}',
                          '', None)
            # Оборудование
            for e in (s.query(Equipment)
                      .filter(Equipment.name.ilike(like) |
                              Equipment.model.ilike(like))
                      .limit(50).all()):
                self._add('Оборудование', e.model or e.name or '',
                          e.name or '', '', None)

            # Производственные наряды (D19: расширение поиска).
            for wo in (s.query(WorkOrder)
                       .filter(WorkOrder.number.ilike(like))
                       .limit(50).all()):
                tp = wo.tech_process
                self._add('Наряд', wo.number,
                          (f'Кол-во: {wo.quantity_total}, '
                           f'статус: {wo.status.value}'),
                          (tp.number if tp else ''),
                          (tp.id if tp else None))
            # Партии (по штрих-коду / serial)
            for it in (s.query(WorkOrderItem)
                       .filter(WorkOrderItem.barcode.ilike(like) |
                               WorkOrderItem.serial.ilike(like))
                       .limit(50).all()):
                wo = it.work_order
                tp = wo.tech_process if wo else None
                self._add('Партия', it.serial or it.barcode or f'#{it.id}',
                          (f'Кол-во: {it.qty_total}, '
                           f'наряд: {wo.number if wo else "—"}'),
                          (tp.number if tp else ''),
                          (tp.id if tp else None))

        self.tbl.resizeColumnsToContents()
        self._info.setText(f'Найдено строк: {self.tbl.rowCount()}.')

    def _add(self, kind: str, ident: str, desc: str,
             tp_label, tp_id):
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        self.tbl.setItem(r, 0, QTableWidgetItem(kind))
        self.tbl.setItem(r, 1, QTableWidgetItem(str(ident)))
        self.tbl.setItem(r, 2, QTableWidgetItem(desc))
        self.tbl.setItem(r, 3, QTableWidgetItem(str(tp_label) if tp_label else ''))
        action_item = QTableWidgetItem(
            'Открыть ТП' if tp_id else ''
        )
        action_item.setData(Qt.ItemDataRole.UserRole, tp_id)
        self.tbl.setItem(r, 4, action_item)

    def _on_dbl(self, idx):
        row = idx.row()
        action_item = self.tbl.item(row, 4)
        if action_item is None:
            return
        tp_id = action_item.data(Qt.ItemDataRole.UserRole)
        if tp_id:
            self.tp_open.emit(int(tp_id))
