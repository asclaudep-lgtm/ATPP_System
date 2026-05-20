"""
Главный редактор технологического процесса
"""
from utils.logger import get_logger

_log = get_logger(__name__)

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileIconProvider,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.models import Operation, TechProcess, TPStatus, Transition

STATUS_COLORS = {
    TPStatus.DRAFT:     ('#f39c12', 'Черновик'),
    TPStatus.REVIEW:    ('#8e44ad', 'На согласовании'),
    TPStatus.REWORK:    ('#e74c3c', 'На доработке'),
    TPStatus.APPROVED:  ('#27ae60', 'Утверждён'),
    TPStatus.ARCHIVED:  ('#95a5a6', 'Архив'),
}


class TPEditorWidget(QWidget):
    """Полный редактор технологического процесса"""

    tp_changed = pyqtSignal(int)  # tp_id

    def __init__(self, db_manager, tp_id, user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.tp_id = tp_id
        self.user = user

        self._load_tp_data()
        self._init_ui()
        self._load_operations()

    # ──────────────────────────────────────────────────────────────
    # Аудит
    # ──────────────────────────────────────────────────────────────
    def _log_audit(self, action: str, entity_type: str,
                   entity_id: int | None, description: str = ''):
        try:
            from modules.audit import log_change
            log_change(
                self.db_manager,
                user_id=(self.user or {}).get('id'),
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                description=description,
            )
        except Exception as e:
            _log.debug('Non-critical operation skipped: %s', e)

    # ──────────────────────────────────────────────────────────────
    # Загрузка данных
    # ──────────────────────────────────────────────────────────────
    def _load_tp_data(self):
        session = self.db_manager.Session()
        try:
            tp = session.get(TechProcess, self.tp_id)
            if not tp:
                self._tp = {}
                return
            prod = tp.product
            self._tp = {
                'id': tp.id,
                'number': tp.number,
                'version': tp.version,
                'execution_variant': getattr(tp, 'execution_variant', None),
                'status': tp.status,
                'tp_type': tp.tp_type,
                'technology_type': tp.technology_type,
                'description': tp.description,
                'author_id': tp.author_id,
                'product_id': tp.product_id,
                'product_designation': prod.designation if prod else '',
                'product_name': prod.name if prod else '',
                'product_material': (prod.material.name + ' ' + (prod.material.grade or '')).strip()
                    if prod and prod.material else '',
                'product_mass': prod.mass if prod else None,
            }
        finally:
            session.close()

    def _load_operations(self):
        session = self.db_manager.Session()
        try:
            ops = (session.query(Operation)
                   .filter(Operation.tech_process_id == self.tp_id,
                           (not Operation.is_deleted) | (Operation.is_deleted.is_(None)))
                   .order_by(Operation.sort_order)
                   .all())
            self._operations = []
            for op in ops:
                eq_name = op.equipment.name if op.equipment else ''
                pr_name = op.profession.name if op.profession else ''
                sketches = getattr(op, 'sketches', None) or []
                self._operations.append({
                    'id': op.id,
                    'number': op.number,
                    'name': op.name,
                    'code': op.code,
                    'shop': op.shop,
                    'equipment_id': op.equipment_id,
                    'equipment_name': eq_name,
                    'profession_id': op.profession_id,
                    'profession_name': pr_name,
                    'grade': op.grade,
                    't_piece': op.t_piece,
                    't_setup': op.t_setup,
                    't_main': op.t_main,
                    't_auxiliary': op.t_auxiliary,
                    'machine_count': op.machine_count,
                    'note': op.note,
                    'sort_order': op.sort_order,
                    'include_in_mtp': bool(getattr(op, 'include_in_mtp', True)),
                    'sketch_count': len(sketches),
                })
        finally:
            session.close()
        self._fill_operations_table()

    def _load_transitions(self, op_id):
        session = self.db_manager.Session()
        try:
            trans = (session.query(Transition)
                     .filter_by(operation_id=op_id)
                     .order_by(Transition.sort_order)
                     .all())
            self._transitions = []
            for t in trans:
                sketches = getattr(t, 'sketches', None) or []
                self._transitions.append({
                    'id': t.id,
                    'number': t.number,
                    'text': t.text,
                    'code': t.code,
                    'diameter': t.diameter,
                    'length': t.length,
                    'depth': t.depth,
                    'feed': t.feed,
                    'speed': t.speed,
                    'rpm': t.rpm,
                    'passes': t.passes,
                    'sort_order': t.sort_order,
                    'sketch_count': len(sketches),
                })
        finally:
            session.close()
        self._fill_transitions_table()

    # ──────────────────────────────────────────────────────────────
    # UI
    # ──────────────────────────────────────────────────────────────
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Шапка
        layout.addWidget(self._make_header())

        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #bdc3c7; max-height: 1px;")
        layout.addWidget(line)

        # Вкладки
        self._tabs = QTabWidget()
        self._tabs.addTab(self._make_operations_tab(), "Операции и переходы")
        self._tabs.addTab(self._make_material_norms_tab(), "Материальное нормирование")
        self._tabs.addTab(self._make_cost_calc_tab(), "Расчёт себестоимости")
        self._tabs.addTab(self._make_documents_tab(), "Документы")
        layout.addWidget(self._tabs)

    def _make_header(self):
        frame = QFrame()
        frame.setStyleSheet("background-color: #ecf0f1; padding: 6px;")
        layout = QHBoxLayout(frame)
        layout.setSpacing(20)

        # Обозначение + наименование
        left = QVBoxLayout()
        prod_label = QLabel(
            f"<b>{self._tp.get('product_designation', '')}</b>  "
            f"{self._tp.get('product_name', '')}"
        )
        prod_label.setStyleSheet("font-size: 14px;")
        left.addWidget(prod_label)

        variant = self._tp.get('execution_variant')
        variant_part = f"  |  Исп.: {variant}" if variant else ""
        tp_info = QLabel(
            f"ТП: {self._tp.get('number', '')}  |  "
            f"Версия: {self._tp.get('version', '1.0')}{variant_part}  |  "
            f"Материал: {self._tp.get('product_material', '—')}"
        )
        tp_info.setStyleSheet("color: #555; font-size: 12px;")
        left.addWidget(tp_info)
        layout.addLayout(left)

        layout.addStretch()

        # Статус (цветной)
        status = self._tp.get('status')
        if status in STATUS_COLORS:
            color, label = STATUS_COLORS[status]
            status_lbl = QLabel(f"  {label}  ")
            status_lbl.setStyleSheet(
                f"background-color: {color}; color: white; "
                f"border-radius: 4px; padding: 3px 8px; font-weight: bold;"
            )
            layout.addWidget(status_lbl)
            self._status_lbl = status_lbl

        # Кнопки смены статуса
        self._status_btn_layout = QHBoxLayout()
        self._update_status_buttons()
        layout.addLayout(self._status_btn_layout)

        return frame

    def _update_status_buttons(self):
        # Очищаем кнопки
        while self._status_btn_layout.count():
            item = self._status_btn_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        status = self._tp.get('status')
        role = self.user.get('role', 'user')

        # Кнопка «Подписи…» — всегда доступна
        sigs_btn = QPushButton('🖋 Подписи…')
        sigs_btn.setStyleSheet(
            "QPushButton { background-color: #3498db; color: white; "
            "border: none; padding: 4px 10px; border-radius: 3px; }"
        )
        sigs_btn.clicked.connect(self._show_signatures)
        self._status_btn_layout.addWidget(sigs_btn)

        transitions = []
        if status == TPStatus.DRAFT:
            transitions.append(('На согласование', TPStatus.REVIEW, '#8e44ad'))
        if status == TPStatus.REVIEW and role in ('admin', 'technologist'):
            # «Утвердить» теперь идёт через диалог подписей
            transitions.append(('На доработку', TPStatus.REWORK, '#e74c3c'))
        if status == TPStatus.REWORK:
            transitions.append(('Переотправить', TPStatus.REVIEW, '#8e44ad'))
        if status == TPStatus.APPROVED and role == 'admin':
            transitions.append(('В архив', TPStatus.ARCHIVED, '#95a5a6'))

        for label, new_status, color in transitions:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color}; color: white; "
                f"border: none; padding: 4px 10px; border-radius: 3px; }}"
                f"QPushButton:hover {{ opacity: 0.8; }}"
            )
            btn.clicked.connect(lambda checked, s=new_status: self._change_status(s))
            self._status_btn_layout.addWidget(btn)

    def _change_status(self, new_status):
        with self.db_manager.get_session() as session:
            tp = session.get(TechProcess, self.tp_id)
            if tp:
                tp.status = new_status
        self._tp['status'] = new_status
        color, label = STATUS_COLORS[new_status]
        self._status_lbl.setText(f"  {label}  ")
        self._status_lbl.setStyleSheet(
            f"background-color: {color}; color: white; "
            f"border-radius: 4px; padding: 3px 8px; font-weight: bold;"
        )
        self._update_status_buttons()
        self.tp_changed.emit(self.tp_id)

    # ──────────────────────────────────────────────────────────────
    # Вкладка «Операции и переходы»
    # ──────────────────────────────────────────────────────────────
    def _make_operations_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Операции ──
        op_widget = QWidget()
        op_layout = QVBoxLayout(op_widget)
        op_layout.setContentsMargins(0, 0, 0, 0)

        op_header = QHBoxLayout()
        op_title = QLabel("Операции")
        op_title_font = QFont()
        op_title_font.setBold(True)
        op_title.setFont(op_title_font)
        op_header.addWidget(op_title)
        op_header.addStretch()

        for text, slot, color in [
            ("+ Добавить", self._add_operation, '#27ae60'),
            ("Импорт из ТП…", self._copy_op_from_other_tp, '#16a085'),
            ("Редактировать", self._edit_operation, '#2980b9'),
            ("⚙ Массовое изменение", self._bulk_edit_operations, '#1abc9c'),
            ("Удалить", self._delete_operation, '#e74c3c'),
            ("↑", self._move_op_up, '#7f8c8d'),
            ("↓", self._move_op_down, '#7f8c8d'),
            ("Авторасчёт времени", self._auto_calc_time, '#8e44ad'),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            btn.setFixedHeight(26)
            if color:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {color}; color: white; "
                    f"border: none; padding: 2px 8px; border-radius: 3px; }}"
                )
            op_header.addWidget(btn)

        op_layout.addLayout(op_header)

        self._time_summary_lbl = QLabel("")
        self._time_summary_lbl.setStyleSheet("color: #555; font-size: 11px; padding: 2px 4px;")
        op_layout.addWidget(self._time_summary_lbl)

        self.op_table = QTableWidget()
        self.op_table.setColumnCount(10)
        self.op_table.setHorizontalHeaderLabels([
            "ID", "№ оп.", "Наименование операции",
            "Оборудование", "Профессия / Разряд",
            "Тшт, мин", "Тпз, мин", "Цех", "МТП", "📎"
        ])
        self.op_table.setColumnHidden(0, True)
        self.op_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.op_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.op_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.op_table.setColumnWidth(1, 60)
        self.op_table.setColumnWidth(3, 180)
        self.op_table.setColumnWidth(4, 160)
        self.op_table.setColumnWidth(5, 80)
        self.op_table.setColumnWidth(6, 80)
        self.op_table.setColumnWidth(7, 100)
        self.op_table.setColumnWidth(8, 50)
        self.op_table.setColumnWidth(9, 40)
        self.op_table.horizontalHeaderItem(9).setToolTip("Кол-во прикреплённых эскизов")
        self.op_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.op_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.op_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.op_table.setAlternatingRowColors(True)
        self.op_table.verticalHeader().setVisible(False)
        self.op_table.selectionModel().selectionChanged.connect(self._on_operation_selected)
        self.op_table.doubleClicked.connect(self._edit_operation)
        op_layout.addWidget(self.op_table)

        splitter.addWidget(op_widget)

        # ── Переходы ──
        tr_widget = QWidget()
        tr_layout = QVBoxLayout(tr_widget)
        tr_layout.setContentsMargins(0, 0, 0, 0)

        tr_header = QHBoxLayout()
        self.tr_title = QLabel("Переходы")
        self.tr_title.setFont(op_title_font)
        tr_header.addWidget(self.tr_title)
        tr_header.addStretch()

        for text, slot, color in [
            ("+ Добавить", self._add_transition, '#27ae60'),
            ("Редактировать", self._edit_transition, '#2980b9'),
            ("Удалить", self._delete_transition, '#e74c3c'),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            btn.setFixedHeight(26)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color}; color: white; "
                f"border: none; padding: 2px 8px; border-radius: 3px; }}"
            )
            tr_header.addWidget(btn)

        tr_layout.addLayout(tr_header)

        self.tr_table = QTableWidget()
        self.tr_table.setColumnCount(10)
        self.tr_table.setHorizontalHeaderLabels([
            "ID", "№", "Текст перехода",
            "D, мм", "L, мм", "t, мм", "S, мм/об", "n, об/мин", "i", "📎"
        ])
        self.tr_table.setColumnHidden(0, True)
        self.tr_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tr_table.setColumnWidth(1, 40)
        self.tr_table.setColumnWidth(3, 65)
        self.tr_table.setColumnWidth(4, 65)
        self.tr_table.setColumnWidth(5, 65)
        self.tr_table.setColumnWidth(6, 75)
        self.tr_table.setColumnWidth(7, 85)
        self.tr_table.setColumnWidth(8, 35)
        self.tr_table.setColumnWidth(9, 40)
        self.tr_table.horizontalHeaderItem(9).setToolTip("Кол-во прикреплённых эскизов")
        self.tr_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tr_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tr_table.setAlternatingRowColors(True)
        self.tr_table.verticalHeader().setVisible(False)
        self.tr_table.doubleClicked.connect(self._edit_transition)
        tr_layout.addWidget(self.tr_table)

        splitter.addWidget(tr_widget)
        splitter.setSizes([350, 200])

        layout.addWidget(splitter)
        return w

    # ──────────────────────────────────────────────────────────────
    # Заполнение таблиц
    # ──────────────────────────────────────────────────────────────
    def _fill_operations_table(self):
        self.op_table.setRowCount(0)
        for op in self._operations:
            row = self.op_table.rowCount()
            self.op_table.insertRow(row)

            self.op_table.setItem(row, 0, QTableWidgetItem(str(op['id'])))
            self.op_table.setItem(row, 1, QTableWidgetItem(op['number'] or ''))
            self.op_table.setItem(row, 2, QTableWidgetItem(op['name'] or ''))
            self.op_table.setItem(row, 3, QTableWidgetItem(op['equipment_name'] or ''))

            prof_text = op['profession_name'] or ''
            if op.get('grade'):
                prof_text += f"  р.{op['grade']}"
            self.op_table.setItem(row, 4, QTableWidgetItem(prof_text))

            t_piece = op.get('t_piece') or 0
            self.op_table.setItem(row, 5, QTableWidgetItem(f"{t_piece:.2f}" if t_piece else ''))
            t_setup = op.get('t_setup') or 0
            self.op_table.setItem(row, 6, QTableWidgetItem(f"{t_setup:.2f}" if t_setup else ''))
            self.op_table.setItem(row, 7, QTableWidgetItem(op.get('shop') or ''))

            include = bool(op.get('include_in_mtp', True))
            mtp_item = QTableWidgetItem('✓' if include else '✗')
            mtp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            mtp_item.setToolTip(
                "Операция выводится в МК и МСК"
                if include else
                "Операция НЕ выводится в МК / МСК\n"
                "(остаётся в составе ТП и в расчётах)"
            )
            mtp_item.setForeground(QColor('#27ae60' if include else '#c0392b'))
            self.op_table.setItem(row, 8, mtp_item)

            sketch_count = int(op.get('sketch_count') or 0)
            sketch_item = QTableWidgetItem(
                f"📎 {sketch_count}" if sketch_count else ''
            )
            sketch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if sketch_count:
                sketch_item.setToolTip(
                    f"Прикреплено эскизов: {sketch_count}\n"
                    "Открыть редактор операции, чтобы увидеть."
                )
                sketch_item.setForeground(QColor('#2980b9'))
            self.op_table.setItem(row, 9, sketch_item)

            # Серый курсив для исключённых из МТП строк
            if not include:
                gray = QColor('#7f8c8d')
                row_font = QFont()
                row_font.setItalic(True)
                row_tip = "Операция исключена из выдачи в МТП"
                for c in range(1, self.op_table.columnCount()):
                    item = self.op_table.item(row, c)
                    if item is None:
                        continue
                    item.setForeground(gray)
                    item.setFont(row_font)
                    if c != 8:
                        item.setToolTip(row_tip)

        # Суммарное время
        if self._operations:
            total_piece = sum(op.get('t_piece') or 0 for op in self._operations)
            total_setup = sum(op.get('t_setup') or 0 for op in self._operations)
            if hasattr(self, '_time_summary_lbl'):
                self._time_summary_lbl.setText(
                    f"Итого:  Тшт = {total_piece:.2f} мин  |  Тпз = {total_setup:.2f} мин"
                )

    def _fill_transitions_table(self):
        self.tr_table.setRowCount(0)
        for tr in self._transitions:
            row = self.tr_table.rowCount()
            self.tr_table.insertRow(row)

            def fmt(v):
                if v is None or v == 0:
                    return ''
                return f"{v:.2f}" if isinstance(v, float) else str(v)

            self.tr_table.setItem(row, 0, QTableWidgetItem(str(tr['id'])))
            self.tr_table.setItem(row, 1, QTableWidgetItem(str(tr['number'] or '')))
            self.tr_table.setItem(row, 2, QTableWidgetItem(tr['text'] or ''))
            self.tr_table.setItem(row, 3, QTableWidgetItem(fmt(tr.get('diameter'))))
            self.tr_table.setItem(row, 4, QTableWidgetItem(fmt(tr.get('length'))))
            self.tr_table.setItem(row, 5, QTableWidgetItem(fmt(tr.get('depth'))))
            self.tr_table.setItem(row, 6, QTableWidgetItem(fmt(tr.get('feed'))))
            self.tr_table.setItem(row, 7, QTableWidgetItem(fmt(tr.get('rpm'))))
            self.tr_table.setItem(row, 8, QTableWidgetItem(str(tr.get('passes') or 1)))

            sk_count = int(tr.get('sketch_count') or 0)
            sk_item = QTableWidgetItem(f"📎 {sk_count}" if sk_count else '')
            sk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if sk_count:
                sk_item.setForeground(QColor('#2980b9'))
                sk_item.setToolTip(f"Прикреплено эскизов: {sk_count}")
            self.tr_table.setItem(row, 9, sk_item)

    # ──────────────────────────────────────────────────────────────
    # Обработчики операций
    # ──────────────────────────────────────────────────────────────
    def _on_operation_selected(self):
        row = self.op_table.currentRow()
        if row < 0:
            self._transitions = []
            self._fill_transitions_table()
            self.tr_title.setText("Переходы")
            return
        op_id = int(self.op_table.item(row, 0).text())
        op_name = self.op_table.item(row, 2).text()
        op_num = self.op_table.item(row, 1).text()
        self.tr_title.setText(f"Переходы операции {op_num} — {op_name}")
        self._load_transitions(op_id)
        self._current_op_id = op_id

    def _get_current_op_id(self):
        row = self.op_table.currentRow()
        if row < 0:
            return None
        return int(self.op_table.item(row, 0).text())

    def _selected_op_ids(self) -> list:
        ids = []
        for idx in self.op_table.selectionModel().selectedRows():
            try:
                ids.append(int(self.op_table.item(idx.row(), 0).text()))
            except Exception as e:
                _log.debug('Item skipped: %s', e)
                continue
        if not ids:
            cur = self.op_table.currentRow()
            if cur >= 0:
                try:
                    ids.append(int(self.op_table.item(cur, 0).text()))
                except Exception as e:
                    _log.debug('Non-critical op skipped: %s', e)
        return ids

    def _bulk_edit_operations(self):
        if not self._check_lock_or_warn():
            return
        ids = self._selected_op_ids()
        if not ids:
            QMessageBox.information(
                self, 'Массовое изменение',
                'Выделите одну или несколько операций (Shift / Ctrl-клик).'
            )
            return
        from ui.dialogs.bulk_edit_ops_dialog import BulkEditOpsDialog
        dlg = BulkEditOpsDialog(self.db_manager, ids, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._load_operations()
            self.tp_changed.emit(self.tp_id)

    def _is_locked(self) -> bool:
        """ТП заблокирован для редактирования (Утверждён или Архив)."""
        from database.models import LOCKED_STATUSES
        return self._tp.get('status') in LOCKED_STATUSES

    def _check_lock_or_warn(self) -> bool:
        """Если ТП заблокирован — показать предупреждение и вернуть False."""
        if not self._is_locked():
            return True
        QMessageBox.warning(
            self, 'ТП заблокирован',
            'Этот ТП утверждён / в архиве и заблокирован для редактирования.\n\n'
            'Чтобы внести изменения — откройте «Подписи…» и выполните\n'
            '«Снять с утверждения» с указанием причины.'
        )
        return False

    def _show_signatures(self):
        from ui.dialogs.signatures_dialog import SignaturesDialog
        dlg = SignaturesDialog(self.db_manager, self.tp_id,
                               current_user=self.user, parent=self)
        dlg.exec()
        # Возможно статус изменился — обновим заголовок и статус-кнопки
        with self.db_manager.get_session() as s:
            tp = s.get(TechProcess, self.tp_id)
            if tp is not None:
                self._tp['status'] = tp.status
        if hasattr(self, '_status_lbl') and self._tp.get('status') in STATUS_COLORS:
            color, label = STATUS_COLORS[self._tp['status']]
            self._status_lbl.setText(f"  {label}  ")
            self._status_lbl.setStyleSheet(
                f"background-color: {color}; color: white; "
                f"border-radius: 4px; padding: 3px 8px; font-weight: bold;"
            )
        self._update_status_buttons()
        self.tp_changed.emit(self.tp_id)

    def _add_operation(self):
        if not self._check_lock_or_warn():
            return
        from ui.dialogs.operation_dialog import OperationDialog
        next_num = self._next_op_number()
        dlg = OperationDialog(
            self.db_manager,
            next_number=next_num,
            product_designation=self._tp.get('product_designation', ''),
            parent=self,
        )
        if dlg.exec() == dlg.DialogCode.Accepted:
            data = dlg.get_data()
            new_op_id = None
            with self.db_manager.get_session() as session:
                op = Operation(
                    tech_process_id=self.tp_id,
                    number=data['number'],
                    name=data['name'],
                    code=data.get('code'),
                    shop=data.get('shop'),
                    equipment_id=data.get('equipment_id'),
                    profession_id=data.get('profession_id'),
                    grade=data.get('grade'),
                    machine_count=data.get('machine_count', 1),
                    include_in_mtp=bool(data.get('include_in_mtp', True)),
                    t_main=data.get('t_main', 0),
                    t_auxiliary=data.get('t_auxiliary', 0),
                    t_piece=data.get('t_piece', 0),
                    t_setup=data.get('t_setup', 0),
                    note=data.get('note'),
                    sort_order=len(self._operations),
                )
                session.add(op)
                session.flush()
                new_op_id = op.id
            # v7.7-fix: перенести pending-эскизы, выбранные ДО сохранения операции.
            if new_op_id is not None:
                panel = getattr(dlg, 'sketches_panel', None)
                if panel is not None and panel.has_pending():
                    panel.flush_pending_to(new_op_id)
            self._load_operations()
            self.tp_changed.emit(self.tp_id)

    def _edit_operation(self):
        op_id = self._get_current_op_id()
        if op_id is None:
            QMessageBox.information(self, "Выбор", "Выберите операцию для редактирования")
            return
        if not self._check_lock_or_warn():
            return
        op_data = next((o for o in self._operations if o['id'] == op_id), None)
        if not op_data:
            return
        from ui.dialogs.operation_dialog import OperationDialog
        dlg = OperationDialog(
            self.db_manager,
            op_data=op_data,
            product_designation=self._tp.get('product_designation', ''),
            parent=self,
        )
        accepted = (dlg.exec() == dlg.DialogCode.Accepted)
        # Эскизы сохраняются в БД сразу — обновляем индикатор в любом случае
        if not accepted:
            self._load_operations()
            return
        if accepted:
            data = dlg.get_data()
            with self.db_manager.get_session() as session:
                op = session.get(Operation, op_id)
                if op:
                    op.number = data['number']
                    op.name = data['name']
                    op.code = data.get('code')
                    op.shop = data.get('shop')
                    op.equipment_id = data.get('equipment_id')
                    op.profession_id = data.get('profession_id')
                    op.grade = data.get('grade')
                    op.machine_count = data.get('machine_count', 1)
                    op.include_in_mtp = bool(data.get('include_in_mtp', True))
                    op.t_main = data.get('t_main', 0)
                    op.t_auxiliary = data.get('t_auxiliary', 0)
                    op.t_piece = data.get('t_piece', 0)
                    op.t_setup = data.get('t_setup', 0)
                    op.note = data.get('note')
            self._load_operations()
            self.tp_changed.emit(self.tp_id)

    def _delete_operation(self):
        op_id = self._get_current_op_id()
        if op_id is None:
            return
        if not self._check_lock_or_warn():
            return
        op_data = next((o for o in self._operations if o['id'] == op_id), None)
        op_name = op_data['name'] if op_data else str(op_id)
        reply = QMessageBox.question(
            self, "Удаление (в корзину)",
            f"Перенести операцию «{op_name}» в корзину?\n"
            f"(Можно восстановить через «Сервис → Корзина»)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            from datetime import datetime
            with self.db_manager.get_session() as session:
                op = session.get(Operation, op_id)
                if op:
                    op.is_deleted = True
                    op.deleted_at = datetime.now()
            self._load_operations()
            self.tr_table.setRowCount(0)
            self.tp_changed.emit(self.tp_id)

    def _move_op_up(self):
        self._move_operation(-1)

    def _move_op_down(self):
        self._move_operation(1)

    def _copy_op_from_other_tp(self):
        """Скопировать операцию (со всеми переходами) из другого ТП в текущий."""
        from database.models import (
            Operation as OpM,
        )
        from database.models import (
            Transition as TrM,
        )
        from ui.dialogs.op_picker_dialog import OpPickerDialog

        dlg = OpPickerDialog(self.db_manager, exclude_tp_id=self.tp_id, parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        src_op_id = dlg.selected_op_id
        if not src_op_id:
            return

        next_num = self._next_op_number()
        with self.db_manager.get_session() as s:
            src = s.get(OpM, src_op_id)
            if not src:
                QMessageBox.warning(self, "Ошибка", "Операция-источник не найдена")
                return
            # Копируем операцию: новый sort_order — в конец
            max_order = max(
                (o.sort_order or 0 for o in s.query(OpM).filter_by(tech_process_id=self.tp_id)),
                default=0,
            )
            new_op = OpM(
                tech_process_id=self.tp_id,
                number=next_num,
                name=src.name,
                code=src.code,
                shop=src.shop,
                equipment_id=src.equipment_id,
                profession_id=src.profession_id,
                grade=src.grade,
                machine_count=src.machine_count,
                t_setup=src.t_setup,
                t_piece=src.t_piece,
                t_main=src.t_main,
                t_auxiliary=src.t_auxiliary,
                note=src.note,
                include_in_mtp=getattr(src, 'include_in_mtp', True),
                sort_order=max_order + 10,
            )
            s.add(new_op)
            s.flush()
            # И переходы
            src_trs = s.query(TrM).filter_by(operation_id=src.id).order_by(
                TrM.sort_order, TrM.id
            ).all()
            for t in src_trs:
                s.add(TrM(
                    operation_id=new_op.id,
                    number=t.number,
                    text=t.text,
                    code=t.code,
                    diameter=t.diameter,
                    length=t.length,
                    depth=t.depth,
                    feed=t.feed,
                    speed=t.speed,
                    rpm=t.rpm,
                    passes=t.passes,
                    sort_order=t.sort_order,
                ))
            s.flush()
            new_op_id = new_op.id

        self._log_audit(
            'create', 'operation', new_op_id,
            f'Скопирована из операции #{src_op_id}'
        )
        self._load_operations()
        QMessageBox.information(
            self, "Импорт операции",
            f"Операция перенесена с переходами. Назначен номер {next_num}."
        )

    def _move_operation(self, direction):
        row = self.op_table.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= len(self._operations):
            return

        op_id_a = int(self.op_table.item(row, 0).text())
        op_id_b = int(self.op_table.item(new_row, 0).text())

        with self.db_manager.get_session() as session:
            op_a = session.get(Operation, op_id_a)
            op_b = session.get(Operation, op_id_b)
            if op_a and op_b:
                op_a.sort_order, op_b.sort_order = op_b.sort_order, op_a.sort_order

        self._load_operations()
        self.op_table.setCurrentCell(new_row, 1)

    def _auto_calc_time(self):
        """Авторасчёт норм времени для всех операций ТП"""
        from modules.labor_calc import LaborCalculator
        session = self.db_manager.Session()
        try:
            calc = LaborCalculator(session)
            for op in self._operations:
                try:
                    calc.calculate_operation_time(op['id'])
                except Exception as e:
                    _log.debug('Non-critical op skipped: %s', e)
            session.commit()
        finally:
            session.close()
        self._load_operations()
        QMessageBox.information(self, "Авторасчёт", "Нормы времени рассчитаны по всем операциям")

    def _next_op_number(self):
        try:
            from modules import settings as _s
            existing = [op.get('number') for op in (self._operations or [])]
            return _s.next_op_number(existing)
        except Exception as e:
            _log.debug('Tab order fallback used: %s', e)
            if not self._operations:
                return '005'
            last = self._operations[-1]['number']
            try:
                n = int(last) + 5
                return str(n).zfill(3)
            except (ValueError, TypeError):
                return '005'

    # ──────────────────────────────────────────────────────────────
    # Обработчики переходов
    # ──────────────────────────────────────────────────────────────
    def _get_current_tr_id(self):
        row = self.tr_table.currentRow()
        if row < 0:
            return None
        return int(self.tr_table.item(row, 0).text())

    def _add_transition(self):
        op_id = getattr(self, '_current_op_id', self._get_current_op_id())
        if not op_id:
            QMessageBox.information(self, "Выбор", "Сначала выберите операцию")
            return
        next_num = str(len(self._transitions) + 1)
        from ui.dialogs.transition_dialog import TransitionDialog
        dlg = TransitionDialog(
            next_number=next_num,
            db_manager=self.db_manager,
            product_designation=self._tp.get('product_designation', ''),
            parent=self,
        )
        if dlg.exec() == dlg.DialogCode.Accepted:
            data = dlg.get_data()
            new_tr_id = None
            with self.db_manager.get_session() as session:
                tr = Transition(
                    operation_id=op_id,
                    number=data['number'],
                    text=data['text'],
                    code=data.get('code'),
                    diameter=data.get('diameter'),
                    length=data.get('length'),
                    depth=data.get('depth'),
                    feed=data.get('feed'),
                    speed=data.get('speed'),
                    rpm=data.get('rpm'),
                    passes=data.get('passes', 1),
                    sort_order=len(self._transitions),
                )
                session.add(tr)
                session.flush()
                new_tr_id = tr.id
            # v7.7-fix: перенести pending-эскизы перехода после его создания.
            if new_tr_id is not None:
                panel = getattr(dlg, 'sketches_panel', None)
                if panel is not None and panel.has_pending():
                    panel.flush_pending_to(new_tr_id)
            self._load_transitions(op_id)

    def _edit_transition(self):
        tr_id = self._get_current_tr_id()
        if tr_id is None:
            return
        tr_data = next((t for t in self._transitions if t['id'] == tr_id), None)
        if not tr_data:
            return
        from ui.dialogs.transition_dialog import TransitionDialog
        dlg = TransitionDialog(
            transition_data=tr_data,
            db_manager=self.db_manager,
            product_designation=self._tp.get('product_designation', ''),
            parent=self,
        )
        accepted = (dlg.exec() == dlg.DialogCode.Accepted)
        if not accepted:
            # Эскизы могли поменяться — освежим список переходов
            op_id = getattr(self, '_current_op_id', None)
            if op_id:
                self._load_transitions(op_id)
            return
        if accepted:
            data = dlg.get_data()
            with self.db_manager.get_session() as session:
                tr = session.get(Transition, tr_id)
                if tr:
                    tr.number = data['number']
                    tr.text = data['text']
                    tr.code = data.get('code')
                    tr.diameter = data.get('diameter')
                    tr.length = data.get('length')
                    tr.depth = data.get('depth')
                    tr.feed = data.get('feed')
                    tr.speed = data.get('speed')
                    tr.rpm = data.get('rpm')
                    tr.passes = data.get('passes', 1)
            op_id = getattr(self, '_current_op_id', None)
            if op_id:
                self._load_transitions(op_id)

    def _delete_transition(self):
        tr_id = self._get_current_tr_id()
        if tr_id is None:
            return
        tr_data = next((t for t in self._transitions if t['id'] == tr_id), None)
        name = (tr_data['text'][:40] + '...') if tr_data and len(tr_data.get('text','')) > 40 else (tr_data['text'] if tr_data else '')
        if QMessageBox.question(
            self, "Удаление", f"Удалить переход:\n«{name}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            with self.db_manager.get_session() as session:
                tr = session.get(Transition, tr_id)
                if tr:
                    session.delete(tr)
            op_id = getattr(self, '_current_op_id', None)
            if op_id:
                self._load_transitions(op_id)

    # ──────────────────────────────────────────────────────────────
    # Вкладка «Материальное нормирование»
    # ──────────────────────────────────────────────────────────────
    def _make_material_norms_tab(self):
        from ui.widgets.material_norms_widget import MaterialNormsWidget
        self._mat_norms_widget = MaterialNormsWidget(self.db_manager, self.tp_id, self)
        return self._mat_norms_widget

    # ──────────────────────────────────────────────────────────────
    # Вкладка «Расчёт себестоимости»
    # ──────────────────────────────────────────────────────────────
    def _make_cost_calc_tab(self):
        from ui.widgets.cost_calc_widget import CostCalcWidget
        self._cost_widget = CostCalcWidget(self.db_manager, self.tp_id, self)
        return self._cost_widget

    # ──────────────────────────────────────────────────────────────
    # Вкладка «Документы»
    # ──────────────────────────────────────────────────────────────
    def _make_documents_tab(self):
        from PyQt6.QtWidgets import (
            QAbstractItemView,
        )

        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(8)

        title = QLabel("Генерация технологических документов")
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        title.setFont(font)
        outer.addWidget(title)

        splitter_h = QHBoxLayout()

        # ── Левая колонка ──
        left = QVBoxLayout()

        # Количество (для МСК, ВНВ)
        qty_layout = QHBoxLayout()
        qty_layout.addWidget(QLabel("Кол-во изделий в партии:"))
        self._qty_spin = QSpinBox()
        self._qty_spin.setRange(1, 99999)
        self._qty_spin.setValue(1)
        self._qty_spin.setFixedWidth(90)
        qty_layout.addWidget(self._qty_spin)
        qty_layout.addStretch()
        left.addLayout(qty_layout)

        # Доп. поля для МТП
        mtp_group = QGroupBox("Заголовок МТП (необязательные поля)")
        mtp_form = QFormLayout(mtp_group)
        mtp_form.setContentsMargins(8, 6, 8, 6)
        mtp_form.setSpacing(4)
        self._mtp_project = QLineEdit()
        self._mtp_project.setPlaceholderText("Например: Ту-204")
        self._mtp_kit = QLineEdit()
        self._mtp_kit.setPlaceholderText("Например: 64050")
        self._mtp_order = QLineEdit()
        self._mtp_order.setPlaceholderText("Шифр заказа / № Заказ")
        mtp_form.addRow("Наименование проекта:", self._mtp_project)
        mtp_form.addRow("№ Комплекта (изделия):", self._mtp_kit)
        mtp_form.addRow("Шифр заказа / № Заказ:", self._mtp_order)
        try:
            from modules import settings as _s
            _saved = _s.get_mtp_header(self._tp.get('product_designation') or '')
            if _saved:
                self._mtp_project.setText(_saved.get('project_name', ''))
                self._mtp_kit.setText(_saved.get('kit_number', ''))
                self._mtp_order.setText(_saved.get('order_number', ''))
        except Exception as e:
            _log.debug('Non-critical operation skipped: %s', e)
        left.addWidget(mtp_group)

        # ── Добавление форм ──
        add_group = QGroupBox("Добавить документ в список формирования")
        add_layout = QHBoxLayout(add_group)
        add_layout.addWidget(QLabel("Форма:"))
        self._form_combo = QComboBox()
        self._form_combo.setMinimumWidth(220)
        from modules.doc_forms import DOC_FORM_REGISTRY
        for f in DOC_FORM_REGISTRY:
            label = f"{f.name}  — {f.gost}"
            self._form_combo.addItem(label, f.form_id)
        add_layout.addWidget(self._form_combo)

        add_layout.addWidget(QLabel("Формат:"))
        self._add_fmt_combo = QComboBox()
        self._add_fmt_combo.addItem("Excel (.xlsx)", "xlsx")
        self._add_fmt_combo.addItem("Word (.docx)", "docx")
        self._add_fmt_combo.addItem("PDF (.pdf)", "pdf")
        add_layout.addWidget(self._add_fmt_combo)

        add_btn = QPushButton("+  Добавить")
        add_btn.clicked.connect(self._add_doc_to_list)
        add_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; "
            "border: none; padding: 4px 12px; border-radius: 3px; font-weight: bold; }"
            "QPushButton:hover { background-color: #219a52; }")
        add_layout.addWidget(add_btn)
        left.addWidget(add_group)

        # ── Список на генерацию ──
        gen_group = QGroupBox("Список на генерацию")
        gen_layout = QVBoxLayout(gen_group)

        self._gen_list_widget = QListWidget()
        self._gen_list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self._gen_list_widget.setAlternatingRowColors(True)
        self._gen_list_widget.setMaximumHeight(180)
        gen_layout.addWidget(self._gen_list_widget)

        self._gen_list = []  # [{form_id, form_name, fmt, gost}, ...]

        list_btn_layout = QHBoxLayout()
        remove_btn = QPushButton("-  Удалить выбранные")
        remove_btn.clicked.connect(self._remove_doc_from_list)
        remove_btn.setStyleSheet(
            "QPushButton { color: #c0392b; padding: 4px 10px; }")
        list_btn_layout.addWidget(remove_btn)
        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self._clear_doc_list)
        list_btn_layout.addWidget(clear_btn)
        list_btn_layout.addStretch()
        gen_layout.addLayout(list_btn_layout)
        left.addWidget(gen_group)

        # Подсказка
        hint = QLabel("Двойной клик по строке — переключить формат")
        hint.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        left.addWidget(hint)

        # Кнопка генерации
        gen_btn = QPushButton("  Сгенерировать документы из списка  ")
        gen_btn.setFixedHeight(38)
        gen_btn.clicked.connect(self._generate_docs)
        gen_btn.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; color: white;
                border: none; border-radius: 4px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #2471a3; }
        """)
        left.addWidget(gen_btn)

        # Доп. кнопки
        aux_btns = QHBoxLayout()
        ktd_btn = QPushButton("Библиотека КТД...")
        ktd_btn.clicked.connect(self._open_ktd_browser)
        aux_btns.addWidget(ktd_btn)
        open_folder_btn = QPushButton("Папка экспорта")
        open_folder_btn.clicked.connect(self._open_export_folder)
        aux_btns.addWidget(open_folder_btn)
        zip_btn = QPushButton("ZIP-архив")
        zip_btn.clicked.connect(self._zip_all_docs)
        aux_btns.addWidget(zip_btn)
        aux_btns.addStretch()
        left.addLayout(aux_btns)

        left.addStretch()
        splitter_h.addLayout(left, stretch=1)

        # ── Правая колонка ──
        right = QVBoxLayout()

        right.addWidget(QLabel("Журнал генерации:"))
        self._doc_log = QTextEdit()
        self._doc_log.setReadOnly(True)
        self._doc_log.setMaximumHeight(150)
        self._doc_log.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 10px; "
            "background-color: #1e1e1e; color: #d4d4d4;")
        right.addWidget(self._doc_log)

        files_header = QHBoxLayout()
        self._files_label = QLabel("Сформированные документы на деталь:")
        files_header.addWidget(self._files_label)
        files_header.addStretch()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.setStyleSheet("QPushButton { padding: 3px 8px; }")
        refresh_btn.clicked.connect(self._refresh_export_files)
        files_header.addWidget(refresh_btn)
        right.addLayout(files_header)

        self._files_list = QListWidget()
        self._files_list.setIconSize(QSize(18, 18))
        self._files_list.itemDoubleClicked.connect(self._open_selected_file)
        self._files_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._files_list.customContextMenuRequested.connect(self._files_context_menu)
        right.addWidget(self._files_list, stretch=1)

        splitter_h.addLayout(right, stretch=1)

        self._form_combo.currentIndexChanged.connect(self._update_tp_formats)
        self._gen_list_widget.itemDoubleClicked.connect(self._toggle_tp_format)

        self._refresh_export_files()
        outer.addLayout(splitter_h)
        return w

    # ── Управление списком генерации (tp_editor) ──

    def _update_tp_formats(self):
        form_id = self._form_combo.currentData()
        from modules.doc_forms import DOC_FORM_REGISTRY
        form = next((f for f in DOC_FORM_REGISTRY if f.form_id == form_id), None)
        if form is None:
            return
        self._add_fmt_combo.clear()
        fmt_labels = {"xlsx": "Excel (.xlsx)", "docx": "Word (.docx)", "pdf": "PDF (.pdf)"}
        for fmt in form.formats:
            self._add_fmt_combo.addItem(fmt_labels.get(fmt, fmt), fmt)

    def _add_doc_to_list(self):
        try:
            form_id = self._form_combo.currentData()
            if form_id is None:
                return
            from modules.doc_forms import DOC_FORM_REGISTRY
            form = next((f for f in DOC_FORM_REGISTRY if f.form_id == form_id), None)
            if form is None:
                return
            fmt = self._add_fmt_combo.currentData()
            entry = {
                'form_id': form.form_id,
                'form_name': form.name,
                'gost': form.gost,
                'fmt': fmt,
            }
            self._gen_list.append(entry)
            label = f"{form.name}  [{fmt.upper()}]  — {form.gost}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, len(self._gen_list) - 1)
            self._gen_list_widget.addItem(item)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", f"Не удалось добавить форму:\n{e}")

    def _remove_doc_from_list(self):
        selected = self._gen_list_widget.selectedItems()
        if not selected:
            return
        indices = sorted(
            [self._gen_list_widget.row(item) for item in selected],
            reverse=True,
        )
        for idx in indices:
            self._gen_list_widget.takeItem(idx)
            del self._gen_list[idx]
        for i in range(self._gen_list_widget.count()):
            self._gen_list_widget.item(i).setData(Qt.ItemDataRole.UserRole, i)

    def _clear_doc_list(self):
        self._gen_list.clear()
        self._gen_list_widget.clear()

    def _toggle_tp_format(self, item):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self._gen_list):
            return
        from modules.doc_forms import DOC_FORM_REGISTRY
        entry = self._gen_list[idx]
        form = next((f for f in DOC_FORM_REGISTRY
                     if f.form_id == entry['form_id']), None)
        if form is None:
            return
        fmts = form.formats
        try:
            next_idx = (fmts.index(entry['fmt']) + 1) % len(fmts)
        except ValueError:
            next_idx = 0
        entry['fmt'] = fmts[next_idx]
        label = f"{entry['form_name']}  [{fmts[next_idx].upper()}]  — {entry['gost']}"
        item.setText(label)

    def _generate_docs(self):
        if not self._gen_list:
            self._doc_log.clear()
            self._doc_log.append("⚠  Добавьте формы документов в список генерации")
            return

        qty = self._qty_spin.value()
        self._doc_log.clear()
        self._doc_log.append(f"ТП: {self._tp.get('number', '')}   Партия: {qty} шт")
        self._doc_log.append("─" * 50)

        session = self.db_manager.Session()
        last_path = None
        try:
            from modules.doc_forms import generate_form

            for i, entry in enumerate(self._gen_list, start=1):
                form_id = entry['form_id']
                fmt = entry['fmt']
                self._doc_log.append(
                    f"[{i}/{len(self._gen_list)}] {entry['form_name']} ({fmt.upper()})...")
                try:
                    kwargs = {'quantity': qty}
                    if form_id == 'MTP':
                        kwargs['project_name'] = self._mtp_project.text().strip()
                        kwargs['kit_number'] = self._mtp_kit.text().strip()
                        kwargs['order_number'] = self._mtp_order.text().strip()
                        # Запоминаем последние значения
                        try:
                            from modules import settings as _s
                            _s.set_mtp_header(
                                self._tp.get('product_designation') or '',
                                project_name=kwargs['project_name'],
                                kit_number=kwargs['kit_number'],
                                order_number=kwargs['order_number'],
                            )
                        except Exception:
                            pass

                    result = generate_form(session, form_id, self.tp_id, fmt, **kwargs)
                    if isinstance(result, list):
                        for p in result:
                            self._doc_log.append(f"   OK  {p.name}")
                        if result:
                            last_path = result[-1]
                    else:
                        self._doc_log.append(f"   OK  {result.name}")
                        last_path = result
                except Exception as e:
                    self._doc_log.append(f"   ERR {e}")

            self._doc_log.append("─" * 50)
            folder = self._product_export_dir()
            if folder is not None:
                self._doc_log.append(f"Готово! Папка: {folder}")
            else:
                self._doc_log.append("Готово! Файлы сохранены в папку exports.")
            if last_path:
                self._export_path = last_path

        except Exception as e:
            self._doc_log.append(f"Критическая ошибка: {e}")
        finally:
            session.close()
            self._refresh_export_files()

    def _open_ktd_browser(self):
        from ui.dialogs.ktd_browser_dialog import KTDBrowserDialog
        dlg = KTDBrowserDialog(self)
        dlg.exec()

    # ──────────────────────────────────────────────────────────────
    # Папка детали и список сформированных документов
    # ──────────────────────────────────────────────────────────────
    def _product_export_dir(self):
        """Папка экспорта для текущей детали (или None, если нет designation)."""
        from config import product_export_dir
        designation = (self._tp.get('product_designation') or '').strip()
        if not designation:
            return None
        return product_export_dir(designation)

    def _refresh_export_files(self):
        """Перечитать содержимое папки экспорта детали и наполнить список."""
        from datetime import datetime as _dt

        from PyQt6.QtCore import QFileInfo
        from PyQt6.QtWidgets import QListWidgetItem

        if not hasattr(self, '_files_list'):
            return

        self._files_list.clear()
        folder = self._product_export_dir()
        if folder is None:
            self._files_label.setText("Сформированные документы на деталь:")
            return

        designation = self._tp.get('product_designation') or ''
        if not folder.exists():
            self._files_label.setText(
                f"Сформированные документы на деталь «{designation}»: 0 файлов"
            )
            return

        files = sorted(
            (p for p in folder.iterdir() if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        self._files_label.setText(
            f"Сформированные документы на деталь «{designation}»: "
            f"{len(files)} файл(ов)"
        )
        if not files:
            return

        provider = QFileIconProvider()
        for p in files:
            stat = p.stat()
            mtime = _dt.fromtimestamp(stat.st_mtime).strftime('%d.%m.%Y %H:%M')
            size_kb = max(1, round(stat.st_size / 1024))
            item = QListWidgetItem(f"{p.name}    [{mtime}, {size_kb} КБ]")
            item.setIcon(provider.icon(QFileInfo(str(p))))
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            item.setToolTip(str(p))
            self._files_list.addItem(item)

    def _open_selected_file(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self._open_path(path)

    def _files_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        item = self._files_list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self._files_list)
        act_open = menu.addAction("Открыть")
        act_folder = menu.addAction("Показать в папке")
        menu.addSeparator()
        act_delete = menu.addAction("Удалить файл")
        chosen = menu.exec(self._files_list.mapToGlobal(pos))
        if chosen is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        if chosen == act_open:
            self._open_path(path)
        elif chosen == act_folder:
            from pathlib import Path as _P
            self._open_path(str(_P(path).parent))
        elif chosen == act_delete:
            from pathlib import Path as _P

            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Удалить файл",
                f"Удалить файл «{_P(path).name}»?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    _P(path).unlink()
                except OSError as e:
                    QMessageBox.warning(self, "Ошибка", f"Не удалось удалить:\n{e}")
                self._refresh_export_files()

    @staticmethod
    def _open_path(path: str):
        """Открыть файл/папку в системной программе. Кросс-платформенно."""
        import os
        import subprocess
        import sys
        try:
            if sys.platform.startswith('win'):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            _log.debug('Non-critical operation skipped: %s', e)

    def _open_export_folder(self):
        folder = self._product_export_dir()
        if folder is None:
            from config import EXPORT_DIR
            folder = EXPORT_DIR
        if folder.exists():
            self._open_path(str(folder))

    def _zip_all_docs(self):
        """Собрать все файлы из папки детали в один ZIP-архив."""
        import zipfile
        from datetime import datetime
        folder = self._product_export_dir()
        if folder is None or not folder.exists():
            QMessageBox.information(
                self, "Архив",
                "Папка экспорта пуста — нечего архивировать."
            )
            return
        files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() != '.zip']
        if not files:
            QMessageBox.information(
                self, "Архив",
                "В папке нет документов для архивирования."
            )
            return
        designation = self._tp.get('product_designation', 'product')
        from config import _sanitize_designation
        safe = _sanitize_designation(designation)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_path = folder / f'Архив_{safe}_{ts}.zip'
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for p in files:
                    zf.write(p, arcname=p.name)
        except OSError as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось создать архив:\n{e}")
            return
        self._refresh_export_files()
        QMessageBox.information(
            self, "Архив создан",
            f"Архив со {len(files)} файлами:\n{zip_path}"
        )

    # ──────────────────────────────────────────────────────────────
    # Публичный метод для обновления заголовка вкладки
    # ──────────────────────────────────────────────────────────────
    def get_tab_title(self):
        tp_num = self._tp.get('number', 'ТП')
        status = self._tp.get('status')
        if status in STATUS_COLORS:
            _, label = STATUS_COLORS[status]
            return f"{tp_num}  [{label}]"
        return tp_num

    def refresh(self):
        """Перечитать данные из БД"""
        self._load_tp_data()
        self._load_operations()
