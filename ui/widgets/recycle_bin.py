"""
Виджет «Корзина» — список soft-deleted элементов.

Поддерживаются:
- Технологические процессы (ТП)
- Операции
- Изделия (детали)               ← v8
- Производственные наряды        ← v8

Действия:
- Восстановить (снять флаг is_deleted)
- Удалить окончательно (DELETE)
- Автоочистка: записи, удалённые более 30 дней назад, можно очистить
  кнопкой «🧹 Очистить старше 30 дней».
"""
from datetime import datetime, timedelta

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QMessageBox, QHeaderView,
    QAbstractItemView,
)

from database.models import TechProcess, Operation, Product, WorkOrder, User


# Срок автоочистки.
PURGE_AFTER_DAYS = 30


class RecycleBinWidget(QWidget):
    """Корзина: восстановление и окончательное удаление."""

    changed = pyqtSignal()

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._build_ui()
        self.reload()

    # ──────────────────────────────────────────────────────────── UI
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        title = QLabel(
            '<b>🗑 Корзина</b> — удалённые объекты можно восстановить. '
            f'Записи старше {PURGE_AFTER_DAYS} дней — на автоочистку.'
        )
        layout.addWidget(title)

        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, 1)

        # ТП
        self.tp_tbl = self._make_table(
            ['ID', 'Номер ТП', 'Изделие', 'Удалён', 'Кем']
        )
        self.tabs.addTab(
            self._wrap_tab(self.tp_tbl, self._restore_tp, self._purge_tp),
            'ТП в корзине'
        )

        # Операции
        self.op_tbl = self._make_table(
            ['ID', '№ оп', 'Наименование', 'ТП', 'Удалена']
        )
        self.tabs.addTab(
            self._wrap_tab(self.op_tbl, self._restore_op, self._purge_op),
            'Операции в корзине'
        )

        # v8: Изделия (детали)
        self.prod_tbl = self._make_table(
            ['ID', 'Обозначение', 'Наименование', 'Удалено', 'Кем']
        )
        self.tabs.addTab(
            self._wrap_tab(self.prod_tbl,
                           self._restore_product, self._purge_product),
            'Детали в корзине'
        )

        # v8: Наряды
        self.wo_tbl = self._make_table(
            ['ID', 'Номер', 'ТП', 'Удалён', 'Кем']
        )
        self.tabs.addTab(
            self._wrap_tab(self.wo_tbl, self._restore_wo, self._purge_wo),
            'Наряды в корзине'
        )

        # Нижняя панель: автоочистка.
        bottom = QHBoxLayout()
        bottom.addStretch()
        purge_btn = QPushButton(f'🧹 Очистить старше {PURGE_AFTER_DAYS} дней')
        purge_btn.setToolTip(
            'Окончательно удалить все элементы, помещённые в Корзину '
            f'более {PURGE_AFTER_DAYS} дней назад. Это необратимо.'
        )
        purge_btn.clicked.connect(self._purge_old)
        bottom.addWidget(purge_btn)
        layout.addLayout(bottom)

    def _make_table(self, headers: list[str]) -> QTableWidget:
        tbl = QTableWidget(0, len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tbl.horizontalHeader().setStretchLastSection(True)
        tbl.verticalHeader().setVisible(False)
        return tbl

    def _wrap_tab(self, tbl: QTableWidget, restore_fn, purge_fn) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(tbl, 1)
        row = QHBoxLayout()
        b1 = QPushButton('↩ Восстановить')
        b1.clicked.connect(restore_fn)
        row.addWidget(b1)
        b2 = QPushButton('🗑 Удалить окончательно')
        b2.clicked.connect(purge_fn)
        row.addWidget(b2)
        row.addStretch()
        b3 = QPushButton('⟳ Обновить')
        b3.clicked.connect(self.reload)
        row.addWidget(b3)
        lay.addLayout(row)
        return w

    # ──────────────────────────────────────────────────────────── DATA
    def _user_name(self, s, uid):
        if not uid:
            return ''
        try:
            u = s.get(User, int(uid))
            return u.full_name or u.username if u else f'#{uid}'
        except Exception:
            return f'#{uid}'

    def reload(self):
        with self.db.get_session() as s:
            tps = (s.query(TechProcess)
                   .filter(TechProcess.is_deleted == True)
                   .order_by(TechProcess.deleted_at.desc())
                   .all())
            self._fill(self.tp_tbl, [
                (tp.id, tp.number or '',
                 tp.product.designation if tp.product else '',
                 self._fmt_dt(tp.deleted_at),
                 self._user_name(s, tp.deleted_by))
                for tp in tps
            ])
            self.tabs.setTabText(0, f'ТП в корзине ({len(tps)})')

            ops = (s.query(Operation)
                   .filter(Operation.is_deleted == True)
                   .order_by(Operation.deleted_at.desc())
                   .all())
            self._fill(self.op_tbl, [
                (op.id, op.number or '', op.name or '',
                 op.tech_process.number if op.tech_process else '',
                 self._fmt_dt(op.deleted_at))
                for op in ops
            ])
            self.tabs.setTabText(1, f'Операции в корзине ({len(ops)})')

            prods = (s.query(Product)
                     .filter(Product.is_deleted == True)
                     .order_by(Product.deleted_at.desc())
                     .all())
            self._fill(self.prod_tbl, [
                (p.id, p.designation or '', p.name or '',
                 self._fmt_dt(p.deleted_at),
                 self._user_name(s, p.deleted_by))
                for p in prods
            ])
            self.tabs.setTabText(2, f'Детали в корзине ({len(prods)})')

            wos = (s.query(WorkOrder)
                   .filter(WorkOrder.is_deleted == True)
                   .order_by(WorkOrder.deleted_at.desc())
                   .all())
            self._fill(self.wo_tbl, [
                (w.id, w.number or '',
                 w.tech_process.number if w.tech_process else '',
                 self._fmt_dt(w.deleted_at),
                 self._user_name(s, w.deleted_by))
                for w in wos
            ])
            self.tabs.setTabText(3, f'Наряды в корзине ({len(wos)})')

        for t in (self.tp_tbl, self.op_tbl, self.prod_tbl, self.wo_tbl):
            t.resizeColumnsToContents()

    def _fmt_dt(self, dt) -> str:
        return dt.strftime('%d.%m.%Y %H:%M') if dt else ''

    def _fill(self, tbl: QTableWidget, rows):
        tbl.setRowCount(0)
        for row in rows:
            r = tbl.rowCount()
            tbl.insertRow(r)
            for c, val in enumerate(row):
                tbl.setItem(r, c, QTableWidgetItem(str(val)))

    def _selected_id(self, table: QTableWidget):
        row = table.currentRow()
        if row < 0:
            return None
        try:
            return int(table.item(row, 0).text())
        except Exception:
            return None

    # ──────────────────────────────────────────────────────────── TP
    def _restore_tp(self):
        tid = self._selected_id(self.tp_tbl)
        if tid is None:
            return
        with self.db.get_session() as s:
            tp = s.get(TechProcess, tid)
            if tp:
                tp.is_deleted = False
                tp.deleted_at = None
                tp.deleted_by = None
        self.changed.emit()
        self.reload()

    def _purge_tp(self):
        tid = self._selected_id(self.tp_tbl)
        if tid is None:
            return
        if QMessageBox.question(
            self, 'Удалить окончательно',
            f'Удалить ТП #{tid} БЕЗ возможности восстановления?'
        ) != QMessageBox.StandardButton.Yes:
            return
        with self.db.get_session() as s:
            tp = s.get(TechProcess, tid)
            if tp:
                s.delete(tp)
        self.changed.emit()
        self.reload()

    # ─────────────────────────────────────────────────────────── OP
    def _restore_op(self):
        oid = self._selected_id(self.op_tbl)
        if oid is None:
            return
        with self.db.get_session() as s:
            op = s.get(Operation, oid)
            if op:
                op.is_deleted = False
                op.deleted_at = None
        self.changed.emit()
        self.reload()

    def _purge_op(self):
        oid = self._selected_id(self.op_tbl)
        if oid is None:
            return
        if QMessageBox.question(
            self, 'Удалить окончательно',
            f'Удалить операцию #{oid} БЕЗ возможности восстановления?'
        ) != QMessageBox.StandardButton.Yes:
            return
        with self.db.get_session() as s:
            op = s.get(Operation, oid)
            if op:
                s.delete(op)
        self.changed.emit()
        self.reload()

    # ──────────────────────────────────────────────────────── PRODUCT
    def _restore_product(self):
        pid = self._selected_id(self.prod_tbl)
        if pid is None:
            return
        with self.db.get_session() as s:
            p = s.get(Product, pid)
            if p:
                p.is_deleted = False
                p.deleted_at = None
                p.deleted_by = None
        self.changed.emit()
        self.reload()

    def _purge_product(self):
        pid = self._selected_id(self.prod_tbl)
        if pid is None:
            return
        if QMessageBox.question(
            self, 'Удалить окончательно',
            f'Удалить деталь #{pid} БЕЗ возможности восстановления?\n'
            f'Это также удалит все ТП этой детали, операции, эскизы и связи.'
        ) != QMessageBox.StandardButton.Yes:
            return
        with self.db.get_session() as s:
            p = s.get(Product, pid)
            if p:
                s.delete(p)
        self.changed.emit()
        self.reload()

    # ────────────────────────────────────────────────────────── WO
    def _restore_wo(self):
        wid = self._selected_id(self.wo_tbl)
        if wid is None:
            return
        with self.db.get_session() as s:
            w = s.get(WorkOrder, wid)
            if w:
                w.is_deleted = False
                w.deleted_at = None
                w.deleted_by = None
        self.changed.emit()
        self.reload()

    def _purge_wo(self):
        wid = self._selected_id(self.wo_tbl)
        if wid is None:
            return
        if QMessageBox.question(
            self, 'Удалить окончательно',
            f'Удалить наряд #{wid} БЕЗ возможности восстановления?'
        ) != QMessageBox.StandardButton.Yes:
            return
        with self.db.get_session() as s:
            w = s.get(WorkOrder, wid)
            if w:
                s.delete(w)
        self.changed.emit()
        self.reload()

    # ─────────────────────────────────────────────────────── PURGE-OLD
    def _purge_old(self):
        """v8: окончательно удалить элементы старше 30 дней."""
        cutoff = datetime.now() - timedelta(days=PURGE_AFTER_DAYS)
        counts = {'tp': 0, 'op': 0, 'product': 0, 'wo': 0}
        with self.db.get_session() as s:
            for tp in (s.query(TechProcess)
                       .filter(TechProcess.is_deleted == True,
                               TechProcess.deleted_at != None,
                               TechProcess.deleted_at < cutoff)
                       .all()):
                s.delete(tp)
                counts['tp'] += 1
            for op in (s.query(Operation)
                       .filter(Operation.is_deleted == True,
                               Operation.deleted_at != None,
                               Operation.deleted_at < cutoff)
                       .all()):
                s.delete(op)
                counts['op'] += 1
            for p in (s.query(Product)
                      .filter(Product.is_deleted == True,
                              Product.deleted_at != None,
                              Product.deleted_at < cutoff)
                      .all()):
                s.delete(p)
                counts['product'] += 1
            for w in (s.query(WorkOrder)
                      .filter(WorkOrder.is_deleted == True,
                              WorkOrder.deleted_at != None,
                              WorkOrder.deleted_at < cutoff)
                      .all()):
                s.delete(w)
                counts['wo'] += 1

        total = sum(counts.values())
        if total == 0:
            QMessageBox.information(
                self, 'Очистка',
                f'Старых записей (> {PURGE_AFTER_DAYS} дней) в корзине нет.'
            )
            return
        QMessageBox.information(
            self, 'Очистка',
            'Удалено окончательно:\n'
            f'  • ТП: {counts["tp"]}\n'
            f'  • Операций: {counts["op"]}\n'
            f'  • Деталей: {counts["product"]}\n'
            f'  • Нарядов: {counts["wo"]}\n'
            f'Всего: {total}.'
        )
        self.changed.emit()
        self.reload()
