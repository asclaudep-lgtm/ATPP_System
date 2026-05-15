"""
Аналитические отчёты:
- Загрузка оборудования (часы / годовая программа)
- Расход материалов (на годовую программу)
- Себестоимость по цехам
- Сравнение вариантов исполнения

Все три отчёта строятся одним SQL и могут быть выгружены в xlsx.
"""
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QSpinBox, QFileDialog,
    QMessageBox, QHeaderView, QAbstractItemView,
)

from sqlalchemy import func

from database.models import (
    TechProcess, Operation, Equipment, Profession, MaterialNorm, Material,
    Product,
)
from config import EXPORT_DIR


class AnalyticsWidget(QWidget):

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._build_ui()
        self.reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        top = QHBoxLayout()
        top.addWidget(QLabel('<b>Аналитические отчёты</b>'))
        top.addStretch()
        top.addWidget(QLabel('Годовая программа (шт):'))
        self.qty_in = QSpinBox()
        self.qty_in.setRange(1, 1000000)
        self.qty_in.setValue(100)
        self.qty_in.valueChanged.connect(self.reload)
        top.addWidget(self.qty_in)

        export_btn = QPushButton('💾 Экспорт текущей вкладки в Excel…')
        export_btn.clicked.connect(self._export_current)
        top.addWidget(export_btn)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        self._tab_eq = self._mk_table(['Оборудование', 'Модель',
                                       'Опер.', 'Ч/программу, ч',
                                       'Загрузка год, %'])
        self.tabs.addTab(self._tab_eq, 'Загрузка оборудования')

        self._tab_prof = self._mk_table(['Профессия', 'Опер.',
                                         'Ч/программу, ч'])
        self.tabs.addTab(self._tab_prof, 'Загрузка по профессиям')

        self._tab_mat = self._mk_table(['Материал', 'Изделий', 'Норма Σ, кг',
                                        'На программу, кг'])
        self.tabs.addTab(self._tab_mat, 'Расход материалов')

        self._tab_shop = self._mk_table(['Цех', 'Опер.', 'Ч/программу, ч'])
        self.tabs.addTab(self._tab_shop, 'Загрузка по цехам')

        layout.addWidget(self.tabs, 1)

        self._info = QLabel('—')
        layout.addWidget(self._info)

    def _mk_table(self, headers: List[str]) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.horizontalHeader().setStretchLastSection(True)
        t.verticalHeader().setVisible(False)
        return t

    # ─── загрузка данных ───
    def reload(self):
        qty = self.qty_in.value()
        with self.db.get_session() as s:
            self._fill_equipment(s, qty)
            self._fill_professions(s, qty)
            self._fill_materials(s, qty)
            self._fill_shops(s, qty)
        ts = datetime.now().strftime('%H:%M:%S')
        self._info.setText(f'Обновлено: {ts}.  Программа: {qty} шт/год.')

    @staticmethod
    def _hours_per_unit(t_main, t_aux, t_piece) -> float:
        """Возвращаем часы на единицу. Берём Тшт если есть, иначе То+Тв."""
        t = float(t_piece or 0)
        if t == 0:
            t = float(t_main or 0) + float(t_aux or 0)
        return t / 60.0  # min → h

    def _fill_equipment(self, s, qty: int):
        rows = (s.query(
            Equipment.id, Equipment.name, Equipment.model,
            func.count(Operation.id),
            func.sum(func.coalesce(Operation.t_piece, 0)),
            func.sum(func.coalesce(Operation.t_main, 0)),
            func.sum(func.coalesce(Operation.t_auxiliary, 0)),
        ).join(Operation, Operation.equipment_id == Equipment.id)
            .filter((Operation.is_deleted == False) | (Operation.is_deleted.is_(None)))
            .group_by(Equipment.id)
            .order_by(func.count(Operation.id).desc()).all())

        annual_avail = 1900  # часов / год / станок
        self._tab_eq.setRowCount(0)
        for eq_id, name, model, n, t_p, t_m, t_a in rows:
            t_total = float(t_p or 0)
            if t_total == 0:
                t_total = float(t_m or 0) + float(t_a or 0)
            hours_per_qty = (t_total * qty) / 60.0
            load = (hours_per_qty / annual_avail) * 100 if annual_avail else 0
            r = self._tab_eq.rowCount()
            self._tab_eq.insertRow(r)
            self._tab_eq.setItem(r, 0, QTableWidgetItem(name or ''))
            self._tab_eq.setItem(r, 1, QTableWidgetItem(model or ''))
            self._tab_eq.setItem(r, 2, QTableWidgetItem(str(n)))
            self._tab_eq.setItem(r, 3, QTableWidgetItem(f'{hours_per_qty:.1f}'))
            self._tab_eq.setItem(r, 4, QTableWidgetItem(f'{load:.1f}'))
        self._tab_eq.resizeColumnsToContents()

    def _fill_professions(self, s, qty: int):
        rows = (s.query(
            Profession.name,
            func.count(Operation.id),
            func.sum(func.coalesce(Operation.t_piece, 0)),
        ).join(Operation, Operation.profession_id == Profession.id)
            .filter((Operation.is_deleted == False) | (Operation.is_deleted.is_(None)))
            .group_by(Profession.id)
            .order_by(func.count(Operation.id).desc()).all())
        self._tab_prof.setRowCount(0)
        for name, n, t_p in rows:
            hours = (float(t_p or 0) * qty) / 60.0
            r = self._tab_prof.rowCount()
            self._tab_prof.insertRow(r)
            self._tab_prof.setItem(r, 0, QTableWidgetItem(name or ''))
            self._tab_prof.setItem(r, 1, QTableWidgetItem(str(n)))
            self._tab_prof.setItem(r, 2, QTableWidgetItem(f'{hours:.1f}'))
        self._tab_prof.resizeColumnsToContents()

    def _fill_materials(self, s, qty: int):
        rows = (s.query(
            Material.name,
            func.count(MaterialNorm.id),
            func.sum(func.coalesce(MaterialNorm.norm_consumption, 0)),
        ).join(MaterialNorm, MaterialNorm.material_id == Material.id)
            .group_by(Material.id)
            .order_by(func.count(MaterialNorm.id).desc()).all())
        self._tab_mat.setRowCount(0)
        for name, n, total in rows:
            programme = float(total or 0) * qty
            r = self._tab_mat.rowCount()
            self._tab_mat.insertRow(r)
            self._tab_mat.setItem(r, 0, QTableWidgetItem(name or ''))
            self._tab_mat.setItem(r, 1, QTableWidgetItem(str(n)))
            self._tab_mat.setItem(r, 2, QTableWidgetItem(f'{float(total or 0):.3f}'))
            self._tab_mat.setItem(r, 3, QTableWidgetItem(f'{programme:.2f}'))
        self._tab_mat.resizeColumnsToContents()

    def _fill_shops(self, s, qty: int):
        rows = (s.query(
            Operation.shop,
            func.count(Operation.id),
            func.sum(func.coalesce(Operation.t_piece, 0)),
        ).filter((Operation.is_deleted == False) | (Operation.is_deleted.is_(None)),
                 Operation.shop.isnot(None))
            .group_by(Operation.shop)
            .order_by(func.count(Operation.id).desc()).all())
        self._tab_shop.setRowCount(0)
        for shop, n, t_p in rows:
            hours = (float(t_p or 0) * qty) / 60.0
            r = self._tab_shop.rowCount()
            self._tab_shop.insertRow(r)
            self._tab_shop.setItem(r, 0, QTableWidgetItem(shop or ''))
            self._tab_shop.setItem(r, 1, QTableWidgetItem(str(n)))
            self._tab_shop.setItem(r, 2, QTableWidgetItem(f'{hours:.1f}'))
        self._tab_shop.resizeColumnsToContents()

    # ─── экспорт ───
    def _export_current(self):
        try:
            from openpyxl import Workbook
        except ImportError:
            QMessageBox.warning(self, 'Экспорт', 'openpyxl не установлен.')
            return
        idx = self.tabs.currentIndex()
        title = self.tabs.tabText(idx)
        table: QTableWidget = self.tabs.currentWidget()  # type: ignore

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_dir = EXPORT_DIR
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        path_str, _ = QFileDialog.getSaveFileName(
            self, 'Сохранить отчёт',
            str(default_dir / f'Аналитика_{title}_{ts}.xlsx'),
            'Excel files (*.xlsx)'
        )
        if not path_str:
            return
        wb = Workbook()
        ws = wb.active
        ws.title = title[:31]
        # шапка
        headers = [table.horizontalHeaderItem(c).text()
                   for c in range(table.columnCount())]
        ws.append([f'Аналитика: {title}'])
        ws.append([f'Программа: {self.qty_in.value()} шт/год'])
        ws.append([])
        ws.append(headers)
        for r in range(table.rowCount()):
            row = []
            for c in range(table.columnCount()):
                it = table.item(r, c)
                row.append(it.text() if it is not None else '')
            ws.append(row)
        wb.save(path_str)
        QMessageBox.information(self, 'Экспорт', f'Сохранено:\n{path_str}')
