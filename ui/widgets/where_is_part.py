"""
WhereIsPartDialog — окно «Где сейчас деталь?» (F3 hotkey).

Назначение: быстро найти все активные наряды по детали (по обозначению или
наименованию) и увидеть, где они находятся в данный момент в производстве.

Содержит:
- Поле ввода (designation / name / partial).
- Таблицу: наряд, штрих-код, изделие, ТП, кол-во, статус, текущая операция,
  цех, % готовности.
- Двойной клик по строке → открывает RouteWindow для этого наряда.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox,
)

from database.models import (
    Product, TechProcess, WorkOrder, WorkOrderItem, RouteStep,
    RouteStepStatus, WorkOrderStatus,
)


class WhereIsPartDialog(QDialog):
    """Поиск активных нарядов по детали — F3 «Где сейчас деталь?»"""

    def __init__(self, db_manager, user: dict, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.user = user

        self.setWindowTitle("Где сейчас деталь?  ·  F3")
        self.resize(1200, 600)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("<h3>🔎  Поиск активных деталей в производстве</h3>")
        root.addWidget(title)

        sub = QLabel(
            "<span style='color:#555'>"
            "Введите часть обозначения или наименования детали. "
            "Будут показаны все наряды, по которым деталь сейчас в работе.</span>"
        )
        sub.setWordWrap(True)
        root.addWidget(sub)

        top = QHBoxLayout()
        self.q_in = QLineEdit()
        self.q_in.setPlaceholderText(
            "Например: «Уголок», «51-74.88», «WO-2026-0001», штрих-код…"
        )
        self.q_in.returnPressed.connect(self._search)
        top.addWidget(self.q_in, 1)

        btn = QPushButton("🔎 Найти")
        btn.setDefault(True)
        btn.clicked.connect(self._search)
        top.addWidget(btn)
        root.addLayout(top)

        # Таблица результатов
        self.tbl = QTableWidget(0, 9)
        self.tbl.setHorizontalHeaderLabels([
            "Наряд", "Штрих-код", "Деталь", "ТП", "Кол-во",
            "Текущая операция", "Цех/Участок", "Статус", "% готово"
        ])
        h = self.tbl.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(self.tbl.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(self.tbl.SelectionBehavior.SelectRows)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.doubleClicked.connect(self._on_dbl)
        root.addWidget(self.tbl, 1)

        self.info_lbl = QLabel("—")
        root.addWidget(self.info_lbl)

        # Кнопки
        bot = QHBoxLayout()
        bot.addStretch()
        btn_open = QPushButton("📋 Открыть маршрут")
        btn_open.clicked.connect(self._open_route)
        bot.addWidget(btn_open)
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        bot.addWidget(btn_close)
        root.addLayout(bot)

        self.q_in.setFocus()

    def _search(self):
        q = self.q_in.text().strip()
        if len(q) < 2:
            self.info_lbl.setText("Введите минимум 2 символа.")
            return
        like = f"%{q}%"
        self.tbl.setRowCount(0)

        s = self.db_manager.Session()
        try:
            # Активные статусы наряда (не завершённые/отменённые)
            active_statuses = (
                WorkOrderStatus.RELEASED, WorkOrderStatus.REGISTERED,
                WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.ON_HOLD,
            )
            # Сначала ищем по полю наряда (номер/штрих-код)
            wo_q = s.query(WorkOrder).filter(
                WorkOrder.status.in_(active_statuses))
            wos_by_wo = wo_q.filter(
                WorkOrder.number.ilike(like)
                | WorkOrder.barcode.ilike(like)
            ).all()

            # Ищем по детали (designation/name)
            wos_by_prod = (s.query(WorkOrder)
                           .join(Product, Product.id == WorkOrder.product_id)
                           .filter(WorkOrder.status.in_(active_statuses))
                           .filter(Product.designation.ilike(like)
                                   | Product.name.ilike(like))
                           .all())

            # Ищем по партии (штрих-код/серийник)
            items_match = (s.query(WorkOrderItem)
                           .filter(WorkOrderItem.barcode.ilike(like)
                                   | WorkOrderItem.serial.ilike(like))
                           .all())
            wos_by_item = list({it.work_order for it in items_match
                                if it.work_order
                                and it.work_order.status in active_statuses})

            seen = set()
            all_wos = []
            for w in wos_by_wo + wos_by_prod + wos_by_item:
                if w.id in seen:
                    continue
                seen.add(w.id)
                all_wos.append(w)

            for wo in all_wos:
                self._add_row(s, wo)
        finally:
            s.close()

        self.info_lbl.setText(
            f"Найдено активных нарядов: {self.tbl.rowCount()}.")
        if self.tbl.rowCount():
            self.tbl.resizeColumnsToContents()
            h = self.tbl.horizontalHeader()
            h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            h.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

    def _add_row(self, session, wo: WorkOrder):
        prod = wo.product
        prod_text = (f"{prod.designation} — {prod.name}"
                     if prod else '—')
        tp = wo.tech_process
        tp_text = (f"{tp.number}"
                   + (f' / «{tp.execution_variant}»'
                      if tp and tp.execution_variant else '')) if tp else '—'

        # Текущая операция и цех — берём первую IN_PROGRESS, иначе первый PENDING
        cur_op_name = '—'
        cur_shop = '—'
        for it in wo.items:
            in_prog = next((st for st in it.route_steps
                            if st.status == RouteStepStatus.IN_PROGRESS), None)
            if in_prog and in_prog.operation:
                cur_op_name = (
                    f"🔄 {in_prog.operation.number} {in_prog.operation.name}")
                cur_shop = (in_prog.workshop.name if in_prog.workshop
                            else (in_prog.operation.shop or '—'))
                break

        if cur_op_name == '—':
            for it in wo.items:
                pending = next(
                    (st for st in it.route_steps
                     if st.status == RouteStepStatus.PENDING), None)
                if pending and pending.operation:
                    cur_op_name = (
                        f"⏳ {pending.operation.number} {pending.operation.name}")
                    cur_shop = (pending.workshop.name if pending.workshop
                                else (pending.operation.shop or '—'))
                    break

        # % готовности
        pct = 0
        if wo.qty_total:
            pct = int(round(100 * (wo.qty_done or 0) / wo.qty_total))

        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        cells = [
            wo.number, wo.barcode or '—', prod_text, tp_text,
            f"{wo.qty_done or 0} / {wo.qty_total} шт.",
            cur_op_name, cur_shop, wo.status.value,
            f"{pct}%"
        ]
        for c, val in enumerate(cells):
            it = QTableWidgetItem(str(val))
            self.tbl.setItem(r, c, it)
        # Сохраняем wo_id
        self.tbl.item(r, 0).setData(Qt.ItemDataRole.UserRole, wo.id)

    def _selected_wo_id(self) -> int | None:
        sel = self.tbl.selectedItems()
        if not sel:
            return None
        item = self.tbl.item(sel[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole)

    def _open_route(self):
        wo_id = self._selected_wo_id()
        if not wo_id:
            QMessageBox.information(
                self, "Маршрут", "Выберите наряд в таблице.")
            return
        self._open_route_for_wo(wo_id)

    def _on_dbl(self, idx):
        row = idx.row()
        item = self.tbl.item(row, 0)
        if item is None:
            return
        wo_id = item.data(Qt.ItemDataRole.UserRole)
        if wo_id:
            self._open_route_for_wo(wo_id)

    def _open_route_for_wo(self, wo_id: int):
        try:
            from ui.widgets.route_window import RouteWindow
            dlg = RouteWindow(self.db_manager, wo_id, self.user, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"{e}")
