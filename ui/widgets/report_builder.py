"""Custom report builder — select fields, filter, group, export."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QListWidget, QListWidgetItem,
    QGroupBox, QMessageBox, QFileDialog, QCheckBox, QLineEdit,
    QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

import openpyxl
from openpyxl.styles import Font as XlFont, Alignment as XlAlign
from config import EXPORT_DIR


# ——— Report definitions ——————————————————————————————————————————

REPORT_DEFS = {
    'products': {
        'title': 'Изделия',
        'model': 'Product',
        'fields': {
            'designation': 'Обозначение',
            'name': 'Наименование',
            'mass': 'Масса, кг',
            'dimensions': 'Габариты',
            'blank_type': 'Вид заготовки',
            'accuracy_class': 'Класс точности',
            'roughness': 'Шероховатость',
        },
        'search_field': 'designation',
    },
    'tech_processes': {
        'title': 'Техпроцессы',
        'model': 'TechProcess',
        'fields': {
            'number': 'Номер ТП',
            'version': 'Версия',
            'status': 'Статус',
            'technology_type': 'Вид технологии',
            'execution_variant': 'Вариант исполнения',
            'description': 'Описание',
        },
        'search_field': 'number',
    },
    'work_orders': {
        'title': 'Наряды',
        'model': 'WorkOrder',
        'fields': {
            'number': 'Номер наряда',
            'status': 'Статус',
            'qty_total': 'Кол-во всего',
            'qty_done': 'Выполнено',
            'qty_scrap': 'Брак',
            'due_date': 'Срок',
            'created_at': 'Создан',
        },
        'search_field': 'number',
    },
    'materials': {
        'title': 'Материалы',
        'model': 'Material',
        'fields': {
            'name': 'Наименование',
            'grade': 'Марка',
            'gost': 'ГОСТ',
            'density': 'Плотность',
            'price_per_kg': 'Цена/кг',
        },
        'search_field': 'name',
    },
}


class ReportBuilderWidget(QWidget):
    """Report builder — selects report type, fields, and exports to Excel."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        title = QLabel('Конструктор отчётов')
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        # Type selector
        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel('Тип отчёта:'))
        self._type_combo = QComboBox()
        for key, defn in REPORT_DEFS.items():
            self._type_combo.addItem(defn['title'], key)
        self._type_combo.currentIndexChanged.connect(self._on_type_change)
        sel_row.addWidget(self._type_combo)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: field selector
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        fields_grp = QGroupBox('Поля')
        fl = QVBoxLayout(fields_grp)
        self._field_list = QListWidget()
        fl.addWidget(self._field_list)
        ll.addWidget(fields_grp)

        # Filter
        filter_grp = QGroupBox('Фильтр')
        filt_lay = QVBoxLayout(filter_grp)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText('Поиск...')
        self._search_edit.textChanged.connect(self._refresh_table)
        filt_lay.addWidget(self._search_edit)
        ll.addWidget(filter_grp)

        # Buttons
        btn_row = QHBoxLayout()
        run_btn = QPushButton('▶ Выполнить')
        run_btn.clicked.connect(self._refresh_table)
        btn_row.addWidget(run_btn)

        select_all_btn = QPushButton('Все поля')
        select_all_btn.clicked.connect(self._select_all_fields)
        btn_row.addWidget(select_all_btn)

        export_btn = QPushButton('📄 Экспорт Excel')
        export_btn.setStyleSheet(
            'QPushButton { background-color: #27ae60; color: white; '
            'border: none; padding: 6px 12px; border-radius: 4px; }')
        export_btn.clicked.connect(self._export_excel)
        btn_row.addWidget(export_btn)
        ll.addLayout(btn_row)
        splitter.addWidget(left)

        # Right: preview table
        self._table = QTableWidget(0, 1)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self._table)

        splitter.setSizes([260, 600])
        layout.addWidget(splitter, stretch=1)

        self._on_type_change()

    def _on_type_change(self):
        key = self._type_combo.currentData()
        defn = REPORT_DEFS[key]
        self._field_list.clear()
        for fkey, flabel in defn['fields'].items():
            item = QListWidgetItem(flabel)
            item.setData(Qt.ItemDataRole.UserRole, fkey)
            item.setCheckState(Qt.CheckState.Checked)
            self._field_list.addItem(item)

    def _select_all_fields(self):
        for i in range(self._field_list.count()):
            self._field_list.item(i).setCheckState(Qt.CheckState.Checked)

    def _checked_fields(self):
        cols = []
        for i in range(self._field_list.count()):
            item = self._field_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                cols.append((item.data(Qt.ItemDataRole.UserRole), item.text()))
        return cols

    def _refresh_table(self):
        key = self._type_combo.currentData()
        defn = REPORT_DEFS[key]
        model_name = defn['model']
        search = self._search_edit.text().strip()
        cols = self._checked_fields()

        import importlib
        models = importlib.import_module('database.models')
        model_cls = getattr(models, model_name)

        with self.db_manager.get_session() as s:
            q = s.query(model_cls)
            if hasattr(model_cls, 'is_deleted'):
                q = q.filter(model_cls.is_deleted == False)
            if search and defn.get('search_field'):
                sf = getattr(model_cls, defn['search_field'], None)
                if sf:
                    q = q.filter(sf.ilike(f'%{search}%'))
            rows = q.limit(200).all()

        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels([c[1] for c in cols])
        self._table.setRowCount(len(rows))
        for i, obj in enumerate(rows):
            for j, (fkey, _) in enumerate(cols):
                val = getattr(obj, fkey, None)
                if val is not None:
                    if hasattr(val, 'value'):
                        val = val.value
                    elif hasattr(val, 'strftime'):
                        val = val.strftime('%Y-%m-%d')
                    val = str(val)
                else:
                    val = ''
                self._table.setItem(i, j, QTableWidgetItem(val))
        self._table.resizeColumnsToContents()

    def _export_excel(self):
        if self._table.rowCount() == 0:
            QMessageBox.information(self, 'Экспорт', 'Нет данных для экспорта.')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Сохранить отчёт', str(EXPORT_DIR / 'report.xlsx'),
            'Excel (*.xlsx)')
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = REPORT_DEFS[self._type_combo.currentData()]['title'][:31]

        headers = [self._table.horizontalHeaderItem(c).text()
                   for c in range(self._table.columnCount())]
        for j, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=j, value=h)
            cell.font = XlFont(bold=True)
            cell.alignment = XlAlign(horizontal='center')

        for i in range(self._table.rowCount()):
            for j in range(self._table.columnCount()):
                item = self._table.item(i, j)
                ws.cell(row=i + 2, column=j + 1, value=item.text() if item else '')

        wb.save(path)
        QMessageBox.information(self, 'Экспорт', f'Сохранено:\n{path}')
