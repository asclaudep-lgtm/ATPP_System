"""
v9-3 UI: Терминал ОТК — фокус-вид для приёмки партий.

Список нарядов, которые «ждут ОТК», крупные кнопки решений,
быстрое добавление брак-записи с фото.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSplitter, QFrame, QSpinBox,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QTextEdit,
    QFileDialog, QMessageBox, QInputDialog,
)

from database.models import (
    WorkOrder, WorkOrderItem, WorkOrderStatus, RouteStep, RouteStepStatus,
    ScrapReason, ScrapDecision, Operation,
)
from modules import scrap_journal as sj


def _pending_qa_orders(session):
    """Наряды, по которым есть готовые позиции, но не закрытые."""
    return (session.query(WorkOrder)
            .filter(WorkOrder.status.in_(
                (WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS)))
            .order_by(WorkOrder.due_date.asc().nulls_last(),
                      WorkOrder.created_at.asc())
            .all())


class _AcceptDialog(QDialog):
    def __init__(self, *, max_qty: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Приёмка партии')
        lay = QFormLayout(self)
        self.good = QSpinBox()
        self.good.setRange(0, max_qty)
        self.good.setValue(max_qty)
        self.scrap = QSpinBox()
        self.scrap.setRange(0, max_qty)
        self.scrap.setValue(0)
        lay.addRow(f'Партия, шт.:', QLabel(f'{max_qty}'))
        lay.addRow('Принято в норму:', self.good)
        lay.addRow('В брак:', self.scrap)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)


class QATerminalWidget(QWidget):
    """Терминал ОТК."""

    def __init__(self, db_manager, current_user_id: int = 0, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.user_id = current_user_id
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)

        head = QLabel('🔍 Терминал ОТК — приёмка партий')
        f = head.font()
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        head.setFont(f)
        root.addWidget(head)

        split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split, 1)

        # Слева — список ожидающих нарядов
        left = QFrame()
        ll = QVBoxLayout(left)
        ll.addWidget(QLabel('Ожидают проверки:'))
        self.list = QListWidget()
        self.list.itemSelectionChanged.connect(self._on_select)
        ll.addWidget(self.list, 1)
        b_refresh = QPushButton('⟳ Обновить список')
        b_refresh.clicked.connect(self.refresh)
        ll.addWidget(b_refresh)
        split.addWidget(left)

        # Справа — крупные кнопки решений
        right = QFrame()
        rl = QVBoxLayout(right)
        self.info = QLabel('— выберите наряд —')
        self.info.setWordWrap(True)
        inf = self.info.font()
        inf.setPointSize(inf.pointSize() + 2)
        self.info.setFont(inf)
        rl.addWidget(self.info)

        rl.addSpacing(20)

        btns_layout = QVBoxLayout()
        for label, color, cb in [
            ('✅ Принять партию', '#2e7d32', self._on_accept),
            ('↩ На доработку', '#f9a825', self._on_rework),
            ('✗ В брак (с фото)', '#c62828', self._on_scrap),
        ]:
            b = QPushButton(label)
            b.setStyleSheet(
                f'QPushButton {{background:{color}; color:white;'
                f' padding:18px; font-size:18px; font-weight:600;'
                f' border-radius:8px;}} '
                f'QPushButton:disabled {{background:#bbb;}}')
            b.clicked.connect(cb)
            btns_layout.addWidget(b)
            self._reg_btn(label, b)
        rl.addLayout(btns_layout)
        rl.addStretch(1)
        split.addWidget(right)
        split.setSizes([400, 700])

    def _reg_btn(self, label, btn):
        if not hasattr(self, '_btns'):
            self._btns = {}
        self._btns[label] = btn

    def refresh(self):
        with self.db.get_session() as s:
            wos = _pending_qa_orders(s)
            self.list.clear()
            for w in wos:
                txt = (f'{w.number}   ({w.qty_total} шт.)   '
                       f'{w.status.value if w.status else ""}')
                it = QListWidgetItem(txt)
                it.setData(Qt.ItemDataRole.UserRole, w.id)
                self.list.addItem(it)

    def _selected_wo_id(self) -> Optional[int]:
        items = self.list.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    def _on_select(self):
        wid = self._selected_wo_id()
        if wid is None:
            self.info.setText('— выберите наряд —')
            return
        with self.db.get_session() as s:
            wo = s.get(WorkOrder, wid)
            if wo is None:
                return
            tp = wo.tech_process
            self.info.setText(
                f'<b>Наряд:</b> {wo.number}<br>'
                f'<b>ТП:</b> {tp.number if tp else "—"}<br>'
                f'<b>Деталь:</b> '
                f'{tp.product.designation if tp and tp.product else "—"} '
                f'{tp.product.name if tp and tp.product else ""}<br>'
                f'<b>Кол-во:</b> {wo.qty_total}<br>'
                f'<b>Срок:</b> '
                f'{wo.due_date.strftime("%d.%m.%Y") if wo.due_date else "—"}<br>'
                f'<b>Статус:</b> {wo.status.value if wo.status else "—"}')

    def _on_accept(self):
        wid = self._selected_wo_id()
        if wid is None:
            return
        with self.db.get_session() as s:
            wo = s.get(WorkOrder, wid)
            max_qty = int(wo.qty_total or 0)
        dlg = _AcceptDialog(max_qty=max_qty, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        good, scrap = dlg.good.value(), dlg.scrap.value()
        if good + scrap > max_qty:
            QMessageBox.warning(
                self, 'Приёмка',
                f'Сумма принятых + брак ({good + scrap}) > партии ({max_qty}).')
            return
        with self.db.get_session() as s:
            wo = s.get(WorkOrder, wid)
            wo.status = WorkOrderStatus.DONE
            for it in wo.items:
                it.qty_good = int(it.qty or 0)
            if scrap > 0:
                sj.create_scrap(
                    s, work_order_id=wid, qty_scrap=scrap,
                    reason=ScrapReason.OTHER,
                    description='Зарегистрировано в терминале ОТК '
                                'при приёмке партии',
                    reported_by=self.user_id)
            s.commit()
        QMessageBox.information(
            self, 'Приёмка',
            f'Принято: {good}, в брак: {scrap}.\nНаряд закрыт.')
        self.refresh()

    def _on_rework(self):
        wid = self._selected_wo_id()
        if wid is None:
            return
        comment, ok = QInputDialog.getMultiLineText(
            self, 'На доработку', 'Причина и что доработать:', '')
        if not ok:
            return
        with self.db.get_session() as s:
            wo = s.get(WorkOrder, wid)
            wo.status = WorkOrderStatus.IN_PROGRESS
            sj.create_scrap(
                s, work_order_id=wid, qty_scrap=0,
                reason=ScrapReason.OTHER,
                description=f'[ОТК: на доработку] {comment}',
                reported_by=self.user_id)
            s.commit()
        self.refresh()

    def _on_scrap(self):
        wid = self._selected_wo_id()
        if wid is None:
            return
        qty, ok = QInputDialog.getInt(
            self, 'В брак', 'Сколько в брак, шт.:',
            value=1, min=1, max=99999)
        if not ok:
            return
        reasons = [r.value for r in ScrapReason]
        r_str, ok = QInputDialog.getItem(
            self, 'Причина', 'Причина брака:', reasons, 0, False)
        if not ok:
            return
        reason = next(r for r in ScrapReason if r.value == r_str)
        descr, ok = QInputDialog.getMultiLineText(
            self, 'Описание', 'Что случилось:', '')
        if not ok:
            descr = ''
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Фото (опционально)',
            filter='Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)')
        with self.db.get_session() as s:
            rec = sj.create_scrap(
                s, work_order_id=wid, qty_scrap=qty,
                reason=reason, description=descr,
                reported_by=self.user_id)
            for f in files:
                try:
                    sj.attach_photo(s, scrap_id=rec.id, src_path=f,
                                    uploaded_by=self.user_id)
                except Exception:
                    pass
            sj.decide(s, scrap_id=rec.id, decision=ScrapDecision.SCRAP,
                      resolution='Решение ОТК: в брак',
                      decided_by=self.user_id)
            s.commit()
        QMessageBox.information(
            self, 'Брак', f'Записано: {qty} шт. в брак (с {len(files)} фото).')
        self.refresh()
