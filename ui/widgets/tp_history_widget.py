"""
v9-7 UI: История версий ТП — список снимков и diff между ними.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules import audit
from modules.tp_versioning import (
    diff_human,
    diff_snapshots,
    list_versions,
    load_snapshot,
)

_logger = logging.getLogger(__name__)


class TPHistoryWidget(QWidget):
    """История версий конкретного ТП."""

    def __init__(self, db_manager, tech_process_id: int,
                 *, current_user_id: int = 0, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.tp_id = tech_process_id
        self.user_id = current_user_id
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        head = QLabel('История версий ТП')
        f = head.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 2)
        head.setFont(f)
        top.addWidget(head)
        top.addStretch(1)
        b_snap = QPushButton('📸 Сделать снимок')
        b_snap.clicked.connect(self._on_snapshot)
        b_diff = QPushButton('🔀 Сравнить выделенные')
        b_diff.clicked.connect(self._on_diff)
        b_refresh = QPushButton('⟳ Обновить')
        b_refresh.clicked.connect(self.refresh)
        for b in (b_snap, b_diff, b_refresh):
            top.addWidget(b)
        root.addLayout(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split, 1)

        # Левый: список версий (можно выбрать 2 для сравнения)
        self.list = QListWidget()
        self.list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection)
        split.addWidget(self.list)

        # Правый: таблица diff
        self.diff_table = QTableWidget(0, 1)
        self.diff_table.setHorizontalHeaderLabels(['Изменение'])
        self.diff_table.horizontalHeader().setStretchLastSection(True)
        self.diff_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        split.addWidget(self.diff_table)
        split.setSizes([320, 700])

    def refresh(self):
        self.list.clear()
        with self.db.get_session() as s:
            versions = list_versions(s, self.tp_id)
            for v in versions:
                txt = (f'v{v.version_number}   '
                       f'{v.created_at.strftime("%d.%m.%Y %H:%M") if v.created_at else ""}   '
                       f'— {(v.comment or "").splitlines()[0] if v.comment else ""}')
                it = QListWidgetItem(txt)
                it.setData(Qt.ItemDataRole.UserRole, v.id)
                self.list.addItem(it)

    def _on_snapshot(self):
        comment, ok = QInputDialog.getText(
            self, 'Снимок', 'Комментарий к снимку:')
        if not ok:
            return
        vid = audit.snapshot_tp(self.db, tp_id=self.tp_id,
                                user_id=self.user_id,
                                comment=comment)
        if vid is None:
            QMessageBox.warning(self, 'Снимок',
                                'Не удалось создать снимок.')
            return
        self.refresh()

    def _on_diff(self):
        sel = self.list.selectedItems()
        if len(sel) != 2:
            QMessageBox.information(
                self, 'Сравнение',
                'Выделите ровно 2 версии (Ctrl+клик).')
            return
        from database.models import TPVersion
        ids = [s.data(Qt.ItemDataRole.UserRole) for s in sel]
        with self.db.get_session() as s:
            a = s.get(TPVersion, ids[0])
            b = s.get(TPVersion, ids[1])
            sa = load_snapshot(a) or {}
            sb = load_snapshot(b) or {}
        # Чтобы было воспроизводимо: меньшая версия — слева.
        try:
            if int(a.version_number) > int(b.version_number):
                sa, sb = sb, sa
        except Exception:
            _logger.exception("Unhandled error")
        d = diff_snapshots(sa, sb)
        self.diff_table.setRowCount(len(d) if d else 1)
        if not d:
            self.diff_table.setItem(0, 0, QTableWidgetItem(
                'Изменений нет — версии идентичны.'))
            return
        for i, item in enumerate(d):
            txt = diff_human(item)
            qi = QTableWidgetItem(txt)
            kind = item.get('kind') or ''
            if 'added' in kind:
                qi.setBackground(QBrush(QColor(220, 255, 220)))
            elif 'removed' in kind:
                qi.setBackground(QBrush(QColor(255, 220, 220)))
            elif 'tp_field' in kind or 'op_field' in kind:
                qi.setBackground(QBrush(QColor(255, 255, 200)))
            self.diff_table.setItem(i, 0, qi)
