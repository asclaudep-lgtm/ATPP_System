"""PDO Dispatcher — Kanban-like board with orders by status."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QComboBox, QGroupBox, QMessageBox,
    QSplitter, QTextEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

from modules import pdo_module
from database.models import PDOStatus

STATUS_COLORS = {
    PDOStatus.NEW:                '#95a5a6',
    PDOStatus.WITH_TECHNOLOGIST:  '#f39c12',
    PDOStatus.MTP_SIGNED:         '#2980b9',
    PDOStatus.READY_FOR_SHOP:     '#27ae60',
    PDOStatus.IN_SHOP:            '#8e44ad',
    PDOStatus.QC:                 '#e67e22',
    PDOStatus.CLOSED:             '#2c3e50',
    PDOStatus.CANCELLED:          '#c0392b',
}


class PDODispatcherWidget(QWidget):
    """Kanban board for PDO production orders."""

    refresh_requested = pyqtSignal()

    def __init__(self, db_manager, user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.user = user
        self._order_detail_cache = {}
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Header
        hdr = QHBoxLayout()
        title = QLabel('Диспетчер ПДО')
        tf = QFont()
        tf.setPointSize(14)
        tf.setBold(True)
        title.setFont(tf)
        hdr.addWidget(title)
        hdr.addStretch()

        new_btn = QPushButton('+ Новый заказ')
        new_btn.setStyleSheet(
            'QPushButton { background-color: #27ae60; color: white; '
            'border: none; padding: 8px 16px; border-radius: 4px; }')
        new_btn.clicked.connect(self._create_order)
        hdr.addWidget(new_btn)

        refresh_btn = QPushButton('↻')
        refresh_btn.clicked.connect(self.refresh)
        hdr.addWidget(refresh_btn)
        layout.addLayout(hdr)

        # Splitter: Kanban left, detail right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Kanban columns
        kanban = QWidget()
        kanban_layout = QHBoxLayout(kanban)
        kanban_layout.setSpacing(6)
        self._columns = {}

        active_statuses = [
            PDOStatus.NEW, PDOStatus.WITH_TECHNOLOGIST,
            PDOStatus.MTP_SIGNED, PDOStatus.READY_FOR_SHOP,
            PDOStatus.IN_SHOP, PDOStatus.QC,
        ]
        for st in active_statuses:
            grp = QGroupBox(st.value)
            grp.setStyleSheet(
                f'QGroupBox {{ border-left: 4px solid '
                f'{STATUS_COLORS.get(st, "#999")}; }}')
            vl = QVBoxLayout(grp)
            tbl = QTableWidget(0, 3)
            tbl.setHorizontalHeaderLabels(['Заказ', 'Изделие', 'Срок'])
            tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            tbl.clicked.connect(lambda checked, t=tbl: self._on_select(t))
            vl.addWidget(tbl)
            kanban_layout.addWidget(grp)
            self._columns[st] = tbl

        splitter.addWidget(kanban)

        # Detail panel
        detail = QWidget()
        dl = QVBoxLayout(detail)
        self._detail_title = QLabel('Выберите заказ')
        tf2 = QFont()
        tf2.setPointSize(11)
        tf2.setBold(True)
        self._detail_title.setFont(tf2)
        dl.addWidget(self._detail_title)

        self._detail_info = QLabel('')
        self._detail_info.setWordWrap(True)
        dl.addWidget(self._detail_info)

        self._history_table = QTableWidget(0, 4)
        self._history_table.setHorizontalHeaderLabels(
            ['От', 'Кому', 'Статус', 'Дата'])
        self._history_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        dl.addWidget(self._history_table)

        btn_row = QHBoxLayout()

        if self.user.get('role') in ('technologist', 'admin'):
            self._sign_mtp_btn = QPushButton('✍ Подписать МТП')
            self._sign_mtp_btn.setStyleSheet(
                'QPushButton { background-color: #2980b9; color: white; '
                'border: none; padding: 6px 12px; border-radius: 4px; }')
            self._sign_mtp_btn.clicked.connect(self._sign_mtp)
            btn_row.addWidget(self._sign_mtp_btn)
            self._sign_mtp_btn.hide()

        if self.user.get('role') in ('admin', 'technologist', 'engineer'):
            self._release_btn = QPushButton('📦 Передать в цех')
            self._release_btn.setStyleSheet(
                'QPushButton { background-color: #8e44ad; color: white; '
                'border: none; padding: 6px 12px; border-radius: 4px; }')
            self._release_btn.clicked.connect(self._release_to_shop)
            btn_row.addWidget(self._release_btn)
            self._release_btn.hide()

        if self.user.get('role') in ('qc', 'admin'):
            self._close_btn = QPushButton('✓ Закрыть заказ')
            self._close_btn.clicked.connect(self._close_order)
            btn_row.addWidget(self._close_btn)
            self._close_btn.hide()

        btn_row.addStretch()
        dl.addLayout(btn_row)
        dl.addStretch()
        splitter.addWidget(detail)

        splitter.setSizes([750, 350])
        layout.addWidget(splitter, stretch=1)

    def refresh(self):
        with self.db_manager.get_session() as s:
            for st, tbl in self._columns.items():
                orders = pdo_module.list_orders_by_status(s, st, limit=50)
                tbl.setRowCount(len(orders))
                for i, o in enumerate(orders):
                    tbl.setItem(i, 0, QTableWidgetItem(o.number))
                    prod = o.product.designation if o.product else ''
                    tbl.setItem(i, 1, QTableWidgetItem(prod))
                    due = str(o.due_date) if o.due_date else '—'
                    tbl.setItem(i, 2, QTableWidgetItem(due))
                tbl.resizeColumnsToContents()

    def _on_select(self, tbl):
        row = tbl.currentRow()
        if row < 0:
            return
        order_num = tbl.item(row, 0).text()

        with self.db_manager.get_session() as s:
            from database.models import ProductionOrder
            order = s.query(ProductionOrder).filter(
                ProductionOrder.number == order_num).first()
            if order is None:
                return
            detail = pdo_module.get_order_detail(s, order.id)
            self._current_order = detail
            self._detail_title.setText(
                f'{detail["number"]} — {detail["product"]}')
            self._detail_info.setText(
                f'Статус: {detail["status"]}\n'
                f'Изделие: {detail["product_name"]}\n'
                f'Кол-во: {detail["qty"]} | Выполнено: {detail["qty_done"]}\n'
                f'Срок: {detail["due_date"] or "—"}\n'
                f'Технолог: {detail["technologist"]}\n'
                f'МТП: {"✓ подписан" if detail["mtp_signed"] else "✗ не подписан"}')

            self._history_table.setRowCount(len(detail['handoffs']))
            for i, h in enumerate(detail['handoffs']):
                self._history_table.setItem(i, 0, QTableWidgetItem(h['from']))
                self._history_table.setItem(i, 1, QTableWidgetItem(h['to']))
                self._history_table.setItem(
                    i, 2, QTableWidgetItem(h['status']))
                self._history_table.setItem(
                    i, 3, QTableWidgetItem(h['created_at'] or ''))

            # Show/hide action buttons
            st = detail['status']
            has_mtp_btn = hasattr(self, '_sign_mtp_btn')
            has_release_btn = hasattr(self, '_release_btn')
            has_close_btn = hasattr(self, '_close_btn')

            if has_mtp_btn:
                self._sign_mtp_btn.setVisible(
                    st in ('Новый', 'У технолога'))
            if has_release_btn:
                self._release_btn.setVisible(
                    st in ('МТП подписан', 'Готов к передаче в цех'))
            if has_close_btn:
                self._close_btn.setVisible(st == 'ОТК')

    def _create_order(self):
        from PyQt6.QtWidgets import QInputDialog
        from database.models import Product
        des, ok = QInputDialog.getText(
            self, 'Новый заказ', 'Обозначение изделия:')
        if not ok or not des.strip():
            return
        qty_str, ok2 = QInputDialog.getText(
            self, 'Количество', 'Количество:')
        if not ok2:
            return
        try:
            qty = int(qty_str)
        except ValueError:
            qty = 1
        with self.db_manager.get_session() as s:
            p = s.query(Product).filter(
                Product.designation == des.strip(),
                Product.is_deleted == False).first()
            if p is None:
                QMessageBox.warning(self, 'Ошибка', 'Изделие не найдено.')
                return
            order = pdo_module.create_order(
                s, product_id=p.id, qty=qty,
                due_date=__import__('datetime').date.today(),
                created_by=self.user.get('id', 1),
            )
            QMessageBox.information(
                self, 'Создан',
                f'Заказ {order.number} создан.\n'
                f'Статус: {order.status.value}')
        self.refresh()

    def _sign_mtp(self):
        if not hasattr(self, '_current_order'):
            return
        oid = self._current_order['id']
        from PyQt6.QtWidgets import QInputDialog
        tp_id_str, ok = QInputDialog.getText(
            self, 'Подпись МТП', 'ID техпроцесса:')
        if not ok:
            return
        try:
            with self.db_manager.get_session() as s:
                pdo_module.sign_mtp(
                    s, order_id=oid,
                    tech_process_id=int(tp_id_str),
                    signed_by=self.user.get('id', 1),
                )
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))
        self.refresh()

    def _release_to_shop(self):
        if not hasattr(self, '_current_order'):
            return
        oid = self._current_order['id']
        from PyQt6.QtWidgets import QInputDialog
        shop, ok = QInputDialog.getText(
            self, 'Передача в цех', 'Номер цеха/участка:',
            text='Цех 1')
        if not ok:
            return
        with self.db_manager.get_session() as s:
            pdo_module.release_to_shop(
                s, order_id=oid, shop=shop,
                released_by=self.user.get('id', 1),
            )
        self.refresh()

    def _close_order(self):
        if not hasattr(self, '_current_order'):
            return
        oid = self._current_order['id']
        with self.db_manager.get_session() as s:
            pdo_module.close_order(
                s, order_id=oid,
                qty_done=self._current_order['qty'],
            )
        self.refresh()
