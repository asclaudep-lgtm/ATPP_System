"""Виджет редактора многоуровневого БОМ."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QTreeWidget, QTreeWidgetItem, QPushButton,
                              QMessageBox)
from PyQt6.QtCore import pyqtSignal

from modules.bom import (get_bom_tree, get_bom_flat, add_bom_item,
                          remove_bom_item, update_bom_item, validate_bom,
                          BOMNode)
from database.models import AssemblyLevel


class BOMWidget(QWidget):
    """Иерархический редактор БОМ."""

    bom_changed = pyqtSignal()

    def __init__(self, db_manager, product_id: int, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.product_id = product_id
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        tb = QHBoxLayout()
        self.add_btn = QPushButton('+ Добавить компонент')
        self.add_btn.clicked.connect(self._add_item)
        tb.addWidget(self.add_btn)

        self.edit_btn = QPushButton('✎ Изменить')
        self.edit_btn.clicked.connect(self._edit_item)
        tb.addWidget(self.edit_btn)

        self.del_btn = QPushButton('✕ Удалить')
        self.del_btn.clicked.connect(self._delete_item)
        tb.addWidget(self.del_btn)

        self.validate_btn = QPushButton('✔ Проверить')
        self.validate_btn.clicked.connect(self._validate)
        tb.addWidget(self.validate_btn)

        tb.addStretch()
        layout.addLayout(tb)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            'Уровень', 'Обозначение', 'Наименование',
            'Кол-во', 'Поз.', 'Есть ТП',
        ])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 150)
        self.tree.setColumnWidth(2, 200)
        self.tree.setColumnWidth(3, 60)
        self.tree.setColumnWidth(4, 60)
        self.tree.setColumnWidth(5, 60)
        self.tree.itemDoubleClicked.connect(self._on_item_double_click)
        layout.addWidget(self.tree)

    def refresh(self):
        self.tree.clear()
        with self.db_manager.get_session() as s:
            tree = get_bom_tree(s, product_id=self.product_id)
            self._populate_tree(tree)

    def _populate_tree(self, nodes, parent=None):
        for node in nodes:
            item = QTreeWidgetItem(parent or self.tree)
            item.setText(0, node.level)
            item.setText(1, node.product_designation)
            item.setText(2, node.product_name)
            item.setText(3, str(node.quantity))
            item.setText(4, node.position or '')
            item.setText(5, '✓' if node.has_tp else '—')
            item.setData(0, 1, node.id)  # Store bom_item_id
            item.setData(0, 2, node.product_id)  # Store product_id
            self._populate_tree(node.children, item)

    def _add_item(self):
        from ui.dialogs.bom_item_dialog import BOMItemDialog
        item = self.tree.currentItem()
        parent_id = item.data(0, 1) if item else None
        dlg = BOMItemDialog(self.db_manager, parent_id=parent_id,
                            parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        data = dlg.get_data()
        try:
            with self.db_manager.get_session() as s:
                add_bom_item(s, **data)
            self.refresh()
            self.bom_changed.emit()
        except ValueError as e:
            QMessageBox.warning(self, 'Ошибка', str(e))

    def _edit_item(self):
        item = self.tree.currentItem()
        if item is None:
            return
        bom_id = item.data(0, 1)
        from ui.dialogs.bom_item_dialog import BOMItemDialog
        dlg = BOMItemDialog(self.db_manager,
                            bom_item_id=bom_id, parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        data = dlg.get_data()
        try:
            with self.db_manager.get_session() as s:
                update_bom_item(s, bom_item_id=bom_id, **data)
            self.refresh()
            self.bom_changed.emit()
        except ValueError as e:
            QMessageBox.warning(self, 'Ошибка', str(e))

    def _delete_item(self):
        item = self.tree.currentItem()
        if item is None:
            return
        bom_id = item.data(0, 1)
        reply = QMessageBox.question(
            self, 'Удаление',
            'Удалить компонент и все его дочерние элементы?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        with self.db_manager.get_session() as s:
            remove_bom_item(s, bom_item_id=bom_id)
        self.refresh()
        self.bom_changed.emit()

    def _validate(self):
        with self.db_manager.get_session() as s:
            warnings = validate_bom(s, product_id=self.product_id)
        if warnings:
            QMessageBox.warning(
                self, 'Проверка БОМ',
                'Предупреждения:\n' + '\n'.join(f'• {w}' for w in warnings),
            )
        else:
            QMessageBox.information(self, 'Проверка БОМ', 'Ошибок нет.')

    def _on_item_double_click(self, item, col):
        product_id = item.data(0, 2)
        if product_id:
            # Открыть карточку изделия
            pass
