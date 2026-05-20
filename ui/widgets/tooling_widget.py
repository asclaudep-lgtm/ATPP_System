"""
v9-4 UI: Учёт оснастки и её выдача / возврат.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.models import (
    ToolingItem,
    ToolingStatus,
    User,
    WorkOrder,
)
from modules import tooling


class ToolingItemDialog(QDialog):
    def __init__(self, db_manager, *, item: Optional[ToolingItem] = None,
                 parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.item_id = item.id if item else None
        self.setWindowTitle(
            'Редактирование оснастки' if item else 'Новая оснастка')
        self.setMinimumWidth(500)
        lay = QFormLayout(self)
        self.inv = QLineEdit(item.inventory_no if item else '')
        self.name = QLineEdit(item.name if item else '')
        self.desc = QTextEdit()
        if item and item.description:
            self.desc.setPlainText(item.description)
        self.loc = QLineEdit(item.location if item else '')
        self.status = QComboBox()
        for st in ToolingStatus:
            self.status.addItem(st.value, st)
            if item and item.status == st:
                self.status.setCurrentIndex(self.status.count() - 1)
        self.wear = QSpinBox()
        self.wear.setRange(0, 100)
        self.wear.setSuffix(' %')
        self.wear.setValue(int(item.wear_percent or 0) if item else 0)

        lay.addRow('Инв.№:', self.inv)
        lay.addRow('Наименование:', self.name)
        lay.addRow('Описание:', self.desc)
        lay.addRow('Где хранится:', self.loc)
        lay.addRow('Статус:', self.status)
        lay.addRow('Износ:', self.wear)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

    def _save(self):
        if not self.inv.text().strip() or not self.name.text().strip():
            QMessageBox.warning(self, 'Оснастка',
                                'Инв.№ и наименование обязательны.')
            return
        with self.db.get_session() as s:
            if self.item_id is None:
                it = ToolingItem(
                    inventory_no=self.inv.text().strip(),
                    name=self.name.text().strip(),
                    description=self.desc.toPlainText() or None,
                    location=self.loc.text().strip() or None,
                    status=self.status.currentData(),
                    wear_percent=self.wear.value(),
                )
                s.add(it)
            else:
                it = s.get(ToolingItem, self.item_id)
                it.inventory_no = self.inv.text().strip()
                it.name = self.name.text().strip()
                it.description = self.desc.toPlainText() or None
                it.location = self.loc.text().strip() or None
                it.status = self.status.currentData()
                it.wear_percent = self.wear.value()
            s.commit()
        self.accept()


class IssueDialog(QDialog):
    def __init__(self, db_manager, *, tooling_item_id: int,
                 current_user_id: int = 0, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.tooling_item_id = tooling_item_id
        self.user_id = current_user_id
        self.setWindowTitle('Выдача оснастки')
        self.setMinimumWidth(400)
        lay = QFormLayout(self)
        self.user_cb = QComboBox()
        self.wo_cb = QComboBox()
        self.notes = QTextEdit()
        with self.db.get_session() as s:
            for u in s.query(User).order_by(User.username).all():
                self.user_cb.addItem(u.full_name or u.username, u.id)
            self.wo_cb.addItem('— без наряда —', None)
            for wo in (s.query(WorkOrder)
                       .order_by(WorkOrder.created_at.desc()).limit(50)):
                self.wo_cb.addItem(wo.number, wo.id)
        lay.addRow('Выдать кому:', self.user_cb)
        lay.addRow('Под наряд:', self.wo_cb)
        lay.addRow('Примечание:', self.notes)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

    def _save(self):
        with self.db.get_session() as s:
            try:
                tooling.issue_to_user(
                    s,
                    tooling_item_id=self.tooling_item_id,
                    issued_to=self.user_cb.currentData(),
                    issued_by=self.user_id,
                    work_order_id=self.wo_cb.currentData(),
                    notes=self.notes.toPlainText(),
                )
                s.commit()
            except ValueError as e:
                QMessageBox.warning(self, 'Выдача', str(e))
                return
        self.accept()


class ToolingWidget(QWidget):
    """Вкладка «Оснастка»."""

    def __init__(self, db_manager, current_user_id: int = 0, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.user_id = current_user_id
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        # Tab 1 — Каталог
        self.cat_tab = QWidget()
        catlay = QVBoxLayout(self.cat_tab)
        self.cat_table = QTableWidget(0, 6)
        self.cat_table.setHorizontalHeaderLabels([
            'Инв.№', 'Наименование', 'Описание', 'Хранение', 'Статус',
            'Износ'])
        self.cat_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.cat_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cat_table.cellDoubleClicked.connect(self._cat_edit)
        self.cat_table.horizontalHeader().setStretchLastSection(True)
        catlay.addWidget(self.cat_table)
        cat_btns = QHBoxLayout()
        for label, cb in [('+ Добавить', self._cat_add),
                          ('✎ Изменить', self._cat_edit),
                          ('▶ Выдать в работу…', self._cat_issue),
                          ('⟳ Обновить', self.refresh)]:
            b = QPushButton(label)
            b.clicked.connect(cb)
            cat_btns.addWidget(b)
        cat_btns.addStretch(1)
        catlay.addLayout(cat_btns)
        tabs.addTab(self.cat_tab, 'Каталог')

        # Tab 2 — Выдачи
        self.iss_tab = QWidget()
        isslay = QVBoxLayout(self.iss_tab)
        self.iss_table = QTableWidget(0, 6)
        self.iss_table.setHorizontalHeaderLabels([
            'Оснастка', 'Кому выдано', 'Под наряд',
            'Выдано', 'Возвращено', 'Износ'])
        self.iss_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.iss_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.iss_table.horizontalHeader().setStretchLastSection(True)
        isslay.addWidget(self.iss_table)
        iss_btns = QHBoxLayout()
        for label, cb in [('↩ Принять (возврат)…', self._iss_return),
                          ('⟳ Обновить', self.refresh)]:
            b = QPushButton(label)
            b.clicked.connect(cb)
            iss_btns.addWidget(b)
        iss_btns.addStretch(1)
        isslay.addLayout(iss_btns)
        tabs.addTab(self.iss_tab, 'Выдачи')

    def refresh(self):
        with self.db.get_session() as s:
            cat = s.query(ToolingItem).order_by(
                ToolingItem.inventory_no).all()
            iss = tooling.active_issues(s)
            self._fill_cat(cat)
            self._fill_iss(iss)

    def _fill_cat(self, items):
        self.cat_table.setRowCount(len(items))
        for i, it in enumerate(items):
            def _i(text, data=None):
                qi = QTableWidgetItem(str(text))
                if data is not None:
                    qi.setData(Qt.ItemDataRole.UserRole, data)
                return qi
            self.cat_table.setItem(i, 0, _i(it.inventory_no, it.id))
            self.cat_table.setItem(i, 1, _i(it.name))
            self.cat_table.setItem(i, 2, _i((it.description or '')[:80]))
            self.cat_table.setItem(i, 3, _i(it.location or ''))
            self.cat_table.setItem(i, 4, _i(
                it.status.value if it.status else ''))
            self.cat_table.setItem(i, 5, _i(f'{it.wear_percent or 0}%'))
        self.cat_table.resizeColumnsToContents()

    def _fill_iss(self, issues):
        self.iss_table.setRowCount(len(issues))
        for i, rec in enumerate(issues):
            def _i(text, data=None):
                qi = QTableWidgetItem(str(text))
                if data is not None:
                    qi.setData(Qt.ItemDataRole.UserRole, data)
                return qi
            t = rec.tooling
            self.iss_table.setItem(i, 0, _i(
                f'{t.inventory_no}  {t.name}' if t else '—', rec.id))
            self.iss_table.setItem(i, 1, _i(
                rec.recipient.full_name or rec.recipient.username
                if rec.recipient else ''))
            self.iss_table.setItem(i, 2, _i(
                rec.work_order.number if rec.work_order else ''))
            self.iss_table.setItem(i, 3, _i(
                rec.issued_at.strftime('%d.%m.%Y %H:%M')
                if rec.issued_at else ''))
            self.iss_table.setItem(i, 4, _i('—'))
            self.iss_table.setItem(i, 5, _i(
                f'{rec.return_wear_percent}%'
                if rec.return_wear_percent is not None else ''))
        self.iss_table.resizeColumnsToContents()

    # ── Каталог: callbacks
    def _selected_cat_id(self) -> Optional[int]:
        r = self.cat_table.currentRow()
        if r < 0:
            return None
        it = self.cat_table.item(r, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _cat_add(self):
        dlg = ToolingItemDialog(self.db, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _cat_edit(self, *args):
        iid = self._selected_cat_id()
        if iid is None:
            return
        with self.db.get_session() as s:
            it = s.get(ToolingItem, iid)
        dlg = ToolingItemDialog(self.db, item=it, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _cat_issue(self):
        iid = self._selected_cat_id()
        if iid is None:
            QMessageBox.information(self, 'Оснастка',
                                    'Выберите единицу.')
            return
        dlg = IssueDialog(self.db, tooling_item_id=iid,
                          current_user_id=self.user_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    # ── Выдачи: callbacks
    def _selected_iss_id(self) -> Optional[int]:
        r = self.iss_table.currentRow()
        if r < 0:
            return None
        it = self.iss_table.item(r, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _iss_return(self):
        iid = self._selected_iss_id()
        if iid is None:
            QMessageBox.information(self, 'Возврат',
                                    'Выберите запись.')
            return
        wear, ok = QInputDialog.getInt(
            self, 'Возврат', 'Текущий износ, % (0–100):',
            value=0, min=0, max=100)
        if not ok:
            return
        with self.db.get_session() as s:
            try:
                tooling.return_from_user(
                    s, issue_id=iid, wear_percent=wear)
                s.commit()
            except ValueError as e:
                QMessageBox.warning(self, 'Возврат', str(e))
                return
        self.refresh()
