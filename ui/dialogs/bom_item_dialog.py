"""Диалог добавления/редактирования строки БОМ."""
from PyQt6.QtWidgets import (QDialog, QFormLayout, QComboBox, QSpinBox,
                              QLineEdit, QDialogButtonBox, QMessageBox)
from database.models import AssemblyLevel, Product


class BOMItemDialog(QDialog):
    """Добавление или редактирование элемента БOM."""

    def __init__(self, db_manager, parent_id=None, bom_item_id=None,
                 parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._parent_id = parent_id
        self._bom_item_id = bom_item_id
        self._editing = bom_item_id is not None
        self.setWindowTitle(
            'Редактировать компонент' if self._editing
            else 'Добавить компонент')
        self.setMinimumWidth(400)
        self._init_ui()

    def _init_ui(self):
        layout = QFormLayout(self)

        # Product selector
        self.product_cb = QComboBox()
        self.product_cb.setEditable(True)
        with self.db_manager.get_session() as s:
            for p in s.query(Product).filter(
                Product.is_deleted == False
            ).order_by(Product.designation).all():
                self.product_cb.addItem(
                    f'{p.designation} — {p.name}', p.id)
        layout.addRow('Изделие:', self.product_cb)

        # Level
        self.level_cb = QComboBox()
        for lev in AssemblyLevel:
            self.level_cb.addItem(lev.value, lev)
        layout.addRow('Уровень:', self.level_cb)

        # Quantity
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 99999)
        self.qty_spin.setValue(1)
        layout.addRow('Количество:', self.qty_spin)

        # Position
        self.pos_edit = QLineEdit()
        self.pos_edit.setPlaceholderText('напр. поз.1')
        layout.addRow('Позиция:', self.pos_edit)

        # Note
        self.note_edit = QLineEdit()
        layout.addRow('Примечание:', self.note_edit)

        # Load existing if editing
        if self._editing:
            with self.db_manager.get_session() as s:
                from database.models import BOMItem
                item = s.query(BOMItem).get(self._bom_item_id)
                if item:
                    idx = self.product_cb.findData(item.product_id)
                    if idx >= 0:
                        self.product_cb.setCurrentIndex(idx)
                    lev_idx = self.level_cb.findData(item.level)
                    if lev_idx >= 0:
                        self.level_cb.setCurrentIndex(lev_idx)
                    self.qty_spin.setValue(item.quantity)
                    self.pos_edit.setText(item.position or '')
                    self.note_edit.setText(item.note or '')

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_ok(self):
        if self.product_cb.currentData() is None:
            QMessageBox.warning(self, 'Ошибка', 'Выберите изделие')
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            'parent_id': self._parent_id,
            'product_id': self.product_cb.currentData(),
            'level': self.level_cb.currentData(),
            'quantity': self.qty_spin.value(),
            'position': self.pos_edit.text().strip() or None,
            'note': self.note_edit.text().strip() or None,
        }
