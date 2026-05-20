"""Отчёты производства — единый диалог с 4 вкладками (B7–B10).

Каждая вкладка показывает таблицу + фильтр по периоду + кнопку экспорта
в Excel/CSV/PDF. Все запросы выполняются по нажатию «Обновить».
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules import production_reports

# ─────────────────────────────────────────────────────────────────────────────
# Утилиты экспорта
# ─────────────────────────────────────────────────────────────────────────────

def _table_to_csv(headers: list[str], rows: list[list[str]], path: Path):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(headers)
        w.writerows(rows)


def _table_to_xlsx(headers: list[str], rows: list[list[str]],
                    path: Path, title: str):
    """Excel-экспорт. Если openpyxl недоступен — кидает ImportError."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = title[:30]
    bold = Font(bold=True, color='FFFFFF')
    fill = PatternFill('solid', start_color='2c3e50')
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = bold
        cell.fill = fill
    for r, row in enumerate(rows, start=2):
        for c, v in enumerate(row, start=1):
            ws.cell(row=r, column=c, value=v)
    for col_idx in range(1, len(headers) + 1):
        col_letter = ws.cell(row=1, column=col_idx).column_letter
        ws.column_dimensions[col_letter].width = max(
            14,
            max((len(str(headers[col_idx-1])),) + tuple(
                len(str(row[col_idx-1])) for row in rows)) + 2)
    wb.save(path)


# ─────────────────────────────────────────────────────────────────────────────
# Базовый класс вкладки
# ─────────────────────────────────────────────────────────────────────────────

class _BaseReportTab(QWidget):
    HEADERS: list[str] = []
    TITLE: str = 'Отчёт'

    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user or {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)

        # фильтры периода
        form = QFormLayout()
        today = date.today()
        self.date_from = QDateEdit(today.replace(day=1))
        self.date_from.setCalendarPopup(True)
        self.date_to = QDateEdit(today)
        self.date_to.setCalendarPopup(True)
        form.addRow('С даты:', self.date_from)
        form.addRow('По дату:', self.date_to)
        root.addLayout(form)

        # кнопки
        bar = QHBoxLayout()
        self.btn_refresh = QPushButton('Обновить')
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        self.btn_csv = QPushButton('CSV…')
        self.btn_csv.clicked.connect(self._export_csv)
        bar.addWidget(self.btn_csv)
        self.btn_xlsx = QPushButton('Excel…')
        self.btn_xlsx.clicked.connect(self._export_xlsx)
        bar.addWidget(self.btn_xlsx)
        bar.addStretch(1)
        self.summary = QLabel('')
        bar.addWidget(self.summary)
        root.addLayout(bar)

        # таблица
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)

    # ----- абстрактные методы
    def _fetch(self) -> list[list[str]]:
        raise NotImplementedError

    # ----- общие
    def refresh(self):
        try:
            rows = self._fetch()
        except Exception as e:
            QMessageBox.critical(self, 'Отчёт',
                                 f'Не удалось построить отчёт:\n{e}')
            return
        self.table.setRowCount(0)
        for r in rows:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            for c, v in enumerate(r):
                it = QTableWidgetItem(str(v) if v is not None else '')
                if isinstance(v, (int, float)):
                    it.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight |
                        Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, c, it)
        self.table.resizeColumnsToContents()
        self.summary.setText(f'Записей: {len(rows)}')

    def _collect_rows(self) -> list[list[str]]:
        out = []
        for r in range(self.table.rowCount()):
            row = []
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                row.append(it.text() if it else '')
            out.append(row)
        return out

    def _export_csv(self):
        if self.table.rowCount() == 0:
            QMessageBox.information(self, 'Экспорт', 'Сначала «Обновить».')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Сохранить CSV',
            f'{self.TITLE}.csv', 'CSV (*.csv)')
        if not path:
            return
        try:
            _table_to_csv(self.HEADERS, self._collect_rows(), Path(path))
            QMessageBox.information(self, 'Экспорт', 'Файл сохранён.')
        except Exception as e:
            QMessageBox.warning(self, 'Экспорт', f'Не удалось:\n{e}')

    def _export_xlsx(self):
        if self.table.rowCount() == 0:
            QMessageBox.information(self, 'Экспорт', 'Сначала «Обновить».')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Сохранить Excel',
            f'{self.TITLE}.xlsx', 'Excel (*.xlsx)')
        if not path:
            return
        try:
            _table_to_xlsx(self.HEADERS, self._collect_rows(), Path(path),
                           self.TITLE)
            QMessageBox.information(self, 'Экспорт', 'Файл сохранён.')
        except ImportError:
            QMessageBox.warning(self, 'Экспорт',
                                'Для XLSX нужен openpyxl: '
                                'pip install openpyxl')
        except Exception as e:
            QMessageBox.warning(self, 'Экспорт', f'Не удалось:\n{e}')

    def _period(self) -> tuple[datetime, datetime]:
        d1 = self.date_from.date().toPyDate()
        d2 = self.date_to.date().toPyDate()
        return (datetime.combine(d1, datetime.min.time()),
                datetime.combine(d2, datetime.max.time()))


# ─────────────────────────────────────────────────────────────────────────────
# B7 — выработка
# ─────────────────────────────────────────────────────────────────────────────
class ThroughputTab(_BaseReportTab):
    TITLE = 'Выработка за период'
    HEADERS = ['Сотрудник', 'Участок', 'Завершено операций',
               'Годных', 'Брак']

    def _fetch(self):
        d1, d2 = self._period()
        with self.db_manager.get_session() as s:
            data = production_reports.throughput(
                s, date_from=d1, date_to=d2)
        return [[r['worker_name'], r['workshop_name'],
                 r['finished_steps'],
                 r['qty_good_total'],
                 r['qty_scrap_total']] for r in data]


# ─────────────────────────────────────────────────────────────────────────────
# B8 — среднее время
# ─────────────────────────────────────────────────────────────────────────────
class LeadTimeTab(_BaseReportTab):
    TITLE = 'Среднее время операций'
    HEADERS = ['Участок', 'Операций (DONE)', 'Сред. время, мин',
               'Мин, мин', 'Макс, мин', 'Годных', 'Брак']

    def _fetch(self):
        d1, d2 = self._period()
        with self.db_manager.get_session() as s:
            data = production_reports.lead_time(
                s, date_from=d1, date_to=d2)
        return [[r['workshop_name'], r['count_steps'],
                 r['avg_minutes'], r['min_minutes'], r['max_minutes'],
                 r['total_qty_good'], r['total_qty_scrap']]
                for r in data]


# ─────────────────────────────────────────────────────────────────────────────
# B9 — журнал смены
# ─────────────────────────────────────────────────────────────────────────────
class ShiftJournalTab(_BaseReportTab):
    TITLE = 'Журнал производства за смену'
    HEADERS = ['Время', 'Тип', 'Наряд', 'Кто', 'Подробности']

    def _build(self):
        # Своя форма: вместо «с/по» — одна дата
        super()._build()
        # Перенастраиваем диапазон: по умолчанию сегодня
        self.date_to.setVisible(False)
        # Меняем подпись поля. Берём form-layout у первой строки.
        # (Проще: оставляем оба, используем только date_from.)
        self.date_from.setToolTip('Дата смены')

    def _fetch(self):
        d1 = self.date_from.date().toPyDate()
        with self.db_manager.get_session() as s:
            data = production_reports.shift_journal(s, day=d1)
        return [[r['at'].strftime('%H:%M:%S') if r['at'] else '',
                 r['event_type'],
                 r['work_order_number'],
                 r['actor'],
                 r['payload_summary']]
                for r in data]


# ─────────────────────────────────────────────────────────────────────────────
# B10 — аналитика проблем
# ─────────────────────────────────────────────────────────────────────────────
class IssuesSummaryTab(_BaseReportTab):
    TITLE = 'Аналитика проблем'
    HEADERS = ['Тип проблемы', 'Всего', 'Блокирующие',
               'Решено', 'Сред. время устранения, ч']

    def _fetch(self):
        d1, d2 = self._period()
        with self.db_manager.get_session() as s:
            data = production_reports.issues_summary(
                s, date_from=d1, date_to=d2)
        return [[r['kind'], r['count'], r['blocking'],
                 r['resolved'], r['avg_resolve_hours']]
                for r in data]


# ─────────────────────────────────────────────────────────────────────────────
# Главный диалог
# ─────────────────────────────────────────────────────────────────────────────

class ProductionReportsDialog(QDialog):
    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user or {}
        self.setWindowTitle('Отчёты производства')
        self.setMinimumSize(1000, 600)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        title = QLabel('Отчёты производства')
        f = QFont(); f.setPointSize(14); f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(ThroughputTab(self.db_manager, self.current_user),
                    'B7. Выработка')
        tabs.addTab(LeadTimeTab(self.db_manager, self.current_user),
                    'B8. Среднее время')
        tabs.addTab(ShiftJournalTab(self.db_manager, self.current_user),
                    'B9. Журнал смены')
        tabs.addTab(IssuesSummaryTab(self.db_manager, self.current_user),
                    'B10. Проблемы')
        root.addWidget(tabs)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        root.addWidget(bb)
