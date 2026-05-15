"""
Диалог библиотеки типовых операций (OperationTemplate).

Два режима:
- pick_mode=False (Сервис → Библиотека): просто CRUD.
- pick_mode=True (вызов из OperationDialog): выбор + accept().
"""
from typing import Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QFormLayout, QComboBox, QDoubleSpinBox,
    QSpinBox, QTextEdit, QMessageBox, QHeaderView, QAbstractItemView,
    QDialogButtonBox,
)

from database.models import (
    OperationTemplate, Equipment, Profession, Operation, TechnologyType
)
from sqlalchemy import func


class OpTemplatesDialog(QDialog):

    def __init__(self, db_manager, *, pick_mode: bool = False, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.pick_mode = pick_mode
        self.selected_template: Optional[Dict] = None

        self.setWindowTitle('Библиотека типовых операций')
        self.resize(960, 520)
        self._build_ui()
        self._reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Поиск
        top = QHBoxLayout()
        top.addWidget(QLabel('Поиск:'))
        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText('часть названия / кода…')
        self.search_in.textChanged.connect(self._reload)
        top.addWidget(self.search_in, 1)

        suggest_btn = QPushButton('🪄 Предложить из истории')
        suggest_btn.setToolTip(
            'Сканирует существующие операции и предлагает шаблоны\n'
            'для самых частых названий, которые ещё не в библиотеке.'
        )
        suggest_btn.clicked.connect(self._suggest_from_history)
        top.addWidget(suggest_btn)
        layout.addLayout(top)

        # Таблица
        self.tbl = QTableWidget(0, 7, self)
        self.tbl.setHorizontalHeaderLabels(
            ['ID', 'Код', 'Название', 'Цех', 'Оборудование',
             'Профессия / разряд', 'Использований']
        )
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setStretchLastSection(False)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tbl, 1)

        # Кнопки
        btn_row = QHBoxLayout()
        if not self.pick_mode:
            add_btn = QPushButton('+ Добавить')
            add_btn.clicked.connect(self._add)
            btn_row.addWidget(add_btn)
            ed_btn = QPushButton('✏ Редактировать')
            ed_btn.clicked.connect(self._edit)
            btn_row.addWidget(ed_btn)
            del_btn = QPushButton('🗑 Удалить')
            del_btn.clicked.connect(self._delete)
            btn_row.addWidget(del_btn)
        btn_row.addStretch()
        if self.pick_mode:
            ok_btn = QPushButton('Использовать')
            ok_btn.setDefault(True)
            ok_btn.clicked.connect(self._on_accept)
            btn_row.addWidget(ok_btn)
        cancel_btn = QPushButton('Закрыть' if not self.pick_mode else 'Отмена')
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _reload(self):
        flt = self.search_in.text().strip().lower()
        with self.db.get_session() as s:
            q = s.query(OperationTemplate)
            if flt:
                like = f'%{flt}%'
                q = q.filter(
                    (OperationTemplate.name.ilike(like)) |
                    (OperationTemplate.code.ilike(like))
                )
            templates = q.order_by(OperationTemplate.usage_count.desc(),
                                   OperationTemplate.name).all()
            self.tbl.setRowCount(0)
            for t in templates:
                row = self.tbl.rowCount()
                self.tbl.insertRow(row)
                self.tbl.setItem(row, 0, QTableWidgetItem(str(t.id)))
                self.tbl.setItem(row, 1, QTableWidgetItem(t.code or ''))
                self.tbl.setItem(row, 2, QTableWidgetItem(t.name or ''))
                self.tbl.setItem(row, 3, QTableWidgetItem(t.shop or ''))
                eq = t.equipment.name if t.equipment else ''
                self.tbl.setItem(row, 4, QTableWidgetItem(eq))
                pr = t.profession.name if t.profession else ''
                grade = f' / {t.grade}р' if t.grade else ''
                self.tbl.setItem(row, 5, QTableWidgetItem(pr + grade))
                self.tbl.setItem(row, 6, QTableWidgetItem(str(t.usage_count or 0)))
        self.tbl.resizeColumnsToContents()

    def _selected_id(self) -> Optional[int]:
        row = self.tbl.currentRow()
        if row < 0:
            return None
        try:
            return int(self.tbl.item(row, 0).text())
        except Exception:
            return None

    def _on_double_click(self, *_):
        if self.pick_mode:
            self._on_accept()
        else:
            self._edit()

    def _on_accept(self):
        tid = self._selected_id()
        if tid is None:
            QMessageBox.information(self, 'Шаблон', 'Выберите шаблон.')
            return
        with self.db.get_session() as s:
            t = s.get(OperationTemplate, tid)
            if t is None:
                return
            self.selected_template = {
                'id': t.id,
                'code': t.code,
                'name': t.name,
                'shop': t.shop,
                'typical_equipment_id': t.typical_equipment_id,
                'typical_profession_id': t.typical_profession_id,
                'grade': t.grade,
                't_setup': t.t_setup,
                't_piece': t.t_piece,
                'description': t.description,
            }
            t.usage_count = (t.usage_count or 0) + 1
        self.accept()

    def _add(self):
        dlg = _OpTemplateEditDialog(self.db, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._reload()

    def _edit(self):
        tid = self._selected_id()
        if tid is None:
            return
        dlg = _OpTemplateEditDialog(self.db, template_id=tid, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._reload()

    def _delete(self):
        tid = self._selected_id()
        if tid is None:
            return
        if QMessageBox.question(self, 'Удаление',
                                'Удалить шаблон?') != QMessageBox.StandardButton.Yes:
            return
        with self.db.get_session() as s:
            t = s.get(OperationTemplate, tid)
            if t:
                s.delete(t)
        self._reload()

    def _suggest_from_history(self):
        """Самые частые названия операций из реальных данных,
        которых ещё нет в шаблонах. Создаём для них черновики.
        """
        with self.db.get_session() as s:
            existing = {
                (t.name or '').lower()
                for t in s.query(OperationTemplate).all()
            }
            rows = (s.query(Operation.name,
                            func.count(Operation.id).label('cnt'),
                            func.max(Operation.code).label('code'),
                            func.max(Operation.shop).label('shop'))
                    .filter(Operation.name.isnot(None),
                            (Operation.is_deleted == False) | (Operation.is_deleted.is_(None)))
                    .group_by(Operation.name)
                    .having(func.count(Operation.id) >= 5)
                    .order_by(func.count(Operation.id).desc())
                    .limit(50)
                    .all())
            created = 0
            for name, cnt, code, shop in rows:
                if not name or name.lower() in existing:
                    continue
                t = OperationTemplate(
                    name=name,
                    code=code,
                    shop=shop,
                    description=f'Авто-создан из {cnt} существующих операций',
                )
                s.add(t)
                created += 1
        QMessageBox.information(
            self, 'Шаблоны',
            f'Добавлено новых шаблонов: {created}\n\n'
            f'Открыли «Редактировать» — задайте оборудование, профессию,\n'
            f'нормы времени, и шаблон будет готов к использованию.'
        )
        self._reload()


class _OpTemplateEditDialog(QDialog):
    """Простая форма редактирования одного шаблона."""

    def __init__(self, db_manager, template_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.template_id = template_id
        self.setWindowTitle('Шаблон операции')
        self.resize(520, 480)
        self._build_ui()
        if template_id is not None:
            self._load(template_id)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_in = QLineEdit()
        form.addRow('Название *', self.name_in)
        self.code_in = QLineEdit()
        self.code_in.setPlaceholderText('4110, 0200…')
        form.addRow('Код', self.code_in)
        self.shop_in = QLineEdit()
        form.addRow('Цех / участок', self.shop_in)

        self.tech_cb = QComboBox()
        self.tech_cb.addItem('— не задан —', None)
        for tt in TechnologyType:
            self.tech_cb.addItem(tt.value, tt.name)
        form.addRow('Тип технологии', self.tech_cb)

        self.eq_cb = QComboBox()
        self.eq_cb.addItem('—', None)
        with self.db.get_session() as s:
            for e in s.query(Equipment).order_by(Equipment.name).all():
                self.eq_cb.addItem(f'{e.name}' + (f' [{e.model}]' if e.model else ''), e.id)
            self._profs = s.query(Profession).order_by(Profession.name).all()
            self.pr_cb = QComboBox()
            self.pr_cb.addItem('—', None)
            for p in self._profs:
                self.pr_cb.addItem(p.name, p.id)
        form.addRow('Типовое оборудование', self.eq_cb)
        form.addRow('Типовая профессия', self.pr_cb)

        self.grade_in = QSpinBox()
        self.grade_in.setRange(0, 8)
        form.addRow('Разряд', self.grade_in)

        self.tpz_in = QDoubleSpinBox()
        self.tpz_in.setRange(0, 9999)
        self.tpz_in.setSuffix(' мин')
        form.addRow('Тпз (типовое)', self.tpz_in)
        self.tsht_in = QDoubleSpinBox()
        self.tsht_in.setRange(0, 9999)
        self.tsht_in.setSuffix(' мин')
        form.addRow('Тшт (типовое)', self.tsht_in)

        self.desc_in = QTextEdit()
        self.desc_in.setMaximumHeight(120)
        form.addRow('Описание', self.desc_in)

        layout.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._on_save)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _load(self, tid: int):
        with self.db.get_session() as s:
            t = s.get(OperationTemplate, tid)
            if t is None:
                return
            self.name_in.setText(t.name or '')
            self.code_in.setText(t.code or '')
            self.shop_in.setText(t.shop or '')
            if t.technology_type is not None:
                for i in range(self.tech_cb.count()):
                    if self.tech_cb.itemData(i) == t.technology_type.name:
                        self.tech_cb.setCurrentIndex(i)
                        break
            if t.typical_equipment_id:
                for i in range(self.eq_cb.count()):
                    if self.eq_cb.itemData(i) == t.typical_equipment_id:
                        self.eq_cb.setCurrentIndex(i)
                        break
            if t.typical_profession_id:
                for i in range(self.pr_cb.count()):
                    if self.pr_cb.itemData(i) == t.typical_profession_id:
                        self.pr_cb.setCurrentIndex(i)
                        break
            self.grade_in.setValue(int(t.grade or 0))
            self.tpz_in.setValue(float(t.t_setup or 0))
            self.tsht_in.setValue(float(t.t_piece or 0))
            self.desc_in.setPlainText(t.description or '')

    def _on_save(self):
        name = self.name_in.text().strip()
        if not name:
            QMessageBox.warning(self, 'Шаблон', 'Название обязательно.')
            return
        with self.db.get_session() as s:
            if self.template_id is None:
                t = OperationTemplate(name=name)
                s.add(t)
                s.flush()
                self.template_id = t.id
            else:
                t = s.get(OperationTemplate, self.template_id)
                if t is None:
                    return
            t.name = name
            t.code = self.code_in.text().strip() or None
            t.shop = self.shop_in.text().strip() or None
            tt = self.tech_cb.currentData()
            t.technology_type = TechnologyType[tt] if tt else None
            t.typical_equipment_id = self.eq_cb.currentData()
            t.typical_profession_id = self.pr_cb.currentData()
            t.grade = self.grade_in.value() or None
            t.t_setup = self.tpz_in.value() or None
            t.t_piece = self.tsht_in.value() or None
            t.description = self.desc_in.toPlainText().strip() or None
        self.accept()
