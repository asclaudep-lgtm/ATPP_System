"""Generic reference editor — one widget for all reference types.

Field configs define the form layout; a single QTableWidget + form
handles CRUD for materials, equipment, tools, and professions.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QSplitter,
    QLabel, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QPushButton, QTextEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from database.models import Material, Equipment, Tool, Profession


# ——— Field configs ——————————————————————————————————————————————

def _field(name: str, label: str, widget='line', options=None, **kw):
    return {'name': name, 'label': label, 'widget': widget,
            'options': options, 'extra': kw}

# Each config is: (model_class, table_columns, field_list, title_field)
REFERENCE_CONFIGS = {
    'material': {
        'model': Material,
        'title': 'Материалы',
        'columns': ['name', 'grade', 'gost', 'density', 'price_per_kg'],
        'col_labels': ['Наименование', 'Марка', 'ГОСТ', 'Плотность', 'Цена/кг'],
        'fields': [
            _field('name', 'Наименование *'),
            _field('grade', 'Марка'),
            _field('gost', 'ГОСТ'),
            _field('density', 'Плотность', 'spin_double',
                   suffix=' кг/м³', min_val=0, max_val=50000, decimals=0),
            _field('price_per_kg', 'Цена за кг', 'spin_double',
                   suffix=' руб', min_val=0, max_val=100000, decimals=2),
            _field('description', 'Описание', 'text'),
        ],
    },
    'equipment': {
        'model': Equipment,
        'title': 'Оборудование',
        'columns': ['name', 'model', 'type', 'power', 'cost_per_hour'],
        'col_labels': ['Наименование', 'Модель', 'Тип', 'Мощность, кВт',
                       'Стоимость часа'],
        'fields': [
            _field('name', 'Наименование *'),
            _field('model', 'Модель'),
            _field('type', 'Тип'),
            _field('power', 'Мощность', 'spin_double',
                   suffix=' кВт', min_val=0, max_val=10000, decimals=1),
            _field('cost_per_hour', 'Стоимость часа', 'spin_double',
                   suffix=' руб', min_val=0, max_val=100000, decimals=2),
            _field('description', 'Описание', 'text'),
        ],
    },
    'tool': {
        'model': Tool,
        'title': 'Инструмент',
        'columns': ['designation', 'name', 'tool_type'],
        'col_labels': ['Обозначение', 'Наименование', 'Тип'],
        'fields': [
            _field('designation', 'Обозначение *'),
            _field('name', 'Наименование'),
            _field('tool_type', 'Тип', 'combo',
                   options=['', 'Режущий', 'Измерительный',
                            'Вспомогательный', 'Слесарный']),
            _field('description', 'Описание', 'text'),
        ],
    },
    'profession': {
        'model': Profession,
        'title': 'Профессии',
        'columns': ['name', 'typical_grade'],
        'col_labels': ['Наименование', 'Типовой разряд'],
        'fields': [
            _field('name', 'Наименование *'),
            _field('typical_grade', 'Типовой разряд', 'spin_int',
                   min_val=1, max_val=8),
        ],
    },
}


class ReferenceEditorWidget(QWidget):
    """Generic CRUD editor for a single reference type.

    Left: table with all records.  Right: form for selected record.
    """

    data_changed = pyqtSignal()

    def __init__(self, db_manager, ref_type: str, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        cfg = REFERENCE_CONFIGS.get(ref_type)
        if cfg is None:
            raise ValueError(f"Unknown reference type: {ref_type}")
        self._cfg = cfg
        self._model_class = cfg['model']
        self._current_id = None
        self._init_ui()
        self._refresh_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        title = QLabel(self._cfg['title'])
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: table
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, len(self._cfg['col_labels']))
        self._table.setHorizontalHeaderLabels(self._cfg['col_labels'])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.selectionModel().selectionChanged.connect(self._on_select)
        ll.addWidget(self._table)

        add_btn = QPushButton("+ Добавить")
        add_btn.clicked.connect(self._add)
        ll.addWidget(add_btn)
        splitter.addWidget(left)

        # Right: form
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 8, 0)

        self._form_layout = QFormLayout()
        self._widgets = {}
        for fdef in self._cfg['fields']:
            w = self._make_widget(fdef)
            self._widgets[fdef['name']] = w
            self._form_layout.addRow(fdef['label'] + ':', w)
        rl.addLayout(self._form_layout)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; "
            "border: none; padding: 4px 16px; border-radius: 4px; }")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        del_btn = QPushButton("Удалить")
        del_btn.setStyleSheet(
            "QPushButton { color: #e74c3c; border: none; "
            "padding: 4px 16px; }")
        del_btn.clicked.connect(self._delete)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        rl.addLayout(btn_row)
        splitter.addWidget(right)

        splitter.setSizes([350, 300])
        layout.addWidget(splitter)

    def _make_widget(self, fdef):
        wtype = fdef['widget']
        if wtype == 'spin_double':
            w = QDoubleSpinBox()
            ex = fdef['extra']
            w.setRange(ex.get('min', 0), ex.get('max', 999999))
            w.setDecimals(ex.get('decimals', 2))
            if ex.get('suffix'):
                w.setSuffix(' ' + ex['suffix'])
            return w
        elif wtype == 'spin_int':
            w = QSpinBox()
            ex = fdef['extra']
            w.setRange(ex.get('min', 0), ex.get('max', 999))
            return w
        elif wtype == 'combo':
            w = QComboBox()
            for opt in (fdef['options'] or []):
                w.addItem(opt)
            return w
        elif wtype == 'text':
            w = QTextEdit()
            w.setMaximumHeight(80)
            return w
        else:
            return QLineEdit()

    # ── Table operations ──────────────────────────────────────────

    def _refresh_table(self):
        self._table.clearSelection()
        self._table.setRowCount(0)
        with self.db_manager.get_session() as s:
            rows = s.query(self._model_class).order_by(
                self._model_class.id).all()
            self._table.setRowCount(len(rows))
            cols = self._cfg['columns']
            for i, obj in enumerate(rows):
                for j, col in enumerate(cols):
                    val = getattr(obj, col, None)
                    text = ''
                    if val is not None:
                        if hasattr(val, 'value'):
                            text = str(val.value)
                        else:
                            text = str(val)
                    self._table.setItem(i, j, QTableWidgetItem(text))
                self._table.item(i, 0).setData(
                    Qt.ItemDataRole.UserRole, obj.id)
        self._table.resizeColumnsToContents()

    def _on_select(self):
        sel = self._table.selectedItems()
        if not sel:
            self._current_id = None
            self._clear_form()
            return
        row = sel[0].row()
        obj_id = self._table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self._current_id = obj_id
        self._load_to_form(obj_id)

    def _load_to_form(self, obj_id):
        with self.db_manager.get_session() as s:
            obj = s.query(self._model_class).get(obj_id)
            if not obj:
                self._clear_form()
                return
            for fdef in self._cfg['fields']:
                val = getattr(obj, fdef['name'], None)
                w = self._widgets[fdef['name']]
                if isinstance(w, QLineEdit):
                    w.setText(str(val) if val is not None else '')
                elif isinstance(w, QDoubleSpinBox):
                    if val is not None:
                        w.setValue(float(val))
                    else:
                        w.setValue(0)
                elif isinstance(w, QSpinBox):
                    if val is not None:
                        w.setValue(int(val))
                    else:
                        w.setValue(0)
                elif isinstance(w, QComboBox):
                    if val:
                        idx = w.findText(str(val))
                        if idx >= 0:
                            w.setCurrentIndex(idx)
                elif isinstance(w, QTextEdit):
                    w.setPlainText(str(val) if val is not None else '')

    def _clear_form(self):
        for fdef in self._cfg['fields']:
            w = self._widgets[fdef['name']]
            if isinstance(w, QLineEdit):
                w.clear()
            elif isinstance(w, (QDoubleSpinBox, QSpinBox)):
                w.setValue(0)
            elif isinstance(w, QComboBox):
                w.setCurrentIndex(0)
            elif isinstance(w, QTextEdit):
                w.clear()

    # ── CRUD ──────────────────────────────────────────────────────

    def _add(self):
        # Get required field name
        req_field = self._cfg['fields'][0]['name']
        val, ok = QInputDialog.getText(
            self, "Добавить",
            f"{self._cfg['fields'][0]['label']}:")
        if not ok or not val.strip():
            return
        try:
            with self.db_manager.get_session() as s:
                obj = self._model_class()
                setattr(obj, req_field, val.strip())
                s.add(obj)
                s.flush()
                new_id = obj.id
            self._refresh_table()
            self._current_id = new_id
            self._highlight_row(new_id)
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _save(self):
        if self._current_id is None:
            QMessageBox.information(self, "Выбор",
                                    "Выберите запись для редактирования.")
            return
        saved_id = self._current_id
        try:
            with self.db_manager.get_session() as s:
                obj = s.query(self._model_class).get(saved_id)
                if not obj:
                    return
                for fdef in self._cfg['fields']:
                    w = self._widgets[fdef['name']]
                    val = self._widget_value(w, fdef)
                    setattr(obj, fdef['name'], val)
            self._refresh_table()
            self._highlight_row(saved_id)
            self._current_id = saved_id
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось сохранить:\n{e}")

    def _delete(self):
        if self._current_id is None:
            return
        reply = QMessageBox.question(
            self, "Удаление",
            "Удалить выбранную запись?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            with self.db_manager.get_session() as s:
                obj = s.query(self._model_class).get(self._current_id)
                if obj:
                    s.delete(obj)
            self._current_id = None
            self._clear_form()
            self._refresh_table()
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _widget_value(self, w, fdef):
        if isinstance(w, QLineEdit):
            val = w.text().strip()
            return val if val else None
        elif isinstance(w, QDoubleSpinBox):
            v = w.value()
            return v if v != 0 else None
        elif isinstance(w, QSpinBox):
            v = w.value()
            return v if v != 0 else None
        elif isinstance(w, QComboBox):
            t = w.currentText()
            return t if t else None
        elif isinstance(w, QTextEdit):
            t = w.toPlainText().strip()
            return t if t else None
        return None

    def _highlight_row(self, obj_id):
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == obj_id:
                self._table.selectRow(i)
                return
