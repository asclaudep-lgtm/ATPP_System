"""TP editor widget — metadata, operations view, norms, documents."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit,
    QTableWidget, QTableWidgetItem, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from database.models import (
    TechProcess, Product, Operation, TPStatus, TPType, TechnologyType,
)


STATUS_COLORS = {
    TPStatus.DRAFT:    ('#f39c12', 'Черновик'),
    TPStatus.REVIEW:   ('#8e44ad', 'Согласование'),
    TPStatus.REWORK:   ('#e74c3c', 'Доработка'),
    TPStatus.APPROVED: ('#27ae60', 'Утверждён'),
    TPStatus.ARCHIVED: ('#95a5a6', 'Архив'),
}


class TPEditorWidget(QWidget):
    """Lightweight TP metadata editor with operations/norms/docs tabs.

    Complements the full ui.widgets.tp_editor.TPEditorWidget which handles
    detailed operation/transition editing.

    Signals:
        tp_saved(tp_id)
        generate_route_card_requested(tp_id, fmt)
    """

    tp_saved = pyqtSignal(int)
    generate_route_card_requested = pyqtSignal(int, str)

    def __init__(self, db_manager, tp_id, user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.tp_id = tp_id
        self.user = user
        self._tp_data = None

        self._load()
        self._init_ui()

    def _load(self):
        with self.db_manager.get_session() as s:
            tp = s.get(TechProcess, self.tp_id)
            if tp:
                prod = tp.product
                self._tp_data = {
                    'id': tp.id,
                    'number': tp.number,
                    'product_name': f"{prod.designation} — {prod.name}"
                                    if prod else '—',
                    'product_id': tp.product_id,
                    'tp_type': tp.tp_type,
                    'technology_type': tp.technology_type,
                    'version': tp.version or '1.0',
                    'execution_variant': getattr(tp, 'execution_variant', '') or '',
                    'status': tp.status,
                    'description': tp.description or '',
                    'author_id': tp.author_id,
                }
            else:
                self._tp_data = None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        if self._tp_data is None:
            layout.addWidget(QLabel("ТП не найден или удалён."))
            return

        d = self._tp_data

        # Header
        hdr = QHBoxLayout()
        color, _ = STATUS_COLORS.get(d['status'], ('#555', '?'))
        title = QLabel(f"ТП: {d['number']} — {d['product_name']}")
        tf = QFont()
        tf.setPointSize(13)
        tf.setBold(True)
        title.setFont(tf)
        hdr.addWidget(title)
        hdr.addStretch()

        status_lbl = QLabel(
            f" [{d['status'].value if hasattr(d['status'], 'value') else str(d['status'])}]")
        status_lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 12px;")
        hdr.addWidget(status_lbl)

        save_btn = QPushButton("Сохранить")
        save_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; "
            "border: none; padding: 6px 16px; border-radius: 4px; }")
        save_btn.clicked.connect(self._save)
        hdr.addWidget(save_btn)
        layout.addLayout(hdr)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._build_header_tab(), "Шапка")
        tabs.addTab(self._build_ops_tab(), "Операции")
        tabs.addTab(self._build_norms_tab(), "Нормы")
        tabs.addTab(self._build_docs_tab(), "Документы")
        layout.addWidget(tabs)

    # ── Header tab ────────────────────────────────────────────────

    def _build_header_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        d = self._tp_data

        self._num_edit = QLineEdit(d['number'])
        form.addRow("Номер ТП *:", self._num_edit)

        self._ver_edit = QLineEdit(d['version'])
        form.addRow("Версия:", self._ver_edit)

        self._variant_edit = QLineEdit(d['execution_variant'])
        form.addRow("Вариант исполнения:", self._variant_edit)

        self._tp_type_combo = QComboBox()
        for t in TPType:
            self._tp_type_combo.addItem(t.value, t)
        if d['tp_type']:
            idx = self._tp_type_combo.findData(d['tp_type'])
            if idx >= 0:
                self._tp_type_combo.setCurrentIndex(idx)
        form.addRow("Тип ТП:", self._tp_type_combo)

        self._tech_type_combo = QComboBox()
        self._tech_type_combo.addItem("—", None)
        for t in TechnologyType:
            self._tech_type_combo.addItem(t.value, t)
        if d['technology_type']:
            idx = self._tech_type_combo.findData(d['technology_type'])
            if idx >= 0:
                self._tech_type_combo.setCurrentIndex(idx)
        form.addRow("Вид технологии:", self._tech_type_combo)

        self._status_combo = QComboBox()
        current_status = d['status']
        for st in TPStatus:
            self._status_combo.addItem(st.value, st)
        idx = self._status_combo.findData(current_status)
        if idx >= 0:
            self._status_combo.setCurrentIndex(idx)
        form.addRow("Статус:", self._status_combo)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlainText(d['description'])
        self._desc_edit.setMaximumHeight(80)
        form.addRow("Описание:", self._desc_edit)

        # Product link (read-only)
        prod_lbl = QLabel(d['product_name'])
        prod_lbl.setStyleSheet("color: #2980b9;")
        form.addRow("Изделие:", prod_lbl)

        return w

    # ── Operations tab ────────────────────────────────────────────

    def _build_ops_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        self._ops_table = QTableWidget(0, 5)
        self._ops_table.setHorizontalHeaderLabels(
            ["№", "Операция", "Оборудование", "Тшт", "Тпз"])
        self._ops_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._ops_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        lay.addWidget(self._ops_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Добавить операцию")
        add_btn.clicked.connect(self._on_add_operation)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._refresh_ops_table()
        return w

    def _refresh_ops_table(self):
        with self.db_manager.get_session() as s:
            ops = (s.query(Operation)
                   .filter(Operation.tech_process_id == self.tp_id)
                   .order_by(Operation.number)
                   .all())
            self._ops_table.setRowCount(len(ops))
            for i, op in enumerate(ops):
                self._ops_table.setItem(
                    i, 0, QTableWidgetItem(str(op.number)))
                self._ops_table.setItem(
                    i, 1, QTableWidgetItem(op.name or ''))
                equip = op.equipment.name if op.equipment else ''
                self._ops_table.setItem(
                    i, 2, QTableWidgetItem(equip))
                self._ops_table.setItem(
                    i, 3, QTableWidgetItem(
                        f'{op.t_piece:.1f}' if op.t_piece else '—'))
                self._ops_table.setItem(
                    i, 4, QTableWidgetItem(
                        f'{op.t_setup:.1f}' if op.t_setup else '—'))
            self._ops_table.resizeColumnsToContents()

    def _on_add_operation(self):
        # Open the full TP editor
        from ui.widgets.tp_editor import TPEditorWidget as FullTPEditor
        for i in range(self.window().work_area.count()):
            w = self.window().work_area.widget(i)
            if (hasattr(w, 'tp_id') and w.tp_id == self.tp_id
                    and type(w).__name__ == 'TPEditorWidget'
                    and hasattr(w, '_has_operations')):
                self.window().work_area.setCurrentIndex(i)
                return
        editor = FullTPEditor(
            self.db_manager, self.tp_id, self.user, self.window())
        editor.tp_changed.connect(lambda tid: (
            self._refresh_ops_table(),
            self.tp_saved.emit(tid),
        ))
        idx = self.window().work_area.addTab(
            editor, f"ТП: {self._tp_data['number']}")
        self.window().work_area.setCurrentIndex(idx)

    # ── Norms tab ─────────────────────────────────────────────────

    def _build_norms_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        # Summary of all operations
        with self.db_manager.get_session() as s:
            ops = (s.query(Operation)
                   .filter(Operation.tech_process_id == self.tp_id)
                   .all())
            total_t_piece = sum(
                (op.t_piece or 0) for op in ops)
            total_t_setup = sum(
                (op.t_setup or 0) for op in ops)
            total_t_piece_calc = total_t_piece / max(len(ops), 1)

        summary = (
            f"Всего операций: {len(ops)}\n"
            f"Суммарное Тшт: {total_t_piece:.1f} мин\n"
            f"Суммарное Тпз: {total_t_setup:.1f} мин\n"
            f"Среднее Тшт: {total_t_piece_calc:.1f} мин/оп"
        )
        lay.addWidget(QLabel(summary))

        # Material norms from BOM
        from database.models import BOMItem, MaterialNorm
        with self.db_manager.get_session() as s:
            norms = (s.query(MaterialNorm)
                     .filter(MaterialNorm.tech_process_id == self.tp_id)
                     .all())
            if norms:
                lay.addWidget(QLabel(
                    f"Норм материалов: {len(norms)}"))
            else:
                lay.addWidget(QLabel(
                    "Нормы материалов: не заданы."))

        lay.addStretch()
        return w

    # ── Documents tab ─────────────────────────────────────────────

    def _build_docs_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        lay.addWidget(QLabel("Генерация документов для ТП:"))

        btn_xlsx = QPushButton("Маршрутная карта — Excel (.xlsx)")
        btn_xlsx.clicked.connect(
            lambda: self.generate_route_card_requested.emit(self.tp_id, 'xlsx'))
        lay.addWidget(btn_xlsx)

        btn_docx = QPushButton("Маршрутная карта — Word (.docx)")
        btn_docx.clicked.connect(
            lambda: self.generate_route_card_requested.emit(self.tp_id, 'docx'))
        lay.addWidget(btn_docx)

        btn_pdf = QPushButton("Маршрутная карта — PDF")
        btn_pdf.clicked.connect(
            lambda: self.generate_route_card_requested.emit(self.tp_id, 'pdf'))
        lay.addWidget(btn_pdf)

        lay.addWidget(QLabel(
            "\nОперационные карты и ведомости — будут добавлены в Фазе 3."))
        lay.addStretch()
        return w

    # ── Save ──────────────────────────────────────────────────────

    def _save(self):
        number = self._num_edit.text().strip()
        if not number:
            QMessageBox.warning(self, "Валидация",
                                "Номер ТП обязателен.")
            return
        try:
            with self.db_manager.get_session() as s:
                tp = s.get(TechProcess, self.tp_id)
                if not tp:
                    return
                tp.number = number
                tp.version = self._ver_edit.text().strip() or '1.0'
                tp.execution_variant = (
                    self._variant_edit.text().strip() or None)
                tp.tp_type = self._tp_type_combo.currentData()
                tp.technology_type = self._tech_type_combo.currentData()
                tp.status = self._status_combo.currentData()
                tp.description = (
                    self._desc_edit.toPlainText().strip() or None)
            self._tp_data['number'] = number
            self._tp_data['status'] = self._status_combo.currentData()
            self.tp_saved.emit(self.tp_id)
            QMessageBox.information(self, "Сохранено",
                                    f"ТП «{number}» сохранён.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить:\n{e}")

    def get_tab_title(self):
        d = self._tp_data or {}
        return f"ТП: {d.get('number', '?')}"
