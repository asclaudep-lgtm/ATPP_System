"""Справочник производственных участков (Workshop) с CRUD-операциями.

Позволяет администратору / технологу:
    - просматривать список участков (код / название / мастер / активен);
    - создавать новые участки;
    - редактировать существующие;
    - назначать мастера (привязка master ↔ участок);
    - помечать участок неактивным (мягкое удаление).

Удаление обычное (DELETE) запрещено: удаление участка, на котором висят
наряды или партии, ломает историю. Используется флаг ``is_active``.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from database.models import User, WorkOrderItem, Workshop

_ALLOWED_ROLES = {'admin', 'technologist'}


def _can_edit(user: dict) -> bool:
    return (user or {}).get('role') in _ALLOWED_ROLES


class WorkshopEditDialog(QDialog):
    """Карточка участка: добавить или изменить."""

    def __init__(self, db_manager, current_user, workshop_id: Optional[int] = None,
                 parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user or {}
        self.workshop_id = workshop_id
        self.saved_id: Optional[int] = None

        self.setWindowTitle('Участок' if workshop_id else 'Новый участок')
        self.setMinimumWidth(440)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.code_edit = QLineEdit()
        self.code_edit.setMaxLength(20)
        self.code_edit.setPlaceholderText('например, TURN1')
        form.addRow('Код *:', self.code_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(100)
        self.name_edit.setPlaceholderText('например, Токарный участок 1')
        form.addRow('Название *:', self.name_edit)

        self.master_combo = QComboBox()
        self.master_combo.addItem('— не назначен —', userData=None)
        form.addRow('Мастер:', self.master_combo)

        self.sort_spin = QSpinBox()
        self.sort_spin.setRange(0, 9999)
        self.sort_spin.setValue(0)
        self.sort_spin.setToolTip('Порядок отображения (меньше — выше)')
        form.addRow('Порядок:', self.sort_spin)

        self.active_chk = QCheckBox('Активен (показывается в выпадающих списках)')
        self.active_chk.setChecked(True)
        form.addRow('', self.active_chk)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(70)
        form.addRow('Примечание:', self.notes_edit)

        layout.addLayout(form)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText('Сохранить')
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _load(self):
        with self.db_manager.get_session() as s:
            # Кандидаты в мастера: роли master/admin/technologist (admin/tech
            # могут совмещать обязанности).
            users = (s.query(User)
                     .filter(User.is_active.is_(True))
                     .filter(User.role.in_(['master', 'admin', 'technologist']))
                     .order_by(User.full_name).all())
            for u in users:
                label = f'{u.full_name or u.username} [{u.role}]'
                self.master_combo.addItem(label, userData=u.id)

            if self.workshop_id is None:
                return
            ws = s.get(Workshop, self.workshop_id)
            if ws is None:
                return
            self.code_edit.setText(ws.code or '')
            self.name_edit.setText(ws.name or '')
            self.sort_spin.setValue(ws.sort_order or 0)
            self.active_chk.setChecked(bool(ws.is_active))
            self.notes_edit.setPlainText(ws.notes or '')
            for i in range(self.master_combo.count()):
                if self.master_combo.itemData(i) == ws.master_user_id:
                    self.master_combo.setCurrentIndex(i)
                    break

    def _on_ok(self):
        code = self.code_edit.text().strip().upper()
        name = self.name_edit.text().strip()
        if not code:
            QMessageBox.warning(self, 'Сохранение', 'Укажите код участка.')
            return
        if not name:
            QMessageBox.warning(self, 'Сохранение', 'Укажите название.')
            return
        if len(code) > 20:
            QMessageBox.warning(self, 'Сохранение',
                                'Код участка должен быть не длиннее 20 символов.')
            return

        try:
            with self.db_manager.get_session() as s:
                if self.workshop_id is None:
                    # Уникальность кода
                    existing = (s.query(Workshop)
                                .filter(Workshop.code == code).first())
                    if existing:
                        QMessageBox.warning(
                            self, 'Сохранение',
                            f'Участок с кодом «{code}» уже существует.')
                        return
                    ws = Workshop(
                        code=code, name=name,
                        master_user_id=self.master_combo.currentData(),
                        sort_order=self.sort_spin.value(),
                        is_active=self.active_chk.isChecked(),
                        notes=self.notes_edit.toPlainText().strip() or None,
                    )
                    s.add(ws)
                    s.flush()
                    self.saved_id = ws.id
                else:
                    ws = s.get(Workshop, self.workshop_id)
                    if ws is None:
                        QMessageBox.warning(self, 'Сохранение',
                                            'Участок не найден.')
                        return
                    if ws.code != code:
                        clash = (s.query(Workshop)
                                 .filter(Workshop.code == code,
                                         Workshop.id != ws.id).first())
                        if clash:
                            QMessageBox.warning(
                                self, 'Сохранение',
                                f'Код «{code}» уже используется участком '
                                f'«{clash.name}».')
                            return
                    ws.code = code
                    ws.name = name
                    ws.master_user_id = self.master_combo.currentData()
                    ws.sort_order = self.sort_spin.value()
                    ws.is_active = self.active_chk.isChecked()
                    ws.notes = self.notes_edit.toPlainText().strip() or None
                    self.saved_id = ws.id
        except Exception as e:
            QMessageBox.critical(self, 'Сохранение', f'Не удалось сохранить:\n{e}')
            return
        self.accept()


class WorkshopsDialog(QDialog):
    """Список участков с кнопками «Добавить / Изменить / Деактивировать»."""

    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user or {}
        self.setWindowTitle('Справочник участков')
        self.setMinimumSize(800, 480)
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)

        title = QLabel('Производственные участки')
        f = QFont(); f.setPointSize(13); f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        info = QLabel(
            'Здесь редактируются участки (цеха), которые используются в '
            'модуле «Производство». Для каждого участка можно назначить '
            'мастера. Удалить участок нельзя — его можно деактивировать.')
        info.setWordWrap(True)
        info.setStyleSheet('color: gray;')
        root.addWidget(info)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            'Код', 'Название', 'Мастер', 'Порядок', 'Активен', 'Партий сейчас',
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(lambda *_: self._on_edit())
        root.addWidget(self.table)

        bar = QHBoxLayout()
        self.btn_add = QPushButton('Добавить…')
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit = QPushButton('Изменить…')
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_toggle = QPushButton('Деактивировать / Активировать')
        self.btn_toggle.clicked.connect(self._on_toggle_active)
        for btn in (self.btn_add, self.btn_edit, self.btn_toggle):
            btn.setMinimumWidth(170)
            bar.addWidget(btn)

        if not _can_edit(self.current_user):
            for btn in (self.btn_add, self.btn_edit, self.btn_toggle):
                btn.setEnabled(False)
                btn.setToolTip('Доступно ролям: admin, technologist')

        bar.addStretch(1)
        btn_close = QPushButton('Закрыть')
        btn_close.clicked.connect(self.accept)
        bar.addWidget(btn_close)
        root.addLayout(bar)

    def refresh(self):
        self.table.setRowCount(0)
        with self.db_manager.get_session() as s:
            workshops = (s.query(Workshop)
                         .order_by(Workshop.sort_order, Workshop.id).all())
            rows = []
            for ws in workshops:
                count = (s.query(WorkOrderItem)
                         .filter(WorkOrderItem.current_workshop_id == ws.id)
                         .count())
                master_label = '—'
                if ws.master:
                    master_label = ws.master.full_name or ws.master.username
                rows.append({
                    'id': ws.id,
                    'code': ws.code,
                    'name': ws.name,
                    'master': master_label,
                    'sort_order': ws.sort_order,
                    'is_active': bool(ws.is_active),
                    'count': count,
                })

        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = [
                r['code'], r['name'], r['master'],
                str(r['sort_order']),
                'да' if r['is_active'] else 'нет',
                str(r['count']),
            ]
            for col, val in enumerate(cells):
                it = QTableWidgetItem(val)
                if col == 0:
                    it.setData(Qt.ItemDataRole.UserRole, r['id'])
                if not r['is_active']:
                    it.setForeground(Qt.GlobalColor.gray)
                self.table.setItem(row, col, it)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(False)

    def _selected_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        it = self.table.item(row, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _on_add(self):
        if not _can_edit(self.current_user):
            return
        dlg = WorkshopEditDialog(self.db_manager, self.current_user, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_edit(self):
        if not _can_edit(self.current_user):
            return
        ws_id = self._selected_id()
        if not ws_id:
            QMessageBox.information(self, 'Изменение',
                                    'Выберите участок в таблице.')
            return
        dlg = WorkshopEditDialog(self.db_manager, self.current_user,
                                 workshop_id=ws_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_toggle_active(self):
        if not _can_edit(self.current_user):
            return
        ws_id = self._selected_id()
        if not ws_id:
            QMessageBox.information(self, 'Активировать / деактивировать',
                                    'Выберите участок в таблице.')
            return
        with self.db_manager.get_session() as s:
            ws = s.get(Workshop, ws_id)
            if ws is None:
                return
            count = (s.query(WorkOrderItem)
                     .filter(WorkOrderItem.current_workshop_id == ws.id)
                     .count())
            if ws.is_active and count > 0:
                ans = QMessageBox.question(
                    self, 'Деактивировать?',
                    f'На участке «{ws.name}» сейчас {count} партий.\n'
                    f'Деактивация только скроет участок в выпадающих списках, '
                    f'история сохранится.\n\nПродолжить?')
                if ans != QMessageBox.StandardButton.Yes:
                    return
            ws.is_active = not bool(ws.is_active)
        self.refresh()
