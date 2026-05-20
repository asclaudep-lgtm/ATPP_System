"""
v9-10 UI: Метрологическая поверка измерительных приборов.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.models import Instrument
from modules import metrology as mt


class InstrumentDialog(QDialog):
    def __init__(self, db_manager, *, instrument: Optional[Instrument] = None,
                 parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.instrument_id = instrument.id if instrument else None
        self.setWindowTitle(
            'Редактирование СИ' if instrument else 'Новый прибор')
        self.setMinimumWidth(500)
        lay = QFormLayout(self)
        self.inv = QLineEdit(instrument.inventory_no if instrument else '')
        self.name = QLineEdit(instrument.name if instrument else '')
        self.type_in = QLineEdit(instrument.type if instrument else '')
        self.range_in = QLineEdit(
            instrument.range_str if instrument else '')
        self.acc = QLineEdit(instrument.accuracy if instrument else '')
        self.loc = QLineEdit(instrument.location if instrument else '')
        self.interval = QSpinBox()
        self.interval.setRange(1, 120)
        self.interval.setValue(
            int(instrument.cal_interval_months or 12) if instrument else 12)
        self.notes = QTextEdit()
        if instrument and instrument.notes:
            self.notes.setPlainText(instrument.notes)

        lay.addRow('Инв. №:', self.inv)
        lay.addRow('Наименование:', self.name)
        lay.addRow('Тип:', self.type_in)
        lay.addRow('Диапазон:', self.range_in)
        lay.addRow('Точность:', self.acc)
        lay.addRow('Где хранится:', self.loc)
        lay.addRow('Межповерочный интервал, мес.:', self.interval)
        lay.addRow('Примечания:', self.notes)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

    def _save(self):
        if not self.inv.text().strip() or not self.name.text().strip():
            QMessageBox.warning(self, 'СИ',
                                'Инв. № и наименование обязательны.')
            return
        with self.db.get_session() as s:
            if self.instrument_id is None:
                inst = Instrument(
                    inventory_no=self.inv.text().strip(),
                    name=self.name.text().strip(),
                    type=self.type_in.text().strip() or None,
                    range_str=self.range_in.text().strip() or None,
                    accuracy=self.acc.text().strip() or None,
                    location=self.loc.text().strip() or None,
                    cal_interval_months=self.interval.value(),
                    notes=self.notes.toPlainText() or None,
                )
                s.add(inst)
            else:
                inst = s.get(Instrument, self.instrument_id)
                inst.inventory_no = self.inv.text().strip()
                inst.name = self.name.text().strip()
                inst.type = self.type_in.text().strip() or None
                inst.range_str = self.range_in.text().strip() or None
                inst.accuracy = self.acc.text().strip() or None
                inst.location = self.loc.text().strip() or None
                inst.cal_interval_months = self.interval.value()
                inst.notes = self.notes.toPlainText() or None
            s.commit()
        self.accept()


class CalibrationDialog(QDialog):
    def __init__(self, db_manager, *, instrument_id: int,
                 current_user_id: int = 0, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.instrument_id = instrument_id
        self.user_id = current_user_id
        self.setWindowTitle('Регистрация поверки')
        self.setMinimumWidth(500)
        lay = QFormLayout(self)

        self.dt = QDateEdit()
        self.dt.setCalendarPopup(True)
        self.dt.setDate(date.today())
        self.org = QLineEdit()
        self.cert = QLineEdit()
        self.result = QComboBox()
        self.result.addItems(['годен', 'не годен'])
        self.notes = QTextEdit()
        self.cert_path: Optional[str] = None
        cert_row = QHBoxLayout()
        self.cert_lbl = QLabel('— файл не выбран —')
        b_pick = QPushButton('Прикрепить PDF…')
        b_pick.clicked.connect(self._pick_pdf)
        cert_row.addWidget(self.cert_lbl, 1)
        cert_row.addWidget(b_pick)
        cert_wrap = QWidget()
        cert_wrap.setLayout(cert_row)

        lay.addRow('Дата поверки:', self.dt)
        lay.addRow('Организация:', self.org)
        lay.addRow('№ свидетельства:', self.cert)
        lay.addRow('Скан свидетельства:', cert_wrap)
        lay.addRow('Результат:', self.result)
        lay.addRow('Примечания:', self.notes)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

    def _pick_pdf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите файл', filter='PDF (*.pdf)')
        if path:
            self.cert_path = path
            self.cert_lbl.setText(path.split('/')[-1])

    def _save(self):
        # Скопируем pdf в data/calibrations/
        cert_stored = None
        if self.cert_path:
            import shutil
            import uuid
            from pathlib import Path
            store = Path('data/calibrations')
            store.mkdir(parents=True, exist_ok=True)
            src = Path(self.cert_path)
            dst = store / f'{uuid.uuid4().hex}{src.suffix.lower()}'
            shutil.copy2(src, dst)
            cert_stored = str(dst.as_posix())
        with self.db.get_session() as s:
            mt.add_calibration(
                s,
                instrument_id=self.instrument_id,
                performed_at=self.dt.date().toPyDate(),
                organization=self.org.text().strip(),
                certificate_no=self.cert.text().strip(),
                cert_path=cert_stored,
                result=self.result.currentText(),
                notes=self.notes.toPlainText(),
                created_by=self.user_id,
            )
            s.commit()
        self.accept()


class MetrologyWidget(QWidget):
    """Вкладка «Метрология»."""

    def __init__(self, db_manager, current_user_id: int = 0, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.user_id = current_user_id
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)

        hint = QLabel(
            'Учёт средств измерения (СИ) и сроков их поверки. '
            'Подсветка: 🔴 просрочено, 🟡 в ближайшие 30 дней.')
        hint.setStyleSheet('color:#666;')
        root.addWidget(hint)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            'Инв.№', 'Наименование', 'Тип', 'Диапазон',
            'Последняя поверка', 'Следующая', 'Статус'])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setStretchLastSection(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_edit)
        root.addWidget(self.table, 1)

        btns = QHBoxLayout()
        b_add = QPushButton('+ Добавить СИ')
        b_add.clicked.connect(self._on_add)
        b_edit = QPushButton('✎ Редактировать')
        b_edit.clicked.connect(self._on_edit)
        b_cal = QPushButton('📝 Зарегистрировать поверку…')
        b_cal.clicked.connect(self._on_cal)
        b_refresh = QPushButton('⟳ Обновить')
        b_refresh.clicked.connect(self.refresh)
        for b in (b_add, b_edit, b_cal):
            btns.addWidget(b)
        btns.addStretch(1)
        btns.addWidget(b_refresh)
        root.addLayout(btns)

        self.alert = QLabel('—')
        self.alert.setWordWrap(True)
        self.alert.setStyleSheet('color:#b71c1c; font-weight:600;')
        root.addWidget(self.alert)

    def refresh(self):
        today = date.today()
        with self.db.get_session() as s:
            mt.refresh_statuses(s)
            s.commit()
            rows = (s.query(Instrument)
                    .order_by(Instrument.next_cal_date.asc().nulls_first(),
                              Instrument.inventory_no)
                    .all())
            self._fill(rows, today)
            due = mt.instruments_due_soon(s, days=30)
            if due:
                expired = sum(1 for i in due
                              if i.next_cal_date and i.next_cal_date < today)
                soon = len(due) - expired
                self.alert.setText(
                    f'⚠ Просрочена поверка: {expired}   ·   '
                    f'Истекает в течение 30 дней: {soon}')
            else:
                self.alert.setText(
                    '✓ Все поверки в пределах допустимого срока.')

    def _fill(self, rows, today: date):
        self.table.setRowCount(len(rows))
        for i, inst in enumerate(rows):
            def _it(text, data=None):
                it = QTableWidgetItem(str(text))
                if data is not None:
                    it.setData(Qt.ItemDataRole.UserRole, data)
                return it
            row_color = None
            if inst.next_cal_date:
                if inst.next_cal_date < today:
                    row_color = QColor(255, 220, 220)
                elif inst.next_cal_date <= today + timedelta(days=30):
                    row_color = QColor(255, 248, 200)
            self.table.setItem(i, 0, _it(inst.inventory_no, inst.id))
            self.table.setItem(i, 1, _it(inst.name))
            self.table.setItem(i, 2, _it(inst.type or ''))
            self.table.setItem(i, 3, _it(inst.range_str or ''))
            self.table.setItem(i, 4, _it(
                inst.last_cal_date.strftime('%d.%m.%Y')
                if inst.last_cal_date else ''))
            self.table.setItem(i, 5, _it(
                inst.next_cal_date.strftime('%d.%m.%Y')
                if inst.next_cal_date else ''))
            self.table.setItem(i, 6, _it(
                inst.status.value if inst.status else ''))
            if row_color is not None:
                for c in range(self.table.columnCount()):
                    it = self.table.item(i, c)
                    if it is not None:
                        it.setBackground(QBrush(row_color))
        self.table.resizeColumnsToContents()

    def _selected_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        it = self.table.item(row, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _on_add(self):
        dlg = InstrumentDialog(self.db, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_edit(self, *args):
        iid = self._selected_id()
        if iid is None:
            return
        with self.db.get_session() as s:
            inst = s.get(Instrument, iid)
        dlg = InstrumentDialog(self.db, instrument=inst, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_cal(self):
        iid = self._selected_id()
        if iid is None:
            QMessageBox.information(self, 'Поверка',
                                    'Выберите прибор в таблице.')
            return
        dlg = CalibrationDialog(self.db, instrument_id=iid,
                                current_user_id=self.user_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
