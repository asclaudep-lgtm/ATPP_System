"""
Диалог генерации технологической документации.

Реализован по образцу СПРУТ-ТП:
  - Реестр доступных форм (doc_forms.DOC_FORM_REGISTRY)
  - Динамический список «на генерацию» — добавление / удаление
  - Выбор формата для каждой формы индивидуально
"""
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from modules.doc_forms import DOC_FORM_REGISTRY, generate_form


class DocGenerateDialog(QDialog):
    """Диалог генерации документов."""

    def __init__(self, db_manager, tp_id=None, tp_number="", parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._given_tp_id = tp_id
        self._given_tp_number = tp_number
        self._tp_list = []
        self._gen_list = []  # [{form_id, form_name, fmt, gost}, ...]

        self.setWindowTitle("Генерация документов ТП")
        self.setMinimumWidth(700)
        self.setMinimumHeight(580)
        self.setModal(True)

        self._load_tp_list()
        self._init_ui()

    def _load_tp_list(self):
        session = self.db_manager.Session()
        try:
            from database.models import TechProcess
            tps = (session.query(TechProcess)
                   .filter(not TechProcess.is_deleted)
                   .order_by(TechProcess.id.desc())
                   .all())
            for tp in tps:
                status = tp.status.value if hasattr(tp.status, 'value') else str(tp.status)
                label = f"ТП {tp.number} — {tp.product.designation} [{status}]"
                self._tp_list.append((tp.id, label))
        finally:
            session.close()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Заголовок ──
        title = QLabel("Генерация технологических документов")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # ── Выбор ТП ──
        tp_group = QGroupBox("Технологический процесс")
        tp_layout = QHBoxLayout(tp_group)
        tp_layout.addWidget(QLabel("ТП:"))
        self.tp_combo = QComboBox()
        self.tp_combo.setMinimumWidth(350)
        for tp_id, label in self._tp_list:
            self.tp_combo.addItem(label, tp_id)
        if self._given_tp_id:
            for i in range(self.tp_combo.count()):
                if self.tp_combo.itemData(i) == self._given_tp_id:
                    self.tp_combo.setCurrentIndex(i)
                    break
        tp_layout.addWidget(self.tp_combo)
        tp_layout.addStretch()
        layout.addWidget(tp_group)

        if not self._tp_list:
            layout.addWidget(QLabel("⚠  Нет ТП в базе данных. Создайте ТП через редактор."))
            close_btn = QPushButton("Закрыть")
            close_btn.clicked.connect(self.accept)
            layout.addWidget(close_btn)
            return

        # ── Список доступных форм + кнопка добавления ──
        add_group = QGroupBox("Доступные формы документов")
        add_layout = QHBoxLayout(add_group)
        add_layout.addWidget(QLabel("Форма:"))
        self._form_combo = QComboBox()
        self._form_combo.setMinimumWidth(300)
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
        add_btn.clicked.connect(self._add_to_list)
        add_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; "
            "border: none; padding: 5px 14px; border-radius: 3px; font-weight: bold; }"
            "QPushButton:hover { background-color: #219a52; }")
        add_layout.addWidget(add_btn)
        layout.addWidget(add_group)

        # ── Список на генерацию ──
        gen_group = QGroupBox("Список на генерацию")
        gen_layout = QVBoxLayout(gen_group)

        self._gen_list_widget = QListWidget()
        self._gen_list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self._gen_list_widget.setAlternatingRowColors(True)
        gen_layout.addWidget(self._gen_list_widget)

        # Кнопки управления списком
        list_btn_layout = QHBoxLayout()
        remove_btn = QPushButton("-  Удалить выбранные")
        remove_btn.clicked.connect(self._remove_from_list)
        remove_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; "
            "border: none; padding: 5px 14px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #a93226; }")
        list_btn_layout.addWidget(remove_btn)

        clear_btn = QPushButton("Очистить список")
        clear_btn.clicked.connect(self._clear_list)
        list_btn_layout.addWidget(clear_btn)

        list_btn_layout.addStretch()
        list_btn_layout.addWidget(QLabel("Двойной клик — изменить формат"))
        gen_layout.addLayout(list_btn_layout)
        layout.addWidget(gen_group)

        # ── Лог ──
        log_group = QGroupBox("Журнал генерации")
        log_layout = QVBoxLayout(log_group)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(120)
        self.log_edit.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 10px; "
            "background-color: #1e1e1e; color: #d4d4d4;")
        log_layout.addWidget(self.log_edit)
        layout.addWidget(log_group)

        # ── Кнопки действий ──
        btn_layout = QHBoxLayout()

        self.gen_btn = QPushButton("  Сгенерировать  ")
        self.gen_btn.clicked.connect(self._generate)
        self.gen_btn.setStyleSheet("""
            QPushButton {
                background-color: #2980b9; color: white;
                border: none; padding: 8px 22px;
                border-radius: 4px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #2471a3; }
        """)

        self.open_folder_btn = QPushButton("Открыть папку")
        self.open_folder_btn.clicked.connect(self._open_export_folder)
        self.open_folder_btn.setEnabled(False)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.gen_btn)
        btn_layout.addWidget(self.open_folder_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._export_dir = None

        # Обновить доступные форматы при смене формы
        self._form_combo.currentIndexChanged.connect(self._update_add_formats)

        # Двойной клик по элементу списка — смена формата
        self._gen_list_widget.itemDoubleClicked.connect(self._toggle_format)

    def _update_add_formats(self):
        """Обновить комбо форматов в соответствии с выбранной формой."""
        form_id = self._form_combo.currentData()
        form = next((f for f in DOC_FORM_REGISTRY if f.form_id == form_id), None)
        if form is None:
            return
        self._add_fmt_combo.clear()
        fmt_labels = {"xlsx": "Excel (.xlsx)", "docx": "Word (.docx)", "pdf": "PDF (.pdf)"}
        for fmt in form.formats:
            self._add_fmt_combo.addItem(fmt_labels.get(fmt, fmt), fmt)

    def _add_to_list(self):
        """Добавить выбранную форму в список на генерацию."""
        try:
            form_id = self._form_combo.currentData()
            if form_id is None:
                return
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
            QMessageBox.critical(self, "Ошибка", f"Не удалось добавить форму:\n{e}")

    def _remove_from_list(self):
        """Удалить выбранные формы из списка на генерацию."""
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
        # Обновить UserRole
        for i in range(self._gen_list_widget.count()):
            self._gen_list_widget.item(i).setData(Qt.ItemDataRole.UserRole, i)

    def _clear_list(self):
        """Очистить список на генерацию."""
        self._gen_list.clear()
        self._gen_list_widget.clear()

    def _toggle_format(self, item):
        """Переключить формат для элемента списка по двойному клику."""
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self._gen_list):
            return
        entry = self._gen_list[idx]
        form = next((f for f in DOC_FORM_REGISTRY
                     if f.form_id == entry['form_id']), None)
        if form is None:
            return
        # Циклически переключить на следующий доступный формат
        fmts = form.formats
        cur = entry['fmt']
        try:
            next_idx = (fmts.index(cur) + 1) % len(fmts)
        except ValueError:
            next_idx = 0
        entry['fmt'] = fmts[next_idx]
        label = f"{entry['form_name']}  [{fmts[next_idx].upper()}]  — {entry['gost']}"
        item.setText(label)

    def _log(self, msg):
        self.log_edit.append(msg)

    def _current_tp_id(self):
        return self.tp_combo.currentData()

    def _generate(self):
        tp_id = self._current_tp_id()
        if tp_id is None:
            QMessageBox.warning(self, "Выбор", "Выберите технологический процесс")
            return
        if not self._gen_list:
            QMessageBox.warning(self, "Список",
                                "Добавьте хотя бы одну форму документа в список генерации")
            return

        self.gen_btn.setEnabled(False)
        self.log_edit.clear()
        self._log(f"ТП ID: {tp_id}")
        self._log(f"Документов к генерации: {len(self._gen_list)}")
        self._log("─" * 50)

        session = self.db_manager.Session()
        try:
            for i, entry in enumerate(self._gen_list, start=1):
                form_id = entry['form_id']
                fmt = entry['fmt']
                self._log(f"[{i}/{len(self._gen_list)}] {entry['form_name']} ({fmt.upper()})...")
                try:
                    result = generate_form(session, form_id, tp_id, fmt)
                    if isinstance(result, list):
                        for p in result:
                            self._log(f"  ✓  {p.name}")
                        if result:
                            self._export_dir = result[0].parent
                    else:
                        self._log(f"  ✓  {result.name}")
                        self._export_dir = result.parent
                    self.open_folder_btn.setEnabled(True)
                except Exception as e:
                    self._log(f"  ✗  Ошибка: {e}")

            self._log("─" * 50)
            self._log("Готово.")
        except Exception as e:
            self._log(f"Критическая ошибка: {e}")
        finally:
            session.close()
            self.gen_btn.setEnabled(True)

    def _open_export_folder(self):
        if self._export_dir and self._export_dir.exists():
            subprocess.Popen(f'explorer "{self._export_dir}"')
