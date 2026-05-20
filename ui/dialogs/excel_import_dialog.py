"""
Импорт справочников из Excel: Оборудование / Профессии / Материалы.

Формат входа: первая строка — шапка с любыми названиями колонок,
пользователь маппит «колонка → поле БД». Идемпотентно: дубли по
ключевому полю (model для Equipment, name для Profession,
brand+gost для Material) не создаются.
"""
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database.models import Equipment, Material, Profession

ENTITY_OPTIONS = {
    'equipment': {
        'title': 'Оборудование (Equipment)',
        'fields': [('name', 'Наименование *'),
                   ('model', 'Модель / Шифр'),
                   ('description', 'Описание')],
        'required': ['name'],
    },
    'profession': {
        'title': 'Профессии (Profession)',
        'fields': [('name', 'Наименование *'),
                   ('typical_grade', 'Типовой разряд (1-6)')],
        'required': ['name'],
    },
    'material': {
        'title': 'Материалы (Material)',
        'fields': [('name', 'Наименование *'),
                   ('grade', 'Марка'),
                   ('gost', 'ГОСТ / ТУ'),
                   ('density', 'Плотность, кг/м³'),
                   ('price_per_kg', 'Цена за кг'),
                   ('description', 'Описание')],
        'required': ['name'],
    },
}


class ExcelImportDialog(QDialog):

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.path: Optional[Path] = None
        self._headers: List[str] = []
        self._rows: List[List] = []
        self.setWindowTitle('Импорт справочников из Excel')
        self.resize(820, 520)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 1. Тип
        top = QHBoxLayout()
        top.addWidget(QLabel('Импортировать в:'))
        self.entity_cb = QComboBox()
        for k, v in ENTITY_OPTIONS.items():
            self.entity_cb.addItem(v['title'], k)
        self.entity_cb.currentIndexChanged.connect(self._rebuild_mapping)
        top.addWidget(self.entity_cb, 1)
        b = QPushButton('📂 Выбрать файл Excel…')
        b.clicked.connect(self._choose_file)
        top.addWidget(b)
        layout.addLayout(top)

        self.file_lbl = QLabel('Файл не выбран')
        layout.addWidget(self.file_lbl)

        # 2. Маппинг колонок
        layout.addWidget(QLabel('<b>Сопоставление колонок:</b>'))
        self.mapping_form = QFormLayout()
        layout.addLayout(self.mapping_form)
        self._mapping_cbs: Dict[str, QComboBox] = {}

        # 3. Превью
        self.preview = QTableWidget(0, 0)
        self.preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.preview, 1)

        # 4. Кнопки
        btn = QHBoxLayout()
        btn.addStretch()
        self.import_btn = QPushButton('📥 Импортировать')
        self.import_btn.setDefault(True)
        self.import_btn.clicked.connect(self._do_import)
        self.import_btn.setEnabled(False)
        btn.addWidget(self.import_btn)
        cb = QPushButton('Закрыть')
        cb.clicked.connect(self.reject)
        btn.addWidget(cb)
        layout.addLayout(btn)

        self._rebuild_mapping()

    def _rebuild_mapping(self):
        # Очищаем форму
        while self.mapping_form.rowCount():
            self.mapping_form.removeRow(0)
        self._mapping_cbs.clear()
        ent = self.entity_cb.currentData()
        opts = ENTITY_OPTIONS[ent]
        for fld, label in opts['fields']:
            cb = QComboBox()
            cb.addItem('— не использовать —', None)
            for h in self._headers:
                cb.addItem(h, h)
            # auto-pick по совпадению имени
            for i in range(cb.count()):
                hdr = cb.itemData(i) or ''
                if hdr and (hdr.lower() == fld.lower()
                            or fld.lower() in hdr.lower()):
                    cb.setCurrentIndex(i)
                    break
            self.mapping_form.addRow(QLabel(label), cb)
            self._mapping_cbs[fld] = cb

    def _choose_file(self):
        path_str, _ = QFileDialog.getOpenFileName(
            self, 'Выберите Excel-файл', '',
            'Excel files (*.xlsx *.xlsm)'
        )
        if not path_str:
            return
        self.path = Path(path_str)
        self.file_lbl.setText(f'Файл: {self.path.name}')
        self._load_workbook()
        self._rebuild_mapping()
        self._fill_preview()
        self.import_btn.setEnabled(bool(self._rows))

    def _load_workbook(self):
        try:
            from openpyxl import load_workbook
        except ImportError:
            QMessageBox.warning(self, 'Импорт', 'Не установлен openpyxl.')
            return
        try:
            wb = load_workbook(filename=str(self.path), data_only=True)
            ws = wb.active
            it = ws.iter_rows(values_only=True)
            self._headers = [str(x or '').strip() for x in next(it)]
            self._rows = []
            for r in it:
                if all(c is None or str(c).strip() == '' for c in r):
                    continue
                self._rows.append(list(r))
        except Exception as e:
            QMessageBox.critical(self, 'Импорт', f'Ошибка чтения: {e}')
            self._headers = []
            self._rows = []

    def _fill_preview(self):
        self.preview.setRowCount(0)
        self.preview.setColumnCount(len(self._headers))
        self.preview.setHorizontalHeaderLabels(self._headers)
        for row in self._rows[:30]:
            r = self.preview.rowCount()
            self.preview.insertRow(r)
            for c, val in enumerate(row):
                self.preview.setItem(r, c, QTableWidgetItem(
                    '' if val is None else str(val)
                ))
        self.preview.resizeColumnsToContents()

    def _do_import(self):
        ent = self.entity_cb.currentData()
        opts = ENTITY_OPTIONS[ent]
        # маппинг fld -> column index
        col_index_by_field = {}
        for fld, cb in self._mapping_cbs.items():
            hdr = cb.currentData()
            if not hdr:
                continue
            try:
                col_index_by_field[fld] = self._headers.index(hdr)
            except ValueError:
                continue

        for req in opts['required']:
            if req not in col_index_by_field:
                QMessageBox.warning(
                    self, 'Импорт',
                    f'Не сопоставлено обязательное поле: {req}'
                )
                return

        added, skipped = 0, 0
        with self.db.get_session() as s:
            for row in self._rows:
                vals = {}
                for fld, idx in col_index_by_field.items():
                    if idx < len(row):
                        v = row[idx]
                        vals[fld] = (str(v).strip() if v is not None else None)
                # required check
                if any(not vals.get(req) for req in opts['required']):
                    skipped += 1
                    continue
                if ent == 'equipment':
                    key = vals.get('model') or vals.get('name')
                    exists = (s.query(Equipment)
                              .filter((Equipment.model == key) |
                                      (Equipment.name == key))
                              .first())
                    if exists:
                        skipped += 1
                        continue
                    s.add(Equipment(**{k: v for k, v in vals.items()
                                       if k in {'name', 'model', 'description'}}))
                    added += 1
                elif ent == 'profession':
                    name = vals.get('name')
                    exists = s.query(Profession).filter_by(name=name).first()
                    if exists:
                        skipped += 1
                        continue
                    grade = None
                    if vals.get('typical_grade'):
                        try:
                            grade = int(float(vals['typical_grade']))
                        except Exception:
                            grade = None
                    s.add(Profession(name=name, typical_grade=grade))
                    added += 1
                elif ent == 'material':
                    name = vals.get('name')
                    grade = vals.get('grade')
                    gost = vals.get('gost')
                    exists = (s.query(Material)
                              .filter_by(name=name, gost=gost)
                              .first())
                    if exists:
                        skipped += 1
                        continue
                    density = None
                    if vals.get('density'):
                        try:
                            density = float(str(vals['density']).replace(',', '.'))
                        except Exception:
                            density = None
                    price = None
                    if vals.get('price_per_kg'):
                        try:
                            price = float(str(vals['price_per_kg']).replace(',', '.'))
                        except Exception:
                            price = None
                    s.add(Material(
                        name=name,
                        grade=grade,
                        gost=gost,
                        density=density,
                        price_per_kg=price,
                        description=vals.get('description'),
                    ))
                    added += 1
        QMessageBox.information(
            self, 'Импорт',
            f'Добавлено: {added}\nПропущено (дубли / пустые): {skipped}'
        )
