"""
Виджет единого журнала регистрации ТП/МТП.
"""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.models import RegistrationJournal
from modules import journal as journal_mod

COLS = [
    ('entry_no', '№', 50),
    ('tp_number', 'Номер ТП', 130),
    ('mtp_number', 'Номер МТП', 130),
    ('product_designation', 'Обозначение чертежа', 180),
    ('product_name', 'Наименование', 160),
    ('product_type', 'Тип изделия', 130),
    ('project', 'Проект', 150),
    ('executor', 'Исполнитель', 130),
    ('date_registered', 'Дата рег.', 90),
    ('date_developed', 'Дата ТП', 90),
    ('in_tp_journal', 'В ТП', 50),
    ('in_mtp_journal', 'В МТП', 50),
    ('excluded', 'Исключено', 80),
    ('notes', 'Примечание', 200),
]


class JournalWidget(QWidget):
    """Единый журнал регистрации ТП/МТП."""

    open_tp = pyqtSignal(int)

    def __init__(self, db_manager, user, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.user = user or {}
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── Тулбар ────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText(
            'Поиск: № ТП, обозначение, наименование, исполнитель...')
        self.search_in.textChanged.connect(self.refresh)
        toolbar.addWidget(self.search_in, 4)

        self.filter_kind = QComboBox()
        self.filter_kind.addItem('Все записи', 'all')
        self.filter_kind.addItem('Только в журнале ТП', 'tp')
        self.filter_kind.addItem('Только в журнале МТП', 'mtp')
        self.filter_kind.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(self.filter_kind)

        self.show_excluded_cb = QComboBox()
        self.show_excluded_cb.addItem('Только активные', 'active')
        self.show_excluded_cb.addItem('Все (включая исключённые)', 'all')
        self.show_excluded_cb.addItem('Только исключённые', 'excluded')
        self.show_excluded_cb.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(self.show_excluded_cb)

        toolbar.addStretch(1)

        self.add_btn = QPushButton('+ Добавить запись')
        self.add_btn.clicked.connect(self._add_entry)
        toolbar.addWidget(self.add_btn)

        self.edit_btn = QPushButton('✎ Изменить')
        self.edit_btn.clicked.connect(self._edit_entry)
        toolbar.addWidget(self.edit_btn)

        self.exclude_btn = QPushButton('✕ Исключить')
        self.exclude_btn.clicked.connect(self._exclude_entry)
        toolbar.addWidget(self.exclude_btn)

        self.restore_btn = QPushButton('↩ Восстановить')
        self.restore_btn.clicked.connect(self._restore_entry)
        toolbar.addWidget(self.restore_btn)

        import_menu_btn = QPushButton('📥 Импорт ▾')
        import_menu_btn.setMenu(self._build_import_menu())
        toolbar.addWidget(import_menu_btn)

        export_menu_btn = QPushButton('💾 Экспорт ▾')
        export_menu_btn.setMenu(self._build_export_menu())
        toolbar.addWidget(export_menu_btn)

        self.refresh_btn = QPushButton('⟳')
        self.refresh_btn.setFixedWidth(32)
        self.refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_btn)

        root.addLayout(toolbar)

        # ── Таблица ──────────────────────────────────────────
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels([c[1] for c in COLS])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        for i, (_, _, w) in enumerate(COLS):
            self.table.setColumnWidth(i, w)
        h = self.table.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        root.addWidget(self.table)

        # ── Статус ──────────────────────────────────────────
        self.status = QLabel('')
        self.status.setStyleSheet('color: #555;')
        root.addWidget(self.status)

    def _build_export_menu(self) -> QMenu:
        m = QMenu(self)
        a1 = m.addAction('Журнал ТП (форма УЗГА.02101.xxx)…')
        a1.triggered.connect(lambda: self._export('tp'))
        a2 = m.addAction('Журнал МТП (форма УЗГА.02101.xxx)…')
        a2.triggered.connect(lambda: self._export('mtp'))
        a3 = m.addAction('Объединённый журнал (все колонки)…')
        a3.triggered.connect(lambda: self._export('unified'))
        return m

    def _build_import_menu(self) -> QMenu:
        m = QMenu(self)
        a1 = m.addAction('Из xlsx (формат журнала ТП)…')
        a1.triggered.connect(lambda: self._import('tp'))
        a2 = m.addAction('Из xlsx (формат журнала МТП)…')
        a2.triggered.connect(lambda: self._import('mtp'))
        return m

    def _import(self, layout: str):
        path_str, _ = QFileDialog.getOpenFileName(
            self, 'Импорт журнала из xlsx',
            '', 'Excel (*.xlsx *.xls)')
        if not path_str:
            return
        from pathlib import Path
        try:
            with self.db.get_session() as s:
                res = journal_mod.import_from_xlsx(s, Path(path_str),
                                                   layout=layout,
                                                   skip_existing=True)
        except Exception as e:
            QMessageBox.critical(self, 'Импорт',
                                 f'Не удалось импортировать:\n{e}')
            return
        QMessageBox.information(
            self, 'Импорт',
            f'Импорт завершён.\n\n'
            f'Добавлено: {res["added"]}\n'
            f'Пропущено (уже есть): {res["skipped"]}'
        )
        self.refresh()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def refresh(self):
        kind = self.filter_kind.currentData()
        excl_mode = self.show_excluded_cb.currentData()
        search = self.search_in.text().strip() or None

        in_tp = True if kind == 'tp' else None
        in_mtp = True if kind == 'mtp' else None
        only_active = (excl_mode == 'active')

        with self.db.get_session() as s:
            entries = journal_mod.list_entries(
                s,
                only_active=only_active,
                in_tp=in_tp,
                in_mtp=in_mtp,
                search=search,
            )
            if excl_mode == 'excluded':
                entries = [e for e in entries if e.excluded]

            # snapshot rows (отвязываем от сессии)
            rows = []
            for e in entries:
                rows.append({
                    'id': e.id,
                    'entry_no': e.entry_no,
                    'tp_number': e.tp_number or '',
                    'mtp_number': e.mtp_number or '',
                    'product_designation': e.product_designation or '',
                    'product_name': e.product_name or '',
                    'product_type': e.product_type or '',
                    'project': e.project or '',
                    'executor': e.executor or '',
                    'date_registered': (
                        e.date_registered.strftime('%d.%m.%Y')
                        if e.date_registered else ''),
                    'date_developed': (
                        e.date_developed.strftime('%d.%m.%Y')
                        if e.date_developed else ''),
                    'in_tp_journal': bool(e.in_tp_journal),
                    'in_mtp_journal': bool(e.in_mtp_journal),
                    'excluded': bool(e.excluded),
                    'notes': e.notes or '',
                    'tech_process_id': e.tech_process_id,
                    'product_id': e.product_id,
                    'excluded_reason': e.excluded_reason or '',
                })

        self.table.setRowCount(0)
        for r in rows:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            for col_i, (key, _, _) in enumerate(COLS):
                v = r[key]
                if key in ('in_tp_journal', 'in_mtp_journal'):
                    text = '✓' if v else ''
                elif key == 'excluded':
                    text = 'да' if v else ''
                else:
                    text = str(v) if v is not None else ''
                item = QTableWidgetItem(text)
                if col_i == 0:
                    item.setData(Qt.ItemDataRole.UserRole, r['id'])
                if r['excluded']:
                    item.setForeground(QBrush(QColor('#888')))
                    f = item.font()
                    f.setItalic(True)
                    item.setFont(f)
                self.table.setItem(row_idx, col_i, item)

        self.status.setText(f'Записей в журнале: {len(rows)}')

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------
    def _selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _selected_ids(self):
        ids = []
        for r in self.table.selectionModel().selectedRows():
            x = self.table.item(r.row(), 0).data(Qt.ItemDataRole.UserRole)
            if x is not None:
                ids.append(int(x))
        return ids

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _add_entry(self):
        from ui.dialogs.journal_register_dialog import JournalRegisterDialog
        dlg = JournalRegisterDialog(
            self.db, 'Новая запись в журнале',
            'Заполните параметры новой записи журнала. '
            'Запись не привязывается к существующему изделию или ТП.',
            defaults={}, parent=self,
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        data = dlg.get_data()
        if data is None:
            return
        with self.db.get_session() as s:
            entry = RegistrationJournal(
                entry_no=journal_mod.next_entry_no(s),
                tp_number=data['tp_number'] or None,
                mtp_number=data['mtp_number'] or None,
                product_designation=None,
                product_name=None,
                product_type=data['product_type'] or None,
                project=data['project'] or None,
                executor=data['executor'] or None,
                notes=data['notes'] or None,
                in_tp_journal=data['in_tp'],
                in_mtp_journal=data['in_mtp'],
                excluded=data['excluded'],
                excluded_at=None,
                created_by=self.user.get('id'),
                date_registered=date.today(),
            )
            s.add(entry)
        self.refresh()

    def _edit_entry(self):
        eid = self._selected_id()
        if eid is None:
            QMessageBox.information(self, 'Журнал',
                                    'Выберите запись для редактирования.')
            return
        with self.db.get_session() as s:
            e = s.get(RegistrationJournal, eid)
            if e is None:
                return
            defaults = {
                'tp_number': e.tp_number,
                'mtp_number': e.mtp_number,
                'executor': e.executor,
                'product_type': e.product_type,
                'project': e.project,
                'notes': e.notes,
            }
        from ui.dialogs.journal_register_dialog import JournalRegisterDialog
        dlg = JournalRegisterDialog(
            self.db, 'Редактирование записи',
            'Изменить параметры записи в журнале.',
            defaults=defaults, parent=self,
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        data = dlg.get_data()
        if data is None:
            return
        with self.db.get_session() as s:
            e = s.get(RegistrationJournal, eid)
            if e is None:
                return
            e.tp_number = data['tp_number'] or None
            e.mtp_number = data['mtp_number'] or None
            e.executor = data['executor'] or None
            e.product_type = data['product_type'] or None
            e.project = data['project'] or None
            e.notes = data['notes'] or None
            e.in_tp_journal = data['in_tp']
            e.in_mtp_journal = data['in_mtp']
            if data['excluded'] and not e.excluded:
                journal_mod.exclude_entry(s, eid, self.user.get('id'),
                                          'Помечено при редактировании')
            elif not data['excluded'] and e.excluded:
                journal_mod.restore_entry(s, eid, self.user.get('id'))
        self.refresh()

    def _exclude_entry(self):
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, 'Журнал',
                                    'Выберите запись для исключения.')
            return
        reason, ok = QInputDialog.getText(
            self, 'Исключение из журнала',
            'Причина исключения (можно оставить пустой):')
        if not ok:
            return
        n = 0
        with self.db.get_session() as s:
            for eid in ids:
                if journal_mod.exclude_entry(s, eid, self.user.get('id'),
                                             reason or None):
                    n += 1
        self.refresh()
        QMessageBox.information(self, 'Журнал',
                                f'Исключено записей: {n}')

    def _restore_entry(self):
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, 'Журнал',
                                    'Выберите запись для восстановления.')
            return
        n = 0
        with self.db.get_session() as s:
            for eid in ids:
                if journal_mod.restore_entry(s, eid, self.user.get('id')):
                    n += 1
        self.refresh()
        QMessageBox.information(self, 'Журнал',
                                f'Восстановлено записей: {n}')

    def _on_double_click(self, item):
        row = item.row()
        eid_item = self.table.item(row, 0)
        if eid_item is None:
            return
        eid = eid_item.data(Qt.ItemDataRole.UserRole)
        with self.db.get_session() as s:
            e = s.get(RegistrationJournal, eid)
            if e is None:
                return
            tp_id = e.tech_process_id
        if tp_id:
            self.open_tp.emit(tp_id)

    def _export(self, layout: str):
        path_str, _ = QFileDialog.getSaveFileName(
            self, 'Экспорт журнала',
            f'Журнал_{layout}.xlsx', 'Excel (*.xlsx)')
        if not path_str:
            return
        kind = self.filter_kind.currentData()
        excl_mode = self.show_excluded_cb.currentData()
        in_tp = True if (layout == 'tp' or kind == 'tp') else None
        in_mtp = True if (layout == 'mtp' or kind == 'mtp') else None
        only_active = (excl_mode == 'active')
        with self.db.get_session() as s:
            entries = journal_mod.list_entries(
                s, only_active=only_active,
                in_tp=in_tp, in_mtp=in_mtp,
            )
            if excl_mode == 'excluded':
                entries = [e for e in entries if e.excluded]
            from pathlib import Path
            out = journal_mod.export_to_excel(s, entries, layout=layout,
                                              out_path=Path(path_str))
        QMessageBox.information(self, 'Экспорт',
                                f'Файл сохранён:\n{out}')

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        act_open = QAction('Открыть ТП', self)
        act_open.triggered.connect(lambda: self._on_double_click(self.table.itemAt(pos)))
        menu.addAction(act_open)
        menu.addSeparator()
        act_edit = QAction('Изменить...', self)
        act_edit.triggered.connect(self._edit_entry)
        menu.addAction(act_edit)
        act_excl = QAction('Исключить из журнала', self)
        act_excl.triggered.connect(self._exclude_entry)
        menu.addAction(act_excl)
        act_rest = QAction('Восстановить', self)
        act_rest.triggered.connect(self._restore_entry)
        menu.addAction(act_rest)
        menu.exec(self.table.viewport().mapToGlobal(pos))
