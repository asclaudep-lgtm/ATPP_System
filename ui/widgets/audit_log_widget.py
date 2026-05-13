"""
Виджет «Журнал изменений» — показывает последние записи ChangeLog.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)

from modules.audit import list_audit


class AuditLogWidget(QWidget):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._all_rows: list[dict] = []
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        title = QLabel('Журнал изменений (audit log)')
        title.setStyleSheet('font-weight: bold; font-size: 14px;')
        lay.addWidget(title)

        flt = QHBoxLayout()
        flt.addWidget(QLabel('Тип объекта:'))
        self._cb_entity = QComboBox()
        self._cb_entity.addItems(
            ['Все', 'TechProcess', 'Operation', 'Transition', 'Sketch', 'Product']
        )
        self._cb_entity.currentIndexChanged.connect(self._apply)
        flt.addWidget(self._cb_entity)

        flt.addSpacing(20)
        flt.addWidget(QLabel('Действие:'))
        self._cb_action = QComboBox()
        self._cb_action.addItems(
            ['Все', 'create', 'update', 'delete', 'approve', 'archive']
        )
        self._cb_action.currentIndexChanged.connect(self._apply)
        flt.addWidget(self._cb_action)

        flt.addSpacing(20)
        flt.addWidget(QLabel('Поиск:'))
        self._ed = QLineEdit()
        self._ed.setPlaceholderText('по описанию или пользователю…')
        self._ed.textChanged.connect(self._apply)
        flt.addWidget(self._ed, 1)

        rb = QPushButton('⟳ Обновить')
        rb.clicked.connect(self.refresh)
        flt.addWidget(rb)
        lay.addLayout(flt)

        self._tbl = QTableWidget()
        self._tbl.setColumnCount(6)
        self._tbl.setHorizontalHeaderLabels([
            'Когда', 'Пользователь', 'Действие', 'Объект', 'ID', 'Описание'
        ])
        self._tbl.setColumnWidth(0, 140)
        self._tbl.setColumnWidth(1, 140)
        self._tbl.setColumnWidth(2, 90)
        self._tbl.setColumnWidth(3, 110)
        self._tbl.setColumnWidth(4, 60)
        self._tbl.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.Stretch
        )
        self._tbl.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.verticalHeader().setVisible(False)
        lay.addWidget(self._tbl, 1)

        self._summary = QLabel('')
        self._summary.setStyleSheet('color:#555;')
        lay.addWidget(self._summary)

    def refresh(self):
        ent = self._cb_entity.currentText()
        act = self._cb_action.currentText()
        rows = list_audit(
            self.db_manager,
            limit=2000,
            entity_type=None if ent == 'Все' else ent,
            action=None if act == 'Все' else act,
        )
        self._all_rows = rows
        self._apply()

    def _apply(self):
        rows = self._all_rows
        ent = self._cb_entity.currentText()
        act = self._cb_action.currentText()
        if ent != 'Все':
            rows = [r for r in rows if r['entity_type'] == ent]
        if act != 'Все':
            rows = [r for r in rows if r['action'] == act]
        text = (self._ed.text() or '').strip().lower()
        if text:
            rows = [r for r in rows if text in (
                (r.get('description') or '') + ' ' + (r.get('user_name') or '')
            ).lower()]

        self._tbl.setRowCount(0)
        for r in rows:
            row = self._tbl.rowCount()
            self._tbl.insertRow(row)
            ts = r['timestamp'].strftime('%d.%m.%Y %H:%M:%S') if r['timestamp'] else ''
            cells = [
                ts, r.get('user_name') or '—', r.get('action') or '',
                r.get('entity_type') or '', str(r.get('entity_id') or ''),
                r.get('description') or '',
            ]
            for c, v in enumerate(cells):
                self._tbl.setItem(row, c, QTableWidgetItem(v))
        self._summary.setText(f'Записей в выборке: {len(rows)}')
