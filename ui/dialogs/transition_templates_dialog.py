"""
v8: Библиотека шаблонов переходов.

Хранится в таблице `transition_templates` (модель ``TransitionTemplate``).

Два режима использования:
 - ``pick_mode=False`` (Сервис → Шаблоны переходов): полный CRUD.
 - ``pick_mode=True`` (вызов из TransitionDialog): двойной клик /
   кнопка «Выбрать» возвращает выбранный шаблон через
   ``self.selected_template``.

Дополнительно: при первом открытии БД без записей пополняем библиотеку
дефолтным стартовым набором типовых формулировок.
"""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

_logger = logging.getLogger(__name__)

from database.models import TransitionTemplate

# Стартовый набор формулировок — добавляется при первом открытии БД без
# записей. Технолог потом может править и пополнять.
_SEED_TEMPLATES = [
    ('001', 'Установить и закрепить заготовку.'),
    ('002', 'Точить наружный диаметр Ø__ на длину __ мм.'),
    ('003', 'Подрезать торец в размер.'),
    ('004', 'Точить канавку шириной __ мм глубиной __ мм.'),
    ('005', 'Сверлить отверстие Ø__ на глубину __ мм.'),
    ('006', 'Зенковать фаску __×__ мм.'),
    ('007', 'Нарезать резьбу М__ на длину __ мм.'),
    ('008', 'Притупить острые кромки.'),
    ('009', 'Снять заусенцы.'),
    ('010', 'Промыть деталь.'),
    ('011', 'Проконтролировать размер __  __  __.'),
    ('012', 'Маркировать клеймом __.'),
    ('013', 'Передать на следующую операцию.'),
    ('014', 'Фрезеровать поверхность в размер __ мм.'),
    ('015', 'Шлифовать поверхность до Ra __ мкм.'),
    ('016', 'Зачистить заусенцы напильником.'),
    ('017', 'Установить деталь в патрон, выверить по индикатору.'),
    ('018', 'Снять деталь со станка, уложить в тару.'),
]


def _seed_if_empty(db_manager):
    """Если библиотека шаблонов переходов пуста — заполнить дефолтами."""
    with db_manager.get_session() as s:
        cnt = s.query(TransitionTemplate).count()
        if cnt > 0:
            return
        for i, (code, text) in enumerate(_SEED_TEMPLATES):
            s.add(TransitionTemplate(code=code, text=text, sort_order=i))


class TransitionTemplatesDialog(QDialog):
    """Библиотека шаблонов переходов."""

    def __init__(self, db_manager, *, pick_mode: bool = False, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.pick_mode = pick_mode
        self.selected_template: Optional[dict] = None

        self.setWindowTitle('Библиотека шаблонов переходов')
        self.resize(760, 520)

        try:
            _seed_if_empty(self.db)
        except Exception:
            _logger.exception("Unhandled error")

        self._build_ui()
        self._reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel(
            '<b>Шаблоны переходов</b> — двойной клик '
            'или «Выбрать» вставит в текст перехода.'
            if self.pick_mode else
            '<b>Шаблоны переходов</b> — стандартные формулировки.'
        ))
        top.addStretch()
        layout.addLayout(top)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel('Поиск:'))
        self.q_in = QLineEdit()
        self.q_in.setPlaceholderText(
            'часть текста: "точить", "снять заусенцы"…'
        )
        self.q_in.textChanged.connect(self._reload)
        search_row.addWidget(self.q_in, 1)
        layout.addLayout(search_row)

        self.tbl = QTableWidget(0, 3, self)
        self.tbl.setHorizontalHeaderLabels(['ID', 'Код', 'Текст перехода'])
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setStretchLastSection(False)
        self.tbl.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.tbl.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tbl, 1)

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
            pick_btn = QPushButton('✅ Выбрать')
            pick_btn.setDefault(True)
            pick_btn.clicked.connect(self._pick)
            btn_row.addWidget(pick_btn)
            cancel_btn = QPushButton('Отмена')
            cancel_btn.clicked.connect(self.reject)
            btn_row.addWidget(cancel_btn)
        else:
            close_btn = QPushButton('Закрыть')
            close_btn.clicked.connect(self.accept)
            btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _reload(self):
        q = (self.q_in.text() or '').strip()
        with self.db.get_session() as s:
            qry = s.query(TransitionTemplate)
            if q:
                like = f'%{q}%'
                qry = qry.filter(
                    TransitionTemplate.text.ilike(like)
                    | TransitionTemplate.code.ilike(like)
                )
            rows = qry.order_by(
                TransitionTemplate.sort_order, TransitionTemplate.id
            ).all()
            self.tbl.setRowCount(0)
            for r in rows:
                row = self.tbl.rowCount()
                self.tbl.insertRow(row)
                self.tbl.setItem(row, 0, QTableWidgetItem(str(r.id)))
                self.tbl.setItem(row, 1, QTableWidgetItem(r.code or ''))
                self.tbl.setItem(row, 2, QTableWidgetItem(r.text or ''))

    def _selected_id(self) -> Optional[int]:
        row = self.tbl.currentRow()
        if row < 0:
            return None
        it = self.tbl.item(row, 0)
        try:
            return int(it.text())
        except (ValueError, AttributeError):
            return None

    def _selected_data(self) -> Optional[dict]:
        rid = self._selected_id()
        if rid is None:
            return None
        with self.db.get_session() as s:
            r = s.get(TransitionTemplate, rid)
            if not r:
                return None
            return {'id': r.id, 'code': r.code or '', 'text': r.text or ''}

    def _on_double_click(self, _idx):
        if self.pick_mode:
            self._pick()
        else:
            self._edit()

    def _pick(self):
        data = self._selected_data()
        if data is None:
            QMessageBox.information(self, 'Выбор',
                                    'Выберите строку в таблице.')
            return
        self.selected_template = data
        self.accept()

    def _add(self):
        dlg = _TemplateEditDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        with self.db.get_session() as s:
            new = TransitionTemplate(
                code=dlg.code, text=dlg.text, sort_order=0
            )
            s.add(new)
        self._reload()

    def _edit(self):
        rid = self._selected_id()
        if rid is None:
            QMessageBox.information(self, 'Изменение',
                                    'Выберите строку.')
            return
        with self.db.get_session() as s:
            r = s.get(TransitionTemplate, rid)
            if not r:
                return
            dlg = _TemplateEditDialog(self, code=r.code or '',
                                      text=r.text or '')
            if dlg.exec() == QDialog.DialogCode.Accepted:
                r.code = dlg.code
                r.text = dlg.text
        self._reload()

    def _delete(self):
        rid = self._selected_id()
        if rid is None:
            return
        r = QMessageBox.question(
            self, 'Удалить',
            'Удалить шаблон?\nЭта операция необратима.',
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        with self.db.get_session() as s:
            obj = s.get(TransitionTemplate, rid)
            if obj:
                s.delete(obj)
        self._reload()


class _TemplateEditDialog(QDialog):
    """Маленький диалог редактирования одного шаблона."""

    def __init__(self, parent=None, *, code: str = '', text: str = ''):
        super().__init__(parent)
        self.setWindowTitle('Шаблон перехода')
        self.setMinimumWidth(420)
        self.code = code
        self.text = text

        lay = QVBoxLayout(self)
        f = QFormLayout()
        self._code_in = QLineEdit(code)
        self._code_in.setMaximumWidth(120)
        f.addRow('Код:', self._code_in)
        self._text_in = QTextEdit()
        self._text_in.setPlainText(text)
        self._text_in.setMinimumHeight(120)
        f.addRow('Текст:', self._text_in)
        lay.addLayout(f)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _on_ok(self):
        text = self._text_in.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, 'Текст', 'Текст не может быть пустым.')
            return
        self.code = self._code_in.text().strip()
        self.text = text
        self.accept()
