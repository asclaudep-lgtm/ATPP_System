"""
Диалог массового изменения операций.

Пользователь отмечает чекбокс рядом с полем — это значит «применить ко
всем выбранным операциям». Если чекбокс снят — поле не трогается.
"""
from typing import Dict, Iterable, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, QLabel, QCheckBox,
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDialogButtonBox,
    QMessageBox,
)

from database.models import Equipment, Profession


class BulkEditOpsDialog(QDialog):

    def __init__(self, db_manager, op_ids: List[int], parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.op_ids = list(op_ids)
        self.changes: Dict = {}

        self.setWindowTitle(f'Массовое изменение — {len(op_ids)} оп.')
        self.setMinimumWidth(520)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f'Выбрано операций: <b>{len(self.op_ids)}</b><br>'
            f'Отметьте чекбоксы напротив полей, которые нужно применить.'
        ))

        form = QFormLayout()

        self.shop_chk = QCheckBox()
        self.shop_in = QLineEdit()
        self.shop_in.setPlaceholderText('Цех 10, Участок 3...')
        form.addRow(self._row(self.shop_chk, 'Цех / участок:'), self.shop_in)

        # Оборудование
        self.eq_chk = QCheckBox()
        self.eq_cb = QComboBox()
        self.eq_cb.addItem('—', None)
        with self.db.get_session() as s:
            for e in s.query(Equipment).order_by(Equipment.name).all():
                label = e.name + (f' [{e.model}]' if e.model else '')
                self.eq_cb.addItem(label, e.id)
            profs = s.query(Profession).order_by(Profession.name).all()
        form.addRow(self._row(self.eq_chk, 'Оборудование:'), self.eq_cb)

        # Профессия
        self.pr_chk = QCheckBox()
        self.pr_cb = QComboBox()
        self.pr_cb.addItem('—', None)
        for p in profs:
            self.pr_cb.addItem(p.name, p.id)
        form.addRow(self._row(self.pr_chk, 'Профессия:'), self.pr_cb)

        self.gr_chk = QCheckBox()
        self.gr_in = QSpinBox()
        self.gr_in.setRange(1, 8)
        form.addRow(self._row(self.gr_chk, 'Разряд:'), self.gr_in)

        self.tpz_chk = QCheckBox()
        self.tpz_in = QDoubleSpinBox()
        self.tpz_in.setRange(0, 99999)
        self.tpz_in.setSuffix(' мин')
        form.addRow(self._row(self.tpz_chk, 'Тпз:'), self.tpz_in)

        self.tsh_chk = QCheckBox()
        self.tsh_in = QDoubleSpinBox()
        self.tsh_in.setRange(0, 99999)
        self.tsh_in.setSuffix(' мин')
        form.addRow(self._row(self.tsh_chk, 'Тшт:'), self.tsh_in)

        # Включать в МТП
        self.mtp_chk = QCheckBox()
        self.mtp_cb = QComboBox()
        self.mtp_cb.addItem('Да — включать', True)
        self.mtp_cb.addItem('Нет — не включать', False)
        form.addRow(self._row(self.mtp_chk, 'Выдавать в МТП:'), self.mtp_cb)

        layout.addLayout(form)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Apply).setText('Применить ко всем')
        bb.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    @staticmethod
    def _row(chk: QCheckBox, label: str):
        from PyQt6.QtWidgets import QWidget
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(chk)
        h.addWidget(QLabel(label))
        h.addStretch()
        return w

    def _on_apply(self):
        changes = {}
        if self.shop_chk.isChecked():
            changes['shop'] = self.shop_in.text().strip() or None
        if self.eq_chk.isChecked():
            changes['equipment_id'] = self.eq_cb.currentData()
        if self.pr_chk.isChecked():
            changes['profession_id'] = self.pr_cb.currentData()
        if self.gr_chk.isChecked():
            changes['grade'] = self.gr_in.value()
        if self.tpz_chk.isChecked():
            changes['t_setup'] = self.tpz_in.value()
        if self.tsh_chk.isChecked():
            changes['t_piece'] = self.tsh_in.value()
        if self.mtp_chk.isChecked():
            changes['include_in_mtp'] = bool(self.mtp_cb.currentData())

        if not changes:
            QMessageBox.information(
                self, 'Массовое изменение',
                'Не выбрано ни одного поля для изменения. Отметьте чекбоксы.'
            )
            return

        from database.models import Operation
        with self.db.get_session() as s:
            updated = (s.query(Operation)
                       .filter(Operation.id.in_(self.op_ids))
                       .update(changes, synchronize_session=False))

        QMessageBox.information(
            self, 'Готово',
            f'Изменено операций: {updated}\n'
            f'Изменённые поля: {", ".join(changes.keys())}'
        )
        self.changes = changes
        self.accept()
