"""Диалог «Уведомления» (A6).

Показывает входящие уведомления текущего пользователя.
Двойной клик по уведомлению → отметить прочитанным; есть кнопка
«Пометить все прочитанными» и фильтр «Только новые».
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from modules import notifications


class NotificationsDialog(QDialog):
    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user or {}
        self.setWindowTitle('Уведомления')
        self.setMinimumSize(720, 460)
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)

        title = QLabel('Уведомления')
        f = QFont(); f.setPointSize(13); f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        bar = QHBoxLayout()
        self.only_unread = QCheckBox('Только новые')
        self.only_unread.setChecked(True)
        self.only_unread.stateChanged.connect(self.refresh)
        bar.addWidget(self.only_unread)
        bar.addStretch(1)
        self.btn_all_read = QPushButton('Пометить все прочитанными')
        self.btn_all_read.clicked.connect(self._on_all_read)
        bar.addWidget(self.btn_all_read)
        root.addLayout(bar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            'Получено', 'Тип', 'Заголовок', 'Сообщение', 'Прочитано',
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self._on_row_dblclick)
        root.addWidget(self.table)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        root.addWidget(bb)

    def refresh(self):
        self.table.setRowCount(0)
        uid = self.current_user.get('id')
        if not uid:
            return
        only_unread = self.only_unread.isChecked()
        with self.db_manager.get_session() as s:
            rows = notifications.list_notifications(
                s, user_id=uid, only_unread=only_unread, limit=300)
            data = [(n.id, n.created_at, n.kind, n.title, n.body or '',
                     n.read_at) for n in rows]
        for r in data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = [
                r[1].strftime('%Y-%m-%d %H:%M') if r[1] else '',
                r[2], r[3], r[4][:200] if r[4] else '',
                r[5].strftime('%Y-%m-%d %H:%M') if r[5] else '—',
            ]
            for col, val in enumerate(cells):
                it = QTableWidgetItem(val)
                if col == 0:
                    it.setData(Qt.ItemDataRole.UserRole, r[0])
                # Жирным — непрочитанные
                if r[5] is None:
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.table.setItem(row, col, it)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

    def _on_row_dblclick(self, row, _col):
        it = self.table.item(row, 0)
        if it is None:
            return
        nid = it.data(Qt.ItemDataRole.UserRole)
        if nid is None:
            return
        with self.db_manager.get_session() as s:
            notifications.mark_read(s, ids=[nid])
        self.refresh()

    def _on_all_read(self):
        uid = self.current_user.get('id')
        if not uid:
            return
        with self.db_manager.get_session() as s:
            notifications.mark_all_read(s, user_id=uid)
        self.refresh()
