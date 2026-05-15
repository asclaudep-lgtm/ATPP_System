"""
v9-8 UI: Извещения об изменениях (ECN).
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QDialogButtonBox, QLineEdit, QComboBox, QTextEdit,
    QMessageBox, QInputDialog,
)

from database.models import (
    ECN, ECNApproval, ECNStatus, Product, TechProcess, SignerRole,
)
from modules import ecn as ecn_mod


class ECNDialog(QDialog):
    """Создание ECN."""
    def __init__(self, db_manager, *, current_user_id: int, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.user_id = current_user_id
        self.setWindowTitle('Новое извещение об изменении')
        self.setMinimumWidth(600)
        lay = QFormLayout(self)
        self.title = QLineEdit()
        self.product_cb = QComboBox()
        self.tp_cb = QComboBox()
        with self.db.get_session() as s:
            self.product_cb.addItem('— не указано —', None)
            for p in s.query(Product).order_by(Product.designation).limit(500):
                self.product_cb.addItem(f'{p.designation}  {p.name}', p.id)
            self.tp_cb.addItem('— не указан —', None)
            for tp in s.query(TechProcess).order_by(TechProcess.number).limit(500):
                self.tp_cb.addItem(tp.number, tp.id)
        self.reason = QTextEdit()
        self.change = QTextEdit()
        lay.addRow('Заголовок:', self.title)
        lay.addRow('ДСЕ:', self.product_cb)
        lay.addRow('ТП:', self.tp_cb)
        lay.addRow('Причина:', self.reason)
        lay.addRow('Предлагаемое изменение:', self.change)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)
        self.created_id: Optional[int] = None

    def _save(self):
        if not self.title.text().strip() or not self.reason.toPlainText().strip():
            QMessageBox.warning(self, 'ECN',
                                'Заголовок и причина обязательны.')
            return
        with self.db.get_session() as s:
            try:
                ecn = ecn_mod.create_ecn(
                    s,
                    title=self.title.text().strip(),
                    reason=self.reason.toPlainText().strip(),
                    proposed_change=self.change.toPlainText().strip(),
                    product_id=self.product_cb.currentData(),
                    tech_process_id=self.tp_cb.currentData(),
                    created_by=self.user_id,
                )
                s.commit()
                self.created_id = ecn.id
            except Exception as e:
                QMessageBox.warning(self, 'ECN', str(e))
                return
        self.accept()


class ECNWidget(QWidget):
    """Список ECN с действиями."""

    def __init__(self, db_manager, current_user_id: int = 0, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.user_id = current_user_id
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ['№', 'Заголовок', 'ДСЕ', 'Статус', 'Создан', 'Подписи'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        root.addWidget(self.table, 1)

        btns = QHBoxLayout()
        for label, cb in [('+ Новое ECN…', self._on_new),
                          ('▶ На согласование', self._on_submit),
                          ('✓ Согласовать (от роли)…', self._on_approve),
                          ('✗ Отклонить (от роли)…', self._on_reject),
                          ('✱ Отметить применённым', self._on_applied),
                          ('⟳ Обновить', self.refresh)]:
            b = QPushButton(label)
            b.clicked.connect(cb)
            btns.addWidget(b)
        btns.addStretch(1)
        root.addLayout(btns)

        self.hint = QLabel(
            'ECN — формальный запрос «изменить ТП». Маршрут: '
            'Гл. технолог → ОТК → Утверждающий. Каждая роль '
            'согласовывает / отклоняет. Когда все согласовали — '
            'статус APPROVED, после применения изменений — APPLIED.')
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

    def refresh(self):
        with self.db.get_session() as s:
            rows = ecn_mod.list_ecns(s)
            self._fill(rows)

    def _fill(self, rows):
        self.table.setRowCount(len(rows))
        for i, e in enumerate(rows):
            def _i(text, data=None):
                qi = QTableWidgetItem(str(text))
                if data is not None:
                    qi.setData(Qt.ItemDataRole.UserRole, data)
                return qi
            self.table.setItem(i, 0, _i(e.number, e.id))
            self.table.setItem(i, 1, _i(e.title))
            self.table.setItem(i, 2, _i(
                e.product.designation if e.product else ''))
            self.table.setItem(i, 3, _i(
                e.status.value if e.status else ''))
            self.table.setItem(i, 4, _i(
                e.created_at.strftime('%d.%m.%Y')
                if e.created_at else ''))
            sign = ', '.join(
                f'{a.role}: {a.decision or "—"}' for a in e.approvals)
            self.table.setItem(i, 5, _i(sign))
        self.table.resizeColumnsToContents()

    def _selected_id(self) -> Optional[int]:
        r = self.table.currentRow()
        if r < 0:
            return None
        it = self.table.item(r, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _on_new(self):
        dlg = ECNDialog(self.db, current_user_id=self.user_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_submit(self):
        eid = self._selected_id()
        if eid is None:
            return
        with self.db.get_session() as s:
            try:
                ecn_mod.submit_for_review(s, ecn_id=eid)
                s.commit()
            except ValueError as e:
                QMessageBox.warning(self, 'ECN', str(e))
                return
        self.refresh()

    def _decide(self, kind: str):
        eid = self._selected_id()
        if eid is None:
            return
        roles = [r.value for r in SignerRole]
        role, ok = QInputDialog.getItem(
            self, 'Роль', 'От какой роли подписать:', roles, 0, False)
        if not ok:
            return
        comment, ok = QInputDialog.getMultiLineText(
            self, 'Комментарий', 'Комментарий (опционально):', '')
        with self.db.get_session() as s:
            try:
                if kind == 'approve':
                    ecn_mod.approve(s, ecn_id=eid, role=role,
                                    user_id=self.user_id,
                                    comment=comment if ok else '')
                else:
                    ecn_mod.reject(s, ecn_id=eid, role=role,
                                   user_id=self.user_id,
                                   comment=comment if ok else '')
                s.commit()
            except ValueError as e:
                QMessageBox.warning(self, 'ECN', str(e))
                return
        self.refresh()

    def _on_approve(self):
        self._decide('approve')

    def _on_reject(self):
        self._decide('reject')

    def _on_applied(self):
        eid = self._selected_id()
        if eid is None:
            return
        with self.db.get_session() as s:
            try:
                ecn_mod.mark_applied(s, ecn_id=eid)
                s.commit()
            except ValueError as e:
                QMessageBox.warning(self, 'ECN', str(e))
                return
        self.refresh()
