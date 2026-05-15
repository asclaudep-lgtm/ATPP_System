"""
RouteWindow — окно «Операционный маршрут детали».

Открывается:
- двойным кликом по наряду в панели «Производство»;
- сканированием штрих-кода наряда (v7.3);
- из F3 «Где сейчас деталь?» (v7.4).

Содержит:
- Шапка: номер наряда, штрих-код, изделие, ТП, кол-во, статус.
- Таблица всех операций со статусом (✓/🔄/⏳/🔁), цех, исполнитель, время.
- Секция активных проблем (issue), сверху если есть.
- Журнал событий (production_events) хронологически.

При выборе текущей операции доступны кнопки «Старт/Финиш» (для мастеров).
"""
from __future__ import annotations

from datetime import datetime
import json

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QGroupBox,
    QSplitter, QTabWidget, QWidget, QMessageBox, QTextEdit,
)

from database.models import (
    WorkOrder, WorkOrderItem, RouteStep, RouteStepStatus,
    ProductionEvent, ProductionIssue, IssueStatus, Operation,
    WorkOrderStatus,
)


# Цвет/иконка для статусов RouteStep
ROUTE_STATUS = {
    RouteStepStatus.PENDING:    ('#7f8c8d', '⏳', 'Ожидает'),
    RouteStepStatus.IN_PROGRESS: ('#3498db', '🔄', 'Выполняется'),
    RouteStepStatus.DONE:       ('#27ae60', '✓', 'Выполнена'),
    RouteStepStatus.REWORK:     ('#e67e22', '🔁', 'Доработка'),
    RouteStepStatus.SKIPPED:    ('#bdc3c7', '⊘', 'Пропущена'),
}


class RouteWindow(QDialog):
    """Окно операционного маршрута детали для одного WorkOrder."""

    def __init__(self, db_manager, work_order_id: int, user: dict, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.work_order_id = work_order_id
        self.user = user

        self.setWindowTitle("Операционный маршрут детали")
        self.resize(1200, 750)
        self._init_ui()
        self.refresh()

    # ───────── UI ───────────────────────────────────────────
    def _init_ui(self):
        root = QVBoxLayout(self)

        # Шапка с информацией о наряде
        self.header = QLabel("")
        self.header.setStyleSheet(
            "background:#ecf0f1; padding:10px; font-size:12px; "
            "border-radius:4px;")
        self.header.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(self.header)

        # Активные проблемы — баннер сверху
        self.issues_box = QGroupBox("⚠ Активные проблемы")
        self.issues_box.setStyleSheet(
            "QGroupBox { color:#c0392b; font-weight:bold; }")
        ibox = QVBoxLayout(self.issues_box)
        self.issues_table = QTableWidget(0, 5)
        self.issues_table.setHorizontalHeaderLabels(
            ["Тип", "Заголовок", "Серьёзность", "Открыта", "Статус"])
        self.issues_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive)
        self.issues_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.issues_table.verticalHeader().setVisible(False)
        self.issues_table.setEditTriggers(
            self.issues_table.EditTrigger.NoEditTriggers)
        self.issues_table.setMaximumHeight(150)
        ibox.addWidget(self.issues_table)
        root.addWidget(self.issues_box)

        # Сплит: маршрут (слева) + журнал событий (справа)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Маршрут (route_steps по партиям) ──
        left = QGroupBox("Маршрут операций")
        ll = QVBoxLayout(left)
        self.route_table = QTableWidget(0, 9)
        self.route_table.setHorizontalHeaderLabels([
            "№ оп.", "Партия", "Наименование", "Цех / Участок",
            "Статус", "Исполнитель", "Старт", "Финиш", "Брак"
        ])
        h = self.route_table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.route_table.verticalHeader().setVisible(False)
        self.route_table.setEditTriggers(
            self.route_table.EditTrigger.NoEditTriggers)
        self.route_table.setAlternatingRowColors(True)
        self.route_table.setSelectionBehavior(
            self.route_table.SelectionBehavior.SelectRows)
        ll.addWidget(self.route_table)

        # Кнопки управления (для мастеров)
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("▶ Старт операции")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_start.setStyleSheet(
            "QPushButton { background:#3498db; color:white; border:none; "
            "padding:6px 14px; border-radius:3px; }")
        self.btn_finish = QPushButton("■ Финиш операции")
        self.btn_finish.clicked.connect(self._on_finish)
        self.btn_finish.setStyleSheet(
            "QPushButton { background:#27ae60; color:white; border:none; "
            "padding:6px 14px; border-radius:3px; }")
        self.btn_refresh = QPushButton("↺ Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_finish)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_refresh)
        ll.addLayout(btn_row)

        splitter.addWidget(left)

        # ── Журнал событий (production_events) ──
        right = QGroupBox("Журнал событий")
        rl = QVBoxLayout(right)
        self.events_table = QTableWidget(0, 4)
        self.events_table.setHorizontalHeaderLabels(
            ["Время", "Тип", "Пользователь", "Детали"])
        eh = self.events_table.horizontalHeader()
        eh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        eh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.events_table.verticalHeader().setVisible(False)
        self.events_table.setEditTriggers(
            self.events_table.EditTrigger.NoEditTriggers)
        self.events_table.setAlternatingRowColors(True)
        rl.addWidget(self.events_table)

        splitter.addWidget(right)
        splitter.setSizes([800, 400])
        root.addWidget(splitter, 1)

        # Закрыть
        bottom = QHBoxLayout()
        bottom.addStretch()
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        bottom.addWidget(btn_close)
        root.addLayout(bottom)

    # ───────── REFRESH ──────────────────────────────────────
    def refresh(self):
        s = self.db_manager.Session()
        try:
            wo = s.get(WorkOrder, self.work_order_id)
            if not wo:
                self.header.setText("Наряд не найден.")
                return
            self._fill_header(wo)
            self._fill_issues(wo)
            self._fill_route(wo)
            self._fill_events(s, wo)
        finally:
            s.close()

    def _fill_header(self, wo: WorkOrder):
        tp = wo.tech_process
        prod = wo.product or (tp.product if tp else None)
        prod_text = (f"{prod.designation} — {prod.name}"
                     if prod else '—')
        tp_text = (f"{tp.number} (v{tp.version}"
                   + (f', «{tp.execution_variant}»' if tp.execution_variant else '')
                   + ')') if tp else '—'

        status_color = {
            WorkOrderStatus.RELEASED: '#3498db',
            WorkOrderStatus.REGISTERED: '#9b59b6',
            WorkOrderStatus.IN_PROGRESS: '#16a085',
            WorkOrderStatus.ON_HOLD: '#f39c12',
            WorkOrderStatus.DONE: '#27ae60',
            WorkOrderStatus.CANCELED: '#c0392b',
        }.get(wo.status, '#7f8c8d')

        text = (
            f"<table cellpadding='4'>"
            f"<tr>"
            f"<td><b>Наряд:</b> {wo.number}</td>"
            f"<td><b>Штрих-код:</b> "
            f"<code style='background:#fff; padding:2px 6px; "
            f"border-radius:3px;'>{wo.barcode or '—'}</code></td>"
            f"<td><b>Статус:</b> "
            f"<span style='color:white; background:{status_color}; "
            f"padding:2px 8px; border-radius:3px;'>"
            f"{wo.status.value}</span></td>"
            f"</tr><tr>"
            f"<td colspan='3'>"
            f"<b>Деталь:</b> {prod_text}  ·  "
            f"<b>ТП:</b> {tp_text}"
            f"</td></tr><tr>"
            f"<td><b>Кол-во:</b> {wo.qty_total} шт.</td>"
            f"<td><b>Готово:</b> {wo.qty_done or 0}</td>"
            f"<td><b>Брак:</b> {wo.qty_scrap or 0}</td>"
            f"</tr></table>"
        )
        self.header.setText(text)

    def _fill_issues(self, wo: WorkOrder):
        active = [i for i in wo.issues
                  if i.status in (IssueStatus.OPEN, IssueStatus.ACKNOWLEDGED)]
        self.issues_table.setRowCount(len(active))
        if not active:
            self.issues_box.setVisible(False)
            return
        self.issues_box.setVisible(True)
        sev_color = {
            'BLOCKER': '#c0392b',
            'HIGH': '#e67e22',
            'MEDIUM': '#f1c40f',
            'LOW': '#7f8c8d',
        }
        for r, i in enumerate(active):
            self.issues_table.setItem(r, 0, QTableWidgetItem(i.kind.value))
            self.issues_table.setItem(r, 1, QTableWidgetItem(i.title))
            sev = QTableWidgetItem(i.severity.value)
            sev.setForeground(QBrush(QColor(
                sev_color.get(i.severity.name, '#7f8c8d'))))
            self.issues_table.setItem(r, 2, sev)
            self.issues_table.setItem(
                r, 3, QTableWidgetItem(
                    i.opened_at.strftime('%Y-%m-%d %H:%M') if i.opened_at else ''))
            self.issues_table.setItem(r, 4, QTableWidgetItem(i.status.value))

    def _fill_route(self, wo: WorkOrder):
        # Собираем все route_steps всех партий
        all_steps = []
        for item in wo.items:
            for st in item.route_steps:
                all_steps.append((item, st))

        # Сортируем: по seq, потом по item id
        all_steps.sort(key=lambda x: (x[1].seq, x[0].id))

        self.route_table.setRowCount(len(all_steps))
        for r, (item, step) in enumerate(all_steps):
            color, emoji, lbl = ROUTE_STATUS.get(
                step.status, ('#7f8c8d', '?', str(step.status)))

            op_no = step.operation.number if step.operation else '?'
            op_name = step.operation.name if step.operation else ''

            partition = (f"#{item.id}  ({item.qty} шт.)"
                         + (f"  S/N {item.serial}"
                            if item.serial else ''))

            shop = step.workshop.name if step.workshop else (
                step.operation.shop if step.operation else '')

            worker = step.worker.full_name if step.worker else (
                step.worker.username if step.worker else '—')

            cells = [
                op_no,
                partition,
                op_name,
                shop or '—',
                f"{emoji}  {lbl}",
                worker,
                step.started_at.strftime('%H:%M %d.%m')
                    if step.started_at else '—',
                step.finished_at.strftime('%H:%M %d.%m')
                    if step.finished_at else '—',
                str(step.qty_scrap or 0),
            ]
            for c, val in enumerate(cells):
                it = QTableWidgetItem(str(val))
                if c == 4:  # Колонка статуса — цветная
                    it.setForeground(QBrush(QColor(color)))
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.route_table.setItem(r, c, it)
            # Сохраняем в строке item_id и step_id для кнопок
            self.route_table.item(r, 0).setData(
                Qt.ItemDataRole.UserRole, (item.id, step.id))

        # Активируем кнопки только если выбрана текущая (PENDING/IN_PROGRESS) операция
        self.route_table.itemSelectionChanged.connect(
            self._update_action_buttons)
        self._update_action_buttons()

    def _fill_events(self, session, wo: WorkOrder):
        events = (session.query(ProductionEvent)
                  .filter(ProductionEvent.work_order_id == wo.id)
                  .order_by(ProductionEvent.at.desc())
                  .limit(200)
                  .all())
        self.events_table.setRowCount(len(events))
        for r, ev in enumerate(events):
            self.events_table.setItem(
                r, 0, QTableWidgetItem(
                    ev.at.strftime('%Y-%m-%d %H:%M:%S') if ev.at else ''))
            self.events_table.setItem(r, 1, QTableWidgetItem(ev.event_type))
            user_name = ''
            if ev.user:
                user_name = ev.user.full_name or ev.user.username or ''
            self.events_table.setItem(r, 2, QTableWidgetItem(user_name))

            details = ''
            if ev.payload:
                try:
                    p = json.loads(ev.payload)
                    details = ', '.join(f'{k}={v}' for k, v in p.items())
                except Exception:
                    details = ev.payload
            self.events_table.setItem(r, 3, QTableWidgetItem(details))

    def _update_action_buttons(self):
        sel = self.route_table.selectedItems()
        if not sel:
            self.btn_start.setEnabled(False)
            self.btn_finish.setEnabled(False)
            return
        row = sel[0].row()
        info_item = self.route_table.item(row, 0)
        data = info_item.data(Qt.ItemDataRole.UserRole)
        if not data:
            self.btn_start.setEnabled(False)
            self.btn_finish.setEnabled(False)
            return

        item_id, step_id = data
        s = self.db_manager.Session()
        try:
            step = s.get(RouteStep, step_id)
            if not step:
                return
            self.btn_start.setEnabled(step.status == RouteStepStatus.PENDING)
            self.btn_finish.setEnabled(
                step.status == RouteStepStatus.IN_PROGRESS)
        finally:
            s.close()

    def _selected_item_id(self) -> int | None:
        sel = self.route_table.selectedItems()
        if not sel:
            return None
        info = self.route_table.item(sel[0].row(), 0)
        data = info.data(Qt.ItemDataRole.UserRole)
        return data[0] if data else None

    # ───────── ACTIONS ──────────────────────────────────────
    def _on_start(self):
        item_id = self._selected_item_id()
        if not item_id:
            return
        try:
            from modules import production
            with self.db_manager.get_session() as s:
                production.start_operation(
                    s, user=self.user, item_id=item_id)
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "Старт операции", f"{e}")

    def _on_finish(self):
        item_id = self._selected_item_id()
        if not item_id:
            return
        # Минимально-инвазивный финиш: всё qty в годные.
        # Расширенный диалог с указанием годных/брака откроем по запросу мастера.
        try:
            from modules import production
            with self.db_manager.get_session() as s:
                item = s.get(WorkOrderItem, item_id)
                qty = item.qty if item else 0
                production.finish_operation(
                    s, user=self.user,
                    item_id=item_id,
                    qty_good=qty, qty_scrap=0)
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "Финиш операции", f"{e}")
