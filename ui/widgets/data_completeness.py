"""
Дашборд полноты данных: показывает по каждому ТП, что заполнено, а что
требует внимания (нормы времени, нормы материала, оборудование, профессии,
автор и т. д.). Помогает технологу-руководителю видеть «что доделать».
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox, QLineEdit,
    QFrame,
)

from database.models import TechProcess, Operation, MaterialNorm, Product


class DataCompletenessWidget(QWidget):
    """Дашборд полноты данных по ТП."""

    # Колонки и их ширины
    _COLUMNS = [
        ('product', 'Обозначение', 200),
        ('name',    'Наименование', 180),
        ('tp',      'ТП',           150),
        ('variant', 'Исп.',          80),
        ('status',  'Статус',        90),
        ('ops',     'Опер.',         55),
        ('time',    'Нормы\nвремени', 80),
        ('equip',   'Оборуд.',       70),
        ('prof',    'Проф.',         70),
        ('mat',     'Нормы\nматер.', 80),
        ('author',  'Автор',         70),
        ('sketches','Эскизы',        70),
        ('score',   'Готовность',   100),
    ]

    # Для сортировки строк — TP, который менее готов, должен идти выше.
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._all_rows: list[dict] = []
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        title = QLabel('Полнота данных по технологическим процессам')
        f = QFont(); f.setBold(True); f.setPointSize(13)
        title.setFont(f)
        lay.addWidget(title)

        sub = QLabel(
            'Показывает, что в каждом ТП заполнено, а что — нет. '
            'Сортируется по проценту готовности (сначала наименее готовые).'
        )
        lay.addWidget(sub)

        # Фильтры
        flt = QHBoxLayout()
        flt.addWidget(QLabel('Статус:'))
        self._cb_status = QComboBox()
        self._cb_status.addItems(['Все', 'DRAFT', 'APPROVED', 'ARCHIVED'])
        self._cb_status.currentIndexChanged.connect(self._apply_filter)
        flt.addWidget(self._cb_status)

        flt.addSpacing(20)
        flt.addWidget(QLabel('Поиск:'))
        self._ed_search = QLineEdit()
        self._ed_search.setPlaceholderText('обозначение, наименование, № ТП…')
        self._ed_search.textChanged.connect(self._apply_filter)
        flt.addWidget(self._ed_search, 1)

        refresh_btn = QPushButton('⟳ Обновить')
        refresh_btn.clicked.connect(self.refresh)
        flt.addWidget(refresh_btn)
        lay.addLayout(flt)

        # Сводка
        self._summary = QLabel('')
        lay.addWidget(self._summary)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(line)

        # Таблица
        self._tbl = QTableWidget()
        self._tbl.setColumnCount(len(self._COLUMNS))
        self._tbl.setHorizontalHeaderLabels([c[1] for c in self._COLUMNS])
        for i, (_, _, w) in enumerate(self._COLUMNS):
            self._tbl.setColumnWidth(i, w)
        self._tbl.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._tbl.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.verticalHeader().setVisible(False)
        self._tbl.setSortingEnabled(True)
        lay.addWidget(self._tbl, 1)

    # ---------------------------------------------------------------- data
    def refresh(self):
        from modules.completeness import score_tp
        rows: list[dict] = []
        with self.db_manager.get_session() as s:
            tps = s.query(TechProcess).all()
            for tp in tps:
                product = tp.product
                ops = list(tp.operations)
                op_count = len(ops)
                with_time = sum(
                    1 for o in ops if (o.t_piece or 0) > 0 or (o.t_setup or 0) > 0
                )
                with_eq = sum(1 for o in ops if o.equipment_id)
                with_prof = sum(1 for o in ops if o.profession_id)
                sketch_count = sum(
                    len(o.sketches or []) + sum(len(t.sketches or []) for t in (o.transitions or []))
                    for o in ops
                )
                mat_norms = list(getattr(tp, 'material_norms', []) or [])
                with_mat = sum(
                    1 for m in mat_norms if (m.norm_per_piece or 0) > 0
                )

                # v8: единая логика подсчёта вынесена в modules.completeness.
                score, _missing = score_tp(tp)

                rows.append({
                    'tp_id': tp.id,
                    'product': product.designation if product else '—',
                    'name': product.name if product else '',
                    'tp': tp.number or f'#{tp.id}',
                    'variant': tp.execution_variant or '',
                    'status': tp.status or 'DRAFT',
                    'ops': op_count,
                    'time': f'{with_time}/{op_count}' if op_count else '—',
                    'equip': f'{with_eq}/{op_count}' if op_count else '—',
                    'prof': f'{with_prof}/{op_count}' if op_count else '—',
                    'mat': f'{with_mat}/{len(mat_norms)}' if mat_norms else '0/0',
                    'author': tp.author.full_name if tp.author else '—',
                    'sketches': str(sketch_count),
                    'score': score,
                    # Доп. флаги для подсветки:
                    '_full_time': op_count > 0 and with_time == op_count,
                    '_full_eq': op_count > 0 and with_eq == op_count,
                    '_full_prof': op_count > 0 and with_prof == op_count,
                    '_has_mat': bool(mat_norms) and with_mat == len(mat_norms),
                    '_has_author': bool(tp.author_id),
                })

        # сортируем по проценту готовности
        rows.sort(key=lambda r: (r['score'], r['product']))
        self._all_rows = rows
        self._apply_filter()

    def _apply_filter(self):
        flt_status = self._cb_status.currentText()
        flt_text = (self._ed_search.text() or '').strip().lower()

        rows = self._all_rows
        if flt_status != 'Все':
            rows = [r for r in rows if (r['status'] or '').upper() == flt_status]
        if flt_text:
            def match(r):
                hay = (r['product'] + ' ' + r['name'] + ' ' + r['tp']
                       + ' ' + (r['variant'] or '') + ' ' + (r['author'] or ''))
                return flt_text in hay.lower()
            rows = [r for r in rows if match(r)]

        self._fill(rows)
        self._update_summary(rows)

    def _fill(self, rows):
        self._tbl.setSortingEnabled(False)
        self._tbl.setRowCount(0)
        for r in rows:
            row = self._tbl.rowCount()
            self._tbl.insertRow(row)
            values = [
                r['product'], r['name'], r['tp'], r['variant'],
                r['status'], r['ops'], r['time'], r['equip'],
                r['prof'], r['mat'], r['author'], r['sketches'],
                f"{r['score']}%",
            ]
            for col, val in enumerate(values):
                it = QTableWidgetItem(str(val))
                it.setData(Qt.ItemDataRole.UserRole, r['tp_id'])
                if col >= 5:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._tbl.setItem(row, col, it)

            # Подсветка проблемных полей
            def color_cell(c, ok):
                cell = self._tbl.item(row, c)
                if cell is None:
                    return
                cell.setForeground(QColor('#27ae60' if ok else '#c0392b'))

            color_cell(6, r['_full_time'])
            color_cell(7, r['_full_eq'])
            color_cell(8, r['_full_prof'])
            color_cell(9, r['_has_mat'])
            color_cell(10, r['_has_author'])

            # Подсветка score
            score = r['score']
            score_item = self._tbl.item(row, 12)
            if score_item:
                if score >= 90:
                    score_item.setForeground(QColor('#27ae60'))
                elif score >= 60:
                    score_item.setForeground(QColor('#d35400'))
                else:
                    score_item.setForeground(QColor('#c0392b'))
                fnt = QFont(); fnt.setBold(True)
                score_item.setFont(fnt)
        self._tbl.setSortingEnabled(True)

    def _update_summary(self, rows):
        if not rows:
            self._summary.setText('Нет данных под фильтр.')
            return
        n = len(rows)
        avg = sum(r['score'] for r in rows) / n
        full = sum(1 for r in rows if r['score'] == 100)
        empty_authors = sum(1 for r in rows if not r['_has_author'])
        empty_time = sum(1 for r in rows if not r['_full_time'])
        empty_mat = sum(1 for r in rows if not r['_has_mat'])
        self._summary.setText(
            f'ТП в выборке: <b>{n}</b>   |   '
            f'Средняя готовность: <b>{avg:.0f}%</b>   |   '
            f'Полностью заполнены: <b>{full}</b>   |   '
            f'Без автора: <b>{empty_authors}</b>   |   '
            f'Без норм времени: <b>{empty_time}</b>   |   '
            f'Без норм материала: <b>{empty_mat}</b>'
        )
