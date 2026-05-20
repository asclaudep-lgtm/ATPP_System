"""
Диалог выбора операции из произвольного ТП. Используется для импорта
операции из соседнего ТП в текущий.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from database.models import TechProcess


class OpPickerDialog(QDialog):
    def __init__(self, db_manager, exclude_tp_id: int | None = None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.exclude_tp_id = exclude_tp_id
        self.selected_op_id: int | None = None

        self.setWindowTitle('Импорт операции из ТП')
        self.resize(720, 520)

        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(
            'Выберите операцию из любого другого ТП. Будут перенесены '
            'параметры операции и все её переходы.'
        ))

        self._search = QLineEdit()
        self._search.setPlaceholderText('Поиск: обозначение, наименование, № операции…')
        self._search.textChanged.connect(self._filter)
        lay.addWidget(self._search)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([
            'ТП / Операция', '№ оп.', 'Оборудование', 'Тшт', 'Переходов',
        ])
        self._tree.setColumnWidth(0, 360)
        self._tree.setColumnWidth(1, 60)
        self._tree.setColumnWidth(2, 160)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        lay.addWidget(self._tree, 1)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._ok_btn = bb.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setEnabled(False)
        self._tree.itemSelectionChanged.connect(self._update_ok)

        self._populate()

    def _populate(self):
        self._tree.clear()
        with self.db_manager.get_session() as s:
            q = s.query(TechProcess).order_by(TechProcess.id)
            if self.exclude_tp_id is not None:
                q = q.filter(TechProcess.id != self.exclude_tp_id)
            tps = q.all()
            for tp in tps:
                product = tp.product
                ops = sorted(tp.operations, key=lambda o: (o.sort_order or 0))
                if not ops:
                    continue
                title = (
                    f"{product.designation if product else '—'}  "
                    f"{product.name if product else ''}    "
                    f"({tp.number}{' · ' + tp.execution_variant if tp.execution_variant else ''})"
                )
                tp_item = QTreeWidgetItem([title, '', '', '', f'{len(ops)}'])
                tp_item.setData(0, Qt.ItemDataRole.UserRole, ('tp', tp.id))
                self._tree.addTopLevelItem(tp_item)
                for op in ops:
                    eq_name = op.equipment.name if op.equipment else ''
                    tshtm = f'{op.t_piece:.2f}' if op.t_piece else ''
                    tr_count = len(op.transitions or [])
                    op_item = QTreeWidgetItem([
                        op.name, op.number, eq_name, tshtm, f'{tr_count}'
                    ])
                    op_item.setData(0, Qt.ItemDataRole.UserRole, ('op', op.id))
                    tp_item.addChild(op_item)

    def _filter(self, txt: str):
        txt = (txt or '').lower().strip()

        def visit(item: QTreeWidgetItem) -> bool:
            self_match = any(
                txt in (item.text(c) or '').lower()
                for c in range(item.columnCount())
            )
            child_visible = False
            for i in range(item.childCount()):
                if visit(item.child(i)):
                    child_visible = True
            visible = (self_match or child_visible) if txt else True
            item.setHidden(not visible)
            if visible and txt:
                item.setExpanded(True)
            return visible

        for i in range(self._tree.topLevelItemCount()):
            visit(self._tree.topLevelItem(i))

    def _update_ok(self):
        items = self._tree.selectedItems()
        ok = False
        if items:
            data = items[0].data(0, Qt.ItemDataRole.UserRole)
            ok = isinstance(data, tuple) and data[0] == 'op'
        self._ok_btn.setEnabled(ok)

    def _on_double_click(self, item, col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple) and data[0] == 'op':
            self.selected_op_id = data[1]
            self.accept()

    def _on_ok(self):
        items = self._tree.selectedItems()
        if not items:
            return
        data = items[0].data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple) and data[0] == 'op':
            self.selected_op_id = data[1]
            self.accept()
