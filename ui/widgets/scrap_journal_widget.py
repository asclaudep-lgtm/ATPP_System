"""
v9-9 UI: Брак-журнал с фотофиксацией + аналитика.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QSpinBox, QComboBox, QTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox, QSplitter, QDialog,
    QDialogButtonBox, QHeaderView, QAbstractItemView, QGroupBox,
)

from database.models import (
    ScrapRecord, ScrapReason, ScrapDecision, WorkOrder, Operation,
    User, ScrapPhoto,
)
from modules import scrap_journal as sj


class ScrapEditDialog(QDialog):
    """Создание / редактирование записи о браке."""

    def __init__(self, db_manager, *, current_user_id: int,
                 record: Optional[ScrapRecord] = None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.current_user_id = current_user_id
        self.record_id = record.id if record else None
        self.setWindowTitle(
            'Редактирование брака' if record else 'Регистрация брака')
        self.setMinimumWidth(600)
        self._build(record)

    def _build(self, record):
        lay = QFormLayout(self)

        self.wo_cb = QComboBox()
        self.op_cb = QComboBox()
        self.reason_cb = QComboBox()
        for r in ScrapReason:
            self.reason_cb.addItem(r.value, r)
        self.qty_sp = QSpinBox()
        self.qty_sp.setRange(1, 99999)
        self.qty_sp.setValue(record.qty_scrap if record else 1)
        self.descr = QTextEdit()
        if record and record.description:
            self.descr.setPlainText(record.description)
        self.fault_cb = QComboBox()

        with self.db.get_session() as s:
            wos = (s.query(WorkOrder)
                   .order_by(WorkOrder.created_at.desc())
                   .limit(200).all())
            self.wo_cb.addItem('— не выбран —', None)
            for wo in wos:
                self.wo_cb.addItem(f'{wo.number}  ({wo.qty_total} шт.)',
                                   wo.id)
                if record and record.work_order_id == wo.id:
                    self.wo_cb.setCurrentIndex(self.wo_cb.count() - 1)

            ops = s.query(Operation).order_by(Operation.number).limit(500).all()
            self.op_cb.addItem('— не выбрана —', None)
            for op in ops:
                self.op_cb.addItem(f'{op.number}  {op.name}', op.id)
                if record and record.operation_id == op.id:
                    self.op_cb.setCurrentIndex(self.op_cb.count() - 1)

            self.fault_cb.addItem('— не указан —', None)
            for u in s.query(User).order_by(User.username).all():
                self.fault_cb.addItem(u.full_name or u.username, u.id)
                if record and record.fault_operator_id == u.id:
                    self.fault_cb.setCurrentIndex(self.fault_cb.count() - 1)

        if record and record.reason:
            for i in range(self.reason_cb.count()):
                if self.reason_cb.itemData(i) == record.reason:
                    self.reason_cb.setCurrentIndex(i)
                    break

        lay.addRow('Наряд:', self.wo_cb)
        lay.addRow('Операция:', self.op_cb)
        lay.addRow('Причина:', self.reason_cb)
        lay.addRow('Кол-во брак, шт.:', self.qty_sp)
        lay.addRow('Виновник (опционально):', self.fault_cb)
        lay.addRow('Описание:', self.descr)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

    def _save(self):
        wo_id = self.wo_cb.currentData()
        if wo_id is None:
            QMessageBox.warning(self, 'Брак', 'Выберите наряд.')
            return
        op_id = self.op_cb.currentData()
        reason = self.reason_cb.currentData()
        fault = self.fault_cb.currentData()
        with self.db.get_session() as s:
            if self.record_id is None:
                rec = sj.create_scrap(
                    s,
                    work_order_id=wo_id,
                    operation_id=op_id,
                    qty_scrap=self.qty_sp.value(),
                    reason=reason,
                    description=self.descr.toPlainText(),
                    fault_operator_id=fault,
                    reported_by=self.current_user_id,
                )
                self.record_id = rec.id
            else:
                rec = s.get(ScrapRecord, self.record_id)
                rec.work_order_id = wo_id
                rec.operation_id = op_id
                rec.reason = reason
                rec.qty_scrap = self.qty_sp.value()
                rec.fault_operator_id = fault
                rec.description = self.descr.toPlainText() or None
            s.commit()
        self.accept()


class ScrapJournalWidget(QWidget):
    """Вкладка «Брак-журнал»."""

    def __init__(self, db_manager, current_user_id: int = 0, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.user_id = current_user_id
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)

        # Сверху — KPI блок
        kpi = QGroupBox('Аналитика за 30 дней')
        kpi_lay = QHBoxLayout(kpi)
        self.lbl_total = QLabel('—')
        self.lbl_by_reason = QLabel('—')
        self.lbl_top_op = QLabel('—')
        for lbl in (self.lbl_total, self.lbl_by_reason, self.lbl_top_op):
            lbl.setWordWrap(True)
        kpi_lay.addWidget(self.lbl_total, 1)
        kpi_lay.addWidget(self.lbl_by_reason, 2)
        kpi_lay.addWidget(self.lbl_top_op, 2)
        root.addWidget(kpi)

        # Таблица записей
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            'Дата', 'Наряд', 'Операция', 'Кол-во', 'Причина',
            'Решение ОТК', 'Описание'])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_edit)
        root.addWidget(self.table, 1)

        # Кнопки
        btns = QHBoxLayout()
        b_add = QPushButton('+ Зарегистрировать брак')
        b_add.clicked.connect(self._on_add)
        b_edit = QPushButton('✎ Редактировать')
        b_edit.clicked.connect(self._on_edit)
        b_photo = QPushButton('🖼 Добавить фото…')
        b_photo.clicked.connect(self._on_attach_photo)
        b_decide = QPushButton('✅ Решение ОТК…')
        b_decide.clicked.connect(self._on_decide)
        b_refresh = QPushButton('⟳ Обновить')
        b_refresh.clicked.connect(self.refresh)
        for b in (b_add, b_edit, b_photo, b_decide):
            btns.addWidget(b)
        btns.addStretch(1)
        btns.addWidget(b_refresh)
        root.addLayout(btns)

    # ── Обновление ────────────────────────────────────────────────
    def refresh(self):
        with self.db.get_session() as s:
            recs = (s.query(ScrapRecord)
                    .order_by(ScrapRecord.reported_at.desc())
                    .limit(500).all())
            self._fill(recs)

            total = sj.total_scrap_qty(s, days=30)
            by_reason = sj.scrap_by_reason(s, days=30)
            top_op = sj.scrap_by_operation(s, days=30, top=3)

        self.lbl_total.setText(
            f'<b>Всего брак-деталей:</b> {total}')
        if by_reason:
            self.lbl_by_reason.setText(
                '<b>По причинам:</b><br>'
                + '<br>'.join(f'{r}: {qty} шт.'
                              for r, _n, qty in by_reason[:5]))
        else:
            self.lbl_by_reason.setText('<b>По причинам:</b> —')
        if top_op:
            self.lbl_top_op.setText(
                '<b>Топ операций:</b><br>'
                + '<br>'.join(f'{n}: {q} шт.' for n, q in top_op))
        else:
            self.lbl_top_op.setText('<b>Топ операций:</b> —')

    def _fill(self, recs):
        self.table.setRowCount(len(recs))
        for i, r in enumerate(recs):
            def _it(text, data=None):
                it = QTableWidgetItem(str(text))
                if data is not None:
                    it.setData(Qt.ItemDataRole.UserRole, data)
                return it
            dt = r.reported_at.strftime('%d.%m.%Y %H:%M') \
                if r.reported_at else ''
            self.table.setItem(i, 0, _it(dt, r.id))
            self.table.setItem(i, 1, _it(
                r.work_order.number if r.work_order else ''))
            self.table.setItem(i, 2, _it(
                f'{r.operation.number}/{r.operation.name}'
                if r.operation else ''))
            self.table.setItem(i, 3, _it(r.qty_scrap))
            self.table.setItem(i, 4, _it(
                r.reason.value if r.reason else ''))
            self.table.setItem(i, 5, _it(
                r.decision.value if r.decision else ''))
            self.table.setItem(i, 6, _it(r.description or ''))
        self.table.resizeColumnsToContents()

    # ── Selection helper ─────────────────────────────────────────
    def _selected_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        it = self.table.item(row, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    # ── Кнопки ────────────────────────────────────────────────────
    def _on_add(self):
        dlg = ScrapEditDialog(self.db, current_user_id=self.user_id,
                              parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_edit(self, *args):
        rid = self._selected_id()
        if rid is None:
            return
        with self.db.get_session() as s:
            rec = s.get(ScrapRecord, rid)
            if rec is None:
                return
        dlg = ScrapEditDialog(self.db, current_user_id=self.user_id,
                              record=rec, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_attach_photo(self):
        rid = self._selected_id()
        if rid is None:
            QMessageBox.information(self, 'Брак',
                                    'Выберите запись в таблице.')
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Выберите фото',
            filter='Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)'
        )
        if not files:
            return
        with self.db.get_session() as s:
            for f in files:
                try:
                    sj.attach_photo(s, scrap_id=rid, src_path=f,
                                    uploaded_by=self.user_id)
                except Exception as e:
                    QMessageBox.warning(self, 'Брак',
                                        f'Не удалось добавить {f}:\n{e}')
            s.commit()
        QMessageBox.information(
            self, 'Брак', f'Добавлено фото: {len(files)}')

    def _on_decide(self):
        rid = self._selected_id()
        if rid is None:
            QMessageBox.information(self, 'Брак',
                                    'Выберите запись в таблице.')
            return
        from PyQt6.QtWidgets import QInputDialog
        choices = [d.value for d in ScrapDecision]
        text, ok = QInputDialog.getItem(
            self, 'Решение ОТК',
            'Выберите решение:', choices, 0, False)
        if not ok:
            return
        decision = next(d for d in ScrapDecision if d.value == text)
        resolution, ok = QInputDialog.getMultiLineText(
            self, 'Решение ОТК', 'Комментарий (опционально):', '')
        with self.db.get_session() as s:
            sj.decide(s, scrap_id=rid, decision=decision,
                      resolution=resolution if ok else '',
                      decided_by=self.user_id)
            s.commit()
        self.refresh()
