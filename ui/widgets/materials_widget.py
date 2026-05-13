"""
v9-5 UI: Учёт материала — партии, резервы, списания.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QDialogButtonBox, QLineEdit, QComboBox, QDateEdit,
    QDoubleSpinBox, QMessageBox, QTextEdit, QFileDialog, QTabWidget,
    QInputDialog,
)

from database.models import (
    Material, MaterialBatch, MaterialReservation, MaterialIssue, WorkOrder,
)
from modules import material_trace as mtr


class BatchDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle('Новое поступление материала')
        self.setMinimumWidth(500)
        lay = QFormLayout(self)
        self.mat_cb = QComboBox()
        with self.db.get_session() as s:
            for m in s.query(Material).order_by(Material.name).all():
                title = m.name + (f' / {m.grade}' if m.grade else '')
                self.mat_cb.addItem(title, m.id)
        self.lot = QLineEdit()
        self.qty = QDoubleSpinBox()
        self.qty.setRange(0.01, 1e9)
        self.qty.setDecimals(3)
        self.unit = QLineEdit('кг')
        self.dt = QDateEdit()
        self.dt.setCalendarPopup(True)
        self.dt.setDate(date.today())
        self.supplier = QLineEdit()
        self.cert_path: Optional[str] = None
        self.cert_lbl = QLabel('— не выбран —')
        cert_row = QWidget()
        rl = QHBoxLayout(cert_row)
        rl.setContentsMargins(0, 0, 0, 0)
        b = QPushButton('Файл…')
        b.clicked.connect(self._pick)
        rl.addWidget(self.cert_lbl, 1)
        rl.addWidget(b)
        self.notes = QTextEdit()

        lay.addRow('Материал:', self.mat_cb)
        lay.addRow('№ партии (lot):', self.lot)
        lay.addRow('Количество:', self.qty)
        lay.addRow('Ед.:', self.unit)
        lay.addRow('Дата:', self.dt)
        lay.addRow('Поставщик:', self.supplier)
        lay.addRow('Сертификат (PDF):', cert_row)
        lay.addRow('Примечание:', self.notes)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

    def _pick(self):
        p, _ = QFileDialog.getOpenFileName(
            self, 'Выберите сертификат',
            filter='PDF (*.pdf);;All files (*.*)')
        if p:
            self.cert_path = p
            self.cert_lbl.setText(p.split('/')[-1])

    def _save(self):
        if not self.lot.text().strip():
            QMessageBox.warning(self, 'Партия', '№ партии обязателен.')
            return
        with self.db.get_session() as s:
            try:
                mtr.add_batch(
                    s,
                    material_id=self.mat_cb.currentData(),
                    lot_no=self.lot.text().strip(),
                    qty_received=self.qty.value(),
                    unit=self.unit.text().strip() or 'кг',
                    received_date=self.dt.date().toPyDate(),
                    supplier=self.supplier.text().strip(),
                    cert_src_path=self.cert_path,
                    notes=self.notes.toPlainText(),
                )
                s.commit()
            except Exception as e:
                QMessageBox.warning(self, 'Партия', str(e))
                return
        self.accept()


class MaterialsWidget(QWidget):
    """Учёт материала."""

    def __init__(self, db_manager, current_user_id: int = 0, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.user_id = current_user_id
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        # Партии
        bt = QWidget()
        blay = QVBoxLayout(bt)
        self.b_table = QTableWidget(0, 9)
        self.b_table.setHorizontalHeaderLabels([
            'ID', 'Материал', 'Партия', 'Дата',
            'Получено', 'Зарезерв.', 'Списано', 'Остаток', 'Сертификат'])
        self.b_table.horizontalHeader().setStretchLastSection(True)
        self.b_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.b_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        blay.addWidget(self.b_table)
        bbtns = QHBoxLayout()
        for label, cb in [('+ Поступление…', self._on_receive),
                          ('Резерв под наряд…', self._on_reserve),
                          ('Списать…', self._on_issue),
                          ('⟳ Обновить', self.refresh)]:
            b = QPushButton(label)
            b.clicked.connect(cb)
            bbtns.addWidget(b)
        bbtns.addStretch(1)
        blay.addLayout(bbtns)
        tabs.addTab(bt, 'Партии материала')

        # Списания
        it = QWidget()
        ilay = QVBoxLayout(it)
        self.i_table = QTableWidget(0, 5)
        self.i_table.setHorizontalHeaderLabels(
            ['Партия', 'Наряд', 'Кол-во', 'Когда', 'Примечание'])
        self.i_table.horizontalHeader().setStretchLastSection(True)
        ilay.addWidget(self.i_table)
        tabs.addTab(it, 'Списания')

    def refresh(self):
        with self.db.get_session() as s:
            batches = (s.query(MaterialBatch)
                       .order_by(MaterialBatch.received_date.desc())
                       .all())
            self._fill_batches(batches)
            issues = (s.query(MaterialIssue)
                      .order_by(MaterialIssue.issued_at.desc()).all())
            self._fill_issues(issues)

    def _fill_batches(self, batches):
        self.b_table.setRowCount(len(batches))
        for i, b in enumerate(batches):
            def _i(text, data=None):
                qi = QTableWidgetItem(str(text))
                if data is not None:
                    qi.setData(Qt.ItemDataRole.UserRole, data)
                return qi
            unit = b.unit or 'кг'
            free = mtr.available_qty(b)
            mname = (b.material.name + (' / ' + b.material.grade
                                        if b.material.grade else '')
                     if b.material else '—')
            self.b_table.setItem(i, 0, _i(b.id, b.id))
            self.b_table.setItem(i, 1, _i(mname))
            self.b_table.setItem(i, 2, _i(b.lot_no))
            self.b_table.setItem(i, 3, _i(
                b.received_date.strftime('%d.%m.%Y')
                if b.received_date else ''))
            self.b_table.setItem(i, 4, _i(
                f'{b.qty_received:g} {unit}'))
            self.b_table.setItem(i, 5, _i(
                f'{b.qty_reserved:g} {unit}'))
            self.b_table.setItem(i, 6, _i(
                f'{b.qty_consumed:g} {unit}'))
            self.b_table.setItem(i, 7, _i(f'{free:g} {unit}'))
            self.b_table.setItem(i, 8, _i('✓' if b.cert_path else ''))
        self.b_table.resizeColumnsToContents()

    def _fill_issues(self, issues):
        self.i_table.setRowCount(len(issues))
        for i, x in enumerate(issues):
            def _i(text):
                return QTableWidgetItem(str(text))
            batch = x.batch
            self.i_table.setItem(i, 0, _i(
                f'{batch.material.name if batch and batch.material else ""} / '
                f'{batch.lot_no if batch else ""}'))
            self.i_table.setItem(i, 1, _i(
                x.work_order.number if x.work_order else ''))
            self.i_table.setItem(i, 2, _i(
                f'{x.qty:g} {batch.unit if batch else ""}'))
            self.i_table.setItem(i, 3, _i(
                x.issued_at.strftime('%d.%m.%Y %H:%M')
                if x.issued_at else ''))
            self.i_table.setItem(i, 4, _i(x.notes or ''))
        self.i_table.resizeColumnsToContents()

    def _selected_batch_id(self) -> Optional[int]:
        r = self.b_table.currentRow()
        if r < 0:
            return None
        it = self.b_table.item(r, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _on_receive(self):
        dlg = BatchDialog(self.db, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_reserve(self):
        bid = self._selected_batch_id()
        if bid is None:
            QMessageBox.information(self, 'Резерв', 'Выберите партию.')
            return
        with self.db.get_session() as s:
            wos = (s.query(WorkOrder)
                   .order_by(WorkOrder.created_at.desc()).limit(100).all())
            choices = [f'{w.number}  ({w.qty_total} шт.)' for w in wos]
            ids = [w.id for w in wos]
        if not choices:
            QMessageBox.information(self, 'Резерв', 'Нет открытых нарядов.')
            return
        item, ok = QInputDialog.getItem(
            self, 'Резерв', 'Под наряд:', choices, 0, False)
        if not ok:
            return
        wo_id = ids[choices.index(item)]
        qty, ok = QInputDialog.getDouble(
            self, 'Резерв', 'Количество:', 1.0, 0.001, 1e9, 3)
        if not ok:
            return
        with self.db.get_session() as s:
            try:
                mtr.reserve(s, batch_id=bid, work_order_id=wo_id,
                            qty=qty, reserved_by=self.user_id)
                s.commit()
            except ValueError as e:
                QMessageBox.warning(self, 'Резерв', str(e))
                return
        self.refresh()

    def _on_issue(self):
        bid = self._selected_batch_id()
        if bid is None:
            QMessageBox.information(self, 'Списание', 'Выберите партию.')
            return
        with self.db.get_session() as s:
            wos = (s.query(WorkOrder)
                   .order_by(WorkOrder.created_at.desc()).limit(100).all())
            choices = [f'{w.number}  ({w.qty_total} шт.)' for w in wos]
            ids = [w.id for w in wos]
        item, ok = QInputDialog.getItem(
            self, 'Списание', 'На какой наряд:', choices, 0, False)
        if not ok:
            return
        wo_id = ids[choices.index(item)]
        qty, ok = QInputDialog.getDouble(
            self, 'Списание', 'Количество:', 1.0, 0.001, 1e9, 3)
        if not ok:
            return
        with self.db.get_session() as s:
            try:
                mtr.issue(s, batch_id=bid, work_order_id=wo_id,
                          qty=qty, issued_by=self.user_id)
                s.commit()
            except ValueError as e:
                QMessageBox.warning(self, 'Списание', str(e))
                return
        self.refresh()
