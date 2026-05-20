"""Виджет «Производство».

Три вкладки:
    - Наряды: список нарядов с фильтрами.
    - Партии: WIP по участкам, поиск партии (в т.ч. по штрих-коду).
    - Проблемы: открытые проблемы / архив, действия мастера.
"""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from database.models import (
    IssueStatus,
    ProductionIssue,
    RouteStepStatus,
    WorkOrder,
    WorkOrderItem,
    WorkOrderStatus,
    Workshop,
)

_logger = logging.getLogger(__name__)
from modules import production

# ──────────────────────────────────────────────────────────────────────────
# Вспомогательное
# ──────────────────────────────────────────────────────────────────────────

def _set_table_props(t: QTableWidget, *, multi: bool = False):
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    # v8: для таблиц с пачечной печатью разрешаем мультивыбор Ctrl/Shift.
    if multi:
        t.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
    else:
        t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setStretchLastSection(True)


def _can(role: str, allowed: set) -> bool:
    return (role or '') in allowed


# ──────────────────────────────────────────────────────────────────────────
# Вкладка «Наряды»
# ──────────────────────────────────────────────────────────────────────────

class OrdersTab(QWidget):
    def __init__(self, db, user, parent=None):
        super().__init__(parent)
        self.db = db
        self.user = user or {}
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        bar = QHBoxLayout()

        self.btn_release = QPushButton('Передать ТП в производство…')
        self.btn_release.clicked.connect(self._on_release)
        if not _can(self.user.get('role'), production.ROLE_RELEASE):
            self.btn_release.setEnabled(False)
            self.btn_release.setToolTip(
                'Доступно ролям: ' + ', '.join(production.ROLE_RELEASE))
        bar.addWidget(self.btn_release)

        self.btn_register = QPushButton('Регистрация наряда…')
        self.btn_register.clicked.connect(self._on_register)
        if not _can(self.user.get('role'), production.ROLE_REGISTER):
            self.btn_register.setEnabled(False)
            self.btn_register.setToolTip(
                'Доступно ролям: ' + ', '.join(production.ROLE_REGISTER))
        bar.addWidget(self.btn_register)

        # v7.2: операционный маршрут детали
        self.btn_route = QPushButton('📋 Маршрут')
        self.btn_route.setToolTip(
            'Открыть окно «Операционный маршрут детали» — статусы операций, '
            'журнал событий, активные проблемы')
        self.btn_route.clicked.connect(self._on_route)
        bar.addWidget(self.btn_route)

        # v7.5: МТП Excel под форму УЗГА
        self.btn_mtp = QPushButton('📄 МТП (xlsx)')
        self.btn_mtp.setToolTip(
            'Сгенерировать МТП по форме УЗГА со штрих-кодом наряда')
        self.btn_mtp.clicked.connect(self._on_mtp_excel)
        bar.addWidget(self.btn_mtp)

        # v8: МТП PDF — для электронного архива (xlsx редактируется, PDF — нет)
        self.btn_mtp_pdf = QPushButton('📑 МТП (PDF)')
        self.btn_mtp_pdf.setToolTip(
            'Сгенерировать МТП в формате PDF (для электронного архива).')
        self.btn_mtp_pdf.clicked.connect(self._on_mtp_pdf)
        bar.addWidget(self.btn_mtp_pdf)

        # v8: Пачкой — для выбора N нарядов и печати одним кликом.
        self.btn_mtp_batch = QPushButton('📦 Пачка МТП…')
        self.btn_mtp_batch.setToolTip(
            'Выделить несколько нарядов в таблице и получить:\n'
            '  • N отдельных xlsx (в выбранной папке), или\n'
            '  • один многостраничный PDF.')
        self.btn_mtp_batch.clicked.connect(self._on_mtp_batch)
        bar.addWidget(self.btn_mtp_batch)

        self.btn_labels = QPushButton('🖨 Ярлыки PDF…')
        self.btn_labels.setToolTip(
            'Сгенерировать PDF со штрих-кодами всех партий выбранного наряда')
        self.btn_labels.clicked.connect(self._on_print_labels)
        bar.addWidget(self.btn_labels)

        self.btn_cancel = QPushButton('🛑 Отменить наряд…')
        self.btn_cancel.clicked.connect(self._on_cancel)
        if not _can(self.user.get('role'), production.ROLE_CANCEL):
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.setToolTip(
                'Доступно ролям: ' + ', '.join(production.ROLE_CANCEL))
        bar.addWidget(self.btn_cancel)

        bar.addSpacing(20)
        bar.addWidget(QLabel('Фильтр:'))
        self.filter_status = QComboBox()
        self.filter_status.addItem('— все статусы —', userData=None)
        for st in WorkOrderStatus:
            self.filter_status.addItem(st.value, userData=st)
        self.filter_status.currentIndexChanged.connect(self.refresh)
        bar.addWidget(self.filter_status)

        bar.addStretch(1)
        btn_refresh = QPushButton('Обновить')
        btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(btn_refresh)

        root.addLayout(bar)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            'Наряд', 'ТП', 'Деталь', 'Кол-во', 'Готово', 'Брак',
            'Статус', 'Создан',
        ])
        # v8: мультивыбор для печати пачкой МТП.
        _set_table_props(self.table, multi=True)
        self.table.cellDoubleClicked.connect(self._on_dbl)
        root.addWidget(self.table)

    def refresh(self):
        self.table.setRowCount(0)
        flt_status = self.filter_status.currentData()
        with self.db.get_session() as s:
            q = s.query(WorkOrder).order_by(WorkOrder.id.desc())
            if flt_status is not None:
                q = q.filter(WorkOrder.status == flt_status)
            rows = []
            for wo in q.all():
                tp = wo.tech_process
                product = wo.product
                rows.append({
                    'id': wo.id,
                    'number': wo.number,
                    'tp_number': tp.number if tp else '—',
                    'product': (
                        f'{product.designation} {product.name}'
                        if product else '—'),
                    'qty_total': wo.qty_total,
                    'qty_done': wo.qty_done or 0,
                    'qty_scrap': wo.qty_scrap or 0,
                    'status': wo.status.value,
                    'status_enum': wo.status,
                    'created': wo.created_at,
                })

        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = [
                r['number'], r['tp_number'], r['product'],
                str(r['qty_total']), str(r['qty_done']), str(r['qty_scrap']),
                r['status'],
                r['created'].strftime('%Y-%m-%d %H:%M') if r['created'] else '',
            ]
            for col, val in enumerate(cells):
                it = QTableWidgetItem(val)
                if col == 0:
                    it.setData(Qt.ItemDataRole.UserRole, r['id'])
                if r['status_enum'] == WorkOrderStatus.ON_HOLD:
                    it.setBackground(QBrush(QColor(255, 240, 200)))
                elif r['status_enum'] == WorkOrderStatus.DONE:
                    it.setForeground(QBrush(QColor(0, 120, 0)))
                self.table.setItem(row, col, it)
        self.table.resizeColumnsToContents()

    def _selected_wo_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        it = self.table.item(row, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _selected_wo_ids(self) -> list[int]:
        """v8: вернуть ID всех выделенных нарядов (для пачечной печати)."""
        ids: list[int] = []
        seen: set[int] = set()
        for it in self.table.selectedItems():
            if it.column() != 0:
                continue
            wid = it.data(Qt.ItemDataRole.UserRole)
            if isinstance(wid, int) and wid not in seen:
                ids.append(wid)
                seen.add(wid)
        if not ids:
            wid = self._selected_wo_id()
            if wid:
                ids.append(wid)
        return ids

    def _on_dbl(self, row, _col):
        """v7.2: двойной клик по наряду открывает Операционный маршрут.
        Для нарядов в статусе RELEASED предлагается регистрация (как раньше).
        """
        wo_id = self._selected_wo_id()
        if not wo_id:
            return
        with self.db.get_session() as s:
            wo = s.get(WorkOrder, wo_id)
            if wo is None:
                return
            status = wo.status
        if status == WorkOrderStatus.RELEASED:
            # Только что переданный — нужно зарегистрировать
            self._on_register(force=True)
            return
        self._open_route(wo_id)

    def _open_route(self, wo_id: int):
        """Открыть окно операционного маршрута."""
        try:
            from ui.widgets.route_window import RouteWindow
            dlg = RouteWindow(self.db, wo_id, self.user, self)
            dlg.exec()
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Маршрут", f"{e}")

    def _on_route(self):
        """Кнопка «📋 Маршрут» — открыть RouteWindow для выбранного наряда."""
        wo_id = self._selected_wo_id()
        if not wo_id:
            QMessageBox.information(self, 'Маршрут',
                                    'Выберите наряд в таблице.')
            return
        self._open_route(wo_id)

    def _on_mtp_excel(self):
        """v7.5: сгенерировать МТП в Excel по форме УЗГА со штрих-кодом."""
        wo_id = self._selected_wo_id()
        if not wo_id:
            QMessageBox.information(
                self, 'МТП', 'Выберите наряд в таблице.')
            return
        from PyQt6.QtWidgets import (
            QFileDialog,
            QInputDialog,
        )
        from PyQt6.QtWidgets import (
            QMessageBox as MB,
        )
        # Спросим: свернуть промежуточные?
        choices = [
            "Сокращённый (свернуть промывочные/промежуточные контрольные)",
            "Полный (все операции ТП)",
        ]
        choice, ok = QInputDialog.getItem(
            self, 'МТП — режим формирования',
            'Выберите режим:', choices, 0, False)
        if not ok:
            return
        collapse = choice.startswith('Сокр')
        try:
            from modules.mtp_excel import generate_mtp_excel
            with self.db.get_session() as s:
                wo = s.get(WorkOrder, wo_id)
                if not wo:
                    return
                default_name = (
                    f"MTP_{wo.number}_"
                    f"{'compact' if collapse else 'full'}.xlsx"
                )
                # Спрашиваем путь
                path, _ = QFileDialog.getSaveFileName(
                    self, "Сохранить МТП", default_name,
                    "Excel (*.xlsx)")
                if not path:
                    return
                generate_mtp_excel(
                    s,
                    tech_process_id=wo.tech_process_id,
                    work_order_id=wo.id,
                    out_path=path,
                    collapse_intermediate=collapse,
                )
            MB.information(self, 'МТП',
                           f'МТП сохранён:\n{path}')
        except Exception as e:
            QMessageBox.critical(self, 'МТП', f'{e}')

    def _on_mtp_pdf(self):
        """v8: МТП в PDF — для электронного архива (xlsx редактируется)."""
        wo_id = self._selected_wo_id()
        if not wo_id:
            QMessageBox.information(
                self, 'МТП', 'Выберите наряд в таблице.')
            return
        from PyQt6.QtWidgets import (
            QFileDialog,
            QInputDialog,
        )
        from PyQt6.QtWidgets import (
            QMessageBox as MB,
        )
        choices = [
            "Сокращённый (свернуть промежуточные)",
            "Полный (все операции ТП)",
        ]
        choice, ok = QInputDialog.getItem(
            self, 'МТП PDF — режим формирования',
            'Выберите режим:', choices, 0, False)
        if not ok:
            return
        collapse = choice.startswith('Сокр')
        try:
            from modules.mtp_pdf import generate_mtp_pdf
            with self.db.get_session() as s:
                wo = s.get(WorkOrder, wo_id)
                if not wo:
                    return
                default_name = (
                    f"MTP_{wo.number}_"
                    f"{'compact' if collapse else 'full'}.pdf"
                )
                path, _ = QFileDialog.getSaveFileName(
                    self, "Сохранить МТП (PDF)", default_name,
                    "PDF (*.pdf)")
                if not path:
                    return
                generate_mtp_pdf(
                    s,
                    tech_process_id=wo.tech_process_id,
                    work_order_id=wo.id,
                    out_path=path,
                    collapse_intermediate=collapse,
                )
            MB.information(self, 'МТП', f'МТП сохранён:\n{path}')
        except Exception as e:
            QMessageBox.critical(self, 'МТП', f'{e}')

    def _on_mtp_batch(self):
        """v8: пачкой — N xlsx в папку или один многостраничный PDF."""
        ids = self._selected_wo_ids()
        if not ids:
            QMessageBox.information(
                self, 'МТП пачкой',
                'Выделите наряды в таблице (Ctrl/Shift+клик).')
            return
        from PyQt6.QtWidgets import (
            QFileDialog,
            QInputDialog,
        )
        from PyQt6.QtWidgets import (
            QMessageBox as MB,
        )
        fmts = [
            f'PDF — один многостраничный файл ({len(ids)} стр.)',
            f'XLSX — отдельные файлы в папку ({len(ids)} шт.)',
        ]
        fmt, ok = QInputDialog.getItem(
            self, 'Печать пачкой МТП',
            f'Выбрано нарядов: {len(ids)}.\nФормат:',
            fmts, 0, False)
        if not ok:
            return
        modes = [
            "Сокращённый (свернуть промежуточные)",
            "Полный (все операции ТП)",
        ]
        mode, ok = QInputDialog.getItem(
            self, 'МТП пачкой — режим',
            'Выберите режим:', modes, 0, False)
        if not ok:
            return
        collapse = mode.startswith('Сокр')

        try:
            if fmt.startswith('PDF'):
                path, _ = QFileDialog.getSaveFileName(
                    self, 'Сохранить пачку МТП в PDF',
                    f'MTP_batch_{len(ids)}.pdf',
                    'PDF (*.pdf)')
                if not path:
                    return
                from modules.mtp_pdf import generate_mtp_pdf_batch
                with self.db.get_session() as s:
                    generate_mtp_pdf_batch(
                        s, work_order_ids=ids, out_path=path,
                        collapse_intermediate=collapse,
                    )
                MB.information(
                    self, 'МТП пачкой',
                    f'Готово: {path}\nНарядов: {len(ids)}.'
                )
                return

            # XLSX в папку
            from PyQt6.QtWidgets import QFileDialog as _FD
            folder = _FD.getExistingDirectory(
                self, 'Выберите папку для xlsx-файлов', '')
            if not folder:
                return
            from pathlib import Path as _P

            from modules.mtp_excel import generate_mtp_excel
            saved = 0
            errs: list[str] = []
            with self.db.get_session() as s:
                for wid in ids:
                    wo = s.get(WorkOrder, wid)
                    if not wo or wo.tech_process_id is None:
                        errs.append(f'#{wid}: нет ТП')
                        continue
                    fname = (
                        f"MTP_{wo.number}_"
                        f"{'compact' if collapse else 'full'}.xlsx"
                    )
                    out = _P(folder) / fname
                    try:
                        generate_mtp_excel(
                            s, tech_process_id=wo.tech_process_id,
                            work_order_id=wo.id, out_path=str(out),
                            collapse_intermediate=collapse,
                        )
                        saved += 1
                    except Exception as e:
                        errs.append(f'{wo.number}: {e}')
            msg = f'Сохранено файлов: {saved} / {len(ids)} в:\n{folder}'
            if errs:
                msg += '\n\nОшибки:\n' + '\n'.join(errs[:10])
            MB.information(self, 'МТП пачкой', msg)
        except Exception as e:
            QMessageBox.critical(self, 'МТП пачкой', f'{e}')

    def _on_release(self):
        from ui.dialogs.production_dialogs import ReleaseDialog
        dlg = ReleaseDialog(self.db, self.user, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_register(self, force: bool = False):
        from ui.dialogs.production_dialogs import RegisterDialog
        wo_id = self._selected_wo_id()
        if not wo_id:
            QMessageBox.information(self, 'Регистрация',
                                    'Выберите наряд в таблице.')
            return
        with self.db.get_session() as s:
            wo = s.get(WorkOrder, wo_id)
            if wo is None:
                return
            status = wo.status
        if status != WorkOrderStatus.RELEASED and not force:
            QMessageBox.information(
                self, 'Регистрация',
                f'Наряд в статусе «{status.value}» — регистрация не требуется.')
            return
        if status != WorkOrderStatus.RELEASED:
            return
        dlg = RegisterDialog(self.db, self.user, work_order_id=wo_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_cancel(self):
        """Отмена наряда: запрашивает причину и вызывает production.cancel_work_order."""
        wo_id = self._selected_wo_id()
        if not wo_id:
            QMessageBox.information(self, 'Отмена наряда',
                                    'Выберите наряд в таблице.')
            return
        with self.db.get_session() as s:
            wo = s.get(WorkOrder, wo_id)
            if wo is None:
                return
            wo_number = wo.number
            wo_status = wo.status

        if wo_status in (WorkOrderStatus.CANCELED, WorkOrderStatus.DONE):
            QMessageBox.information(
                self, 'Отмена наряда',
                f'Наряд {wo_number} уже в статусе «{wo_status.value}».')
            return

        from ui.dialogs.production_dialogs import CancelWorkOrderDialog
        dlg = CancelWorkOrderDialog(self.db, self.user,
                                    work_order_id=wo_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _on_print_labels(self):
        """Генерирует PDF с штрих-кодами всех партий выбранного наряда."""
        from PyQt6.QtWidgets import QFileDialog

        from modules import barcode_gen

        wo_id = self._selected_wo_id()
        if not wo_id:
            QMessageBox.information(self, 'Печать ярлыков',
                                    'Выберите наряд в таблице.')
            return
        with self.db.get_session() as s:
            wo = s.get(WorkOrder, wo_id)
            if wo is None:
                return
            wo_number = wo.number
            items_count = len(wo.items)
        if items_count == 0:
            QMessageBox.warning(
                self, 'Печать ярлыков',
                'У этого наряда нет партий — сначала зарегистрируйте наряд.')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Сохранить ярлыки PDF',
            f'labels-{wo_number}.pdf',
            'PDF (*.pdf)')
        if not path:
            return
        try:
            with self.db.get_session() as s:
                pdf_bytes = barcode_gen.generate_labels_pdf(s, wo_id)
            with open(path, 'wb') as f:
                f.write(pdf_bytes)
        except barcode_gen.BarcodeError as e:
            QMessageBox.warning(self, 'Печать ярлыков', str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, 'Печать ярлыков',
                                 f'Не удалось сохранить:\n{e}')
            return
        QMessageBox.information(
            self, 'Печать ярлыков',
            f'PDF сохранён: {path}\nПартий: {items_count}.')


# ──────────────────────────────────────────────────────────────────────────
# Вкладка «Партии»
# ──────────────────────────────────────────────────────────────────────────

class ItemsTab(QWidget):
    def __init__(self, db, user, parent=None):
        super().__init__(parent)
        self.db = db
        self.user = user or {}
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel('Сканер / поиск:'))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            'отсканируйте штрих-код или введите серийник партии и нажмите Enter')
        self.search_edit.returnPressed.connect(self._on_scan)
        top.addWidget(self.search_edit, 1)

        top.addSpacing(10)
        top.addWidget(QLabel('Участок:'))
        self.workshop_combo = QComboBox()
        self.workshop_combo.addItem('— все —', userData=None)
        with self.db.get_session() as s:
            for w in (s.query(Workshop)
                      .filter(Workshop.is_active.is_(True))
                      .order_by(Workshop.sort_order, Workshop.id).all()):
                self.workshop_combo.addItem(f'{w.code} — {w.name}',
                                            userData=w.id)
        self.workshop_combo.currentIndexChanged.connect(self.refresh)
        top.addWidget(self.workshop_combo)

        btn = QPushButton('Обновить')
        btn.clicked.connect(self.refresh)
        top.addWidget(btn)
        root.addLayout(top)

        action_bar = QHBoxLayout()
        self.btn_start = QPushButton('Начать операцию')
        self.btn_start.clicked.connect(self._on_start)
        action_bar.addWidget(self.btn_start)

        self.btn_finish = QPushButton('Завершить операцию…')
        self.btn_finish.clicked.connect(self._on_finish)
        action_bar.addWidget(self.btn_finish)

        self.btn_label = QPushButton('Штрих-код / ярлык…')
        self.btn_label.clicked.connect(self._on_label)
        action_bar.addWidget(self.btn_label)

        self.btn_issue = QPushButton('Сообщить о проблеме…')
        self.btn_issue.clicked.connect(self._on_issue)
        action_bar.addWidget(self.btn_issue)

        self.btn_rework = QPushButton('↩ Вернуть на доработку…')
        self.btn_rework.setToolTip(
            'Откатить партию на предыдущую выполненную операцию '
            '(REWORK).')
        self.btn_rework.clicked.connect(self._on_rework)
        action_bar.addWidget(self.btn_rework)

        action_bar.addStretch(1)
        root.addLayout(action_bar)

        if not _can(self.user.get('role'), production.ROLE_MOVE):
            self.btn_start.setEnabled(False)
            self.btn_finish.setEnabled(False)
        if not _can(self.user.get('role'), production.ROLE_REWORK):
            self.btn_rework.setEnabled(False)
            self.btn_rework.setToolTip(
                'Доступно ролям: ' + ', '.join(production.ROLE_REWORK))

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            'Партия', 'Наряд', 'Деталь', 'Кол-во', 'Годных', 'Брак',
            'Участок', 'Текущая операция', 'Статус',
        ])
        _set_table_props(self.table)
        root.addWidget(self.table)

    def refresh(self):
        self.table.setRowCount(0)
        flt_ws = self.workshop_combo.currentData()
        with self.db.get_session() as s:
            q = (s.query(WorkOrderItem)
                 .order_by(WorkOrderItem.id.desc()))
            if flt_ws is not None:
                q = q.filter(WorkOrderItem.current_workshop_id == flt_ws)
            rows = []
            for it in q.limit(500).all():
                wo = it.work_order
                product = wo.product if wo else None
                cur = production._current_step(it)
                rows.append({
                    'id': it.id,
                    'serial': it.serial,
                    'wo_number': wo.number if wo else '—',
                    'product': (
                        f'{product.designation} {product.name}'
                        if product else '—'),
                    'qty': it.qty,
                    'qty_good': it.qty_good or 0,
                    'qty_scrap': it.qty_scrap or 0,
                    'workshop': it.current_workshop.name if it.current_workshop else '—',
                    'op': (f'#{cur.seq} {cur.operation.name}'
                           if cur and cur.operation else '—'),
                    'status': it.status.value,
                })
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = [
                r['serial'], r['wo_number'], r['product'],
                str(r['qty']), str(r['qty_good']), str(r['qty_scrap']),
                r['workshop'], r['op'], r['status'],
            ]
            for col, val in enumerate(cells):
                it = QTableWidgetItem(val)
                if col == 0:
                    it.setData(Qt.ItemDataRole.UserRole, r['id'])
                self.table.setItem(row, col, it)
        self.table.resizeColumnsToContents()

    def _selected_item_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        it = self.table.item(row, 0)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _on_scan(self):
        text = self.search_edit.text().strip()
        if not text:
            return
        # v7.3: сначала пробуем как штрих-код наряда (WorkOrder.barcode/number)
        with self.db.get_session() as s:
            wo = (s.query(WorkOrder)
                  .filter((WorkOrder.barcode == text)
                          | (WorkOrder.number == text)).first())
            if wo is not None:
                wo_id = wo.id
                self.search_edit.clear()
                # Открываем окно операционного маршрута для этого наряда
                try:
                    from ui.widgets.route_window import RouteWindow
                    dlg = RouteWindow(self.db, wo_id, self.user, self)
                    dlg.exec()
                    self.refresh()
                except Exception as e:
                    QMessageBox.critical(self, 'Маршрут', f'{e}')
                return

            # Иначе — как штрих-код партии
            item = (s.query(WorkOrderItem)
                    .filter(WorkOrderItem.barcode == text).first())
            if item is None:
                # затем как серийник
                item = (s.query(WorkOrderItem)
                        .filter(WorkOrderItem.serial == text).first())
            if item is None:
                # затем по id из ATPP-WI-<id>-...
                parsed = production.parse_barcode(text)
                if parsed:
                    item = s.get(WorkOrderItem, parsed)
            if item is None:
                QMessageBox.information(
                    self, 'Сканер',
                    'Не найдено: ни наряд, ни партия по этому коду.\n'
                    'Проверьте штрих-код наряда (WO-…) или партии.')
                return
            item_id = item.id
            workshop_id = item.current_workshop_id
        # Подсветим в таблице если есть, иначе — добавим в фильтр
        if workshop_id is not None:
            for i in range(self.workshop_combo.count()):
                if self.workshop_combo.itemData(i) == workshop_id:
                    self.workshop_combo.setCurrentIndex(i)
                    break
        # Ищем строку в таблице
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 0)
            if it and it.data(Qt.ItemDataRole.UserRole) == item_id:
                self.table.selectRow(row)
                self.table.scrollToItem(it)
                self.search_edit.clear()
                return
        # Не нашли — обновим
        self.refresh()
        for row in range(self.table.rowCount()):
            it = self.table.item(row, 0)
            if it and it.data(Qt.ItemDataRole.UserRole) == item_id:
                self.table.selectRow(row)
                self.table.scrollToItem(it)
                break
        self.search_edit.clear()

    def _on_start(self):
        item_id = self._selected_item_id()
        if not item_id:
            QMessageBox.information(self, 'Старт', 'Выберите партию.')
            return
        try:
            with self.db.get_session() as s:
                production.start_operation(
                    s, user=self.user, item_id=item_id)
        except production.ProductionError as e:
            QMessageBox.warning(self, 'Старт', str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, 'Старт', f'Ошибка: {e}')
            return
        self.refresh()

    def _on_finish(self):
        item_id = self._selected_item_id()
        if not item_id:
            QMessageBox.information(self, 'Завершение', 'Выберите партию.')
            return
        with self.db.get_session() as s:
            item = s.get(WorkOrderItem, item_id)
            if item is None:
                return
            qty = item.qty
            cur = production._current_step(item)

        good, ok = QInputDialog.getInt(
            self, 'Завершение операции',
            f'Сколько годных деталей? (всего {qty})',
            qty, 0, qty, 1)
        if not ok:
            return
        scrap, ok = QInputDialog.getInt(
            self, 'Завершение операции',
            'Сколько в брак?',
            0, 0, qty, 1)
        if not ok:
            return

        # Если есть следующий шаг — спросим, на какой участок передать
        next_workshop_id = None
        with self.db.get_session() as s:
            item = s.get(WorkOrderItem, item_id)
            cur = production._current_step(item)
            has_next = False
            if cur is not None:
                next_step = next(
                    (st for st in item.route_steps
                     if st.seq > cur.seq
                     and st.status == RouteStepStatus.PENDING),
                    None,
                )
                has_next = next_step is not None
        if has_next:
            workshops = []
            with self.db.get_session() as s:
                for w in (s.query(Workshop)
                          .filter(Workshop.is_active.is_(True))
                          .order_by(Workshop.sort_order).all()):
                    workshops.append((w.id, f'{w.code} — {w.name}'))
            labels = ['(оставить тот же участок)'] + [w[1] for w in workshops]
            choice, ok = QInputDialog.getItem(
                self, 'Передача', 'Передать на участок:', labels, 0, False)
            if not ok:
                return
            if choice != labels[0]:
                idx = labels.index(choice) - 1
                next_workshop_id = workshops[idx][0]

        try:
            with self.db.get_session() as s:
                production.finish_operation(
                    s, user=self.user, item_id=item_id,
                    qty_good=good, qty_scrap=scrap,
                    next_workshop_id=next_workshop_id,
                )
        except production.ProductionError as e:
            QMessageBox.warning(self, 'Завершение', str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, 'Завершение', f'Ошибка: {e}')
            return
        self.refresh()

    def _on_label(self):
        from ui.dialogs.production_dialogs import BarcodePreviewDialog
        item_id = self._selected_item_id()
        if not item_id:
            QMessageBox.information(self, 'Штрих-код', 'Выберите партию.')
            return
        BarcodePreviewDialog(self.db, item_id, parent=self).exec()

    def _on_issue(self):
        from ui.dialogs.production_dialogs import IssueDialog
        item_id = self._selected_item_id()
        if not item_id:
            QMessageBox.information(self, 'Проблема', 'Выберите партию.')
            return
        with self.db.get_session() as s:
            item = s.get(WorkOrderItem, item_id)
            if item is None:
                return
            wo_id = item.work_order_id
            workshop_id = item.current_workshop_id
            operation_id = item.current_operation_id
        dlg = IssueDialog(
            self.db, self.user,
            work_order_id=wo_id, work_order_item_id=item_id,
            workshop_id=workshop_id, operation_id=operation_id,
            parent=self,
        )
        dlg.exec()

    def _on_rework(self):
        """Возврат партии на предыдущую операцию (REWORK)."""
        from ui.dialogs.production_dialogs import ReworkDialog
        item_id = self._selected_item_id()
        if not item_id:
            QMessageBox.information(self, 'Доработка', 'Выберите партию.')
            return
        dlg = ReworkDialog(self.db, self.user, item_id=item_id, parent=self)
        if dlg.exec():
            self.refresh()


# ──────────────────────────────────────────────────────────────────────────
# Вкладка «Проблемы»
# ──────────────────────────────────────────────────────────────────────────

class IssuesTab(QWidget):
    def __init__(self, db, user, parent=None):
        super().__init__(parent)
        self.db = db
        self.user = user or {}
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel('Статус:'))
        self.status_combo = QComboBox()
        self.status_combo.addItem('Открытые / принятые', userData='active')
        self.status_combo.addItem('Закрытые', userData='closed')
        self.status_combo.addItem('Все', userData='all')
        self.status_combo.currentIndexChanged.connect(self.refresh)
        bar.addWidget(self.status_combo)

        bar.addStretch(1)

        self.btn_resolve = QPushButton('Закрыть проблему…')
        self.btn_resolve.clicked.connect(self._on_resolve)
        if not _can(self.user.get('role'), production.ROLE_ISSUE_RESOLVE):
            self.btn_resolve.setEnabled(False)
        bar.addWidget(self.btn_resolve)

        btn = QPushButton('Обновить')
        btn.clicked.connect(self.refresh)
        bar.addWidget(btn)

        root.addLayout(bar)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            'Открыта', 'Тип', 'Серьёзность', 'Заголовок',
            'Наряд', 'Участок', 'Блокирует?', 'Статус',
        ])
        _set_table_props(self.table)
        root.addWidget(self.table)

    def refresh(self):
        self.table.setRowCount(0)
        mode = self.status_combo.currentData()
        with self.db.get_session() as s:
            q = (s.query(ProductionIssue)
                 .order_by(ProductionIssue.opened_at.desc()))
            if mode == 'active':
                q = q.filter(ProductionIssue.status.in_(
                    (IssueStatus.OPEN, IssueStatus.ACKNOWLEDGED)))
            elif mode == 'closed':
                q = q.filter(ProductionIssue.status == IssueStatus.RESOLVED)

            rows = []
            for i in q.limit(500).all():
                rows.append({
                    'id': i.id,
                    'opened_at': i.opened_at,
                    'kind': i.kind.value,
                    'severity': i.severity.value,
                    'title': i.title,
                    'wo_number': i.work_order.number if i.work_order else '—',
                    'workshop': i.workshop.name if i.workshop else '—',
                    'blocks': 'Да' if i.blocks_production else '',
                    'status': i.status.value,
                    'is_blocker': i.blocks_production,
                    'is_active': i.status in (IssueStatus.OPEN,
                                              IssueStatus.ACKNOWLEDGED),
                })
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = [
                r['opened_at'].strftime('%Y-%m-%d %H:%M')
                if r['opened_at'] else '',
                r['kind'], r['severity'], r['title'],
                r['wo_number'], r['workshop'], r['blocks'], r['status'],
            ]
            for col, val in enumerate(cells):
                it = QTableWidgetItem(val)
                if col == 0:
                    it.setData(Qt.ItemDataRole.UserRole, r['id'])
                if r['is_blocker'] and r['is_active']:
                    it.setBackground(QBrush(QColor(255, 220, 220)))
                self.table.setItem(row, col, it)
        self.table.resizeColumnsToContents()

    def _on_resolve(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, 'Закрытие', 'Выберите проблему.')
            return
        issue_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        from ui.dialogs.production_dialogs import ResolveIssueDialog
        dlg = ResolveIssueDialog(self.db, self.user, issue_id=issue_id,
                                 parent=self)
        if dlg.exec():
            self.refresh()


# ──────────────────────────────────────────────────────────────────────────
# Вкладка «Сводка / отчёты»
# ──────────────────────────────────────────────────────────────────────────

class SummaryTab(QWidget):
    def __init__(self, db, user, parent=None):
        super().__init__(parent)
        self.db = db
        self.user = user or {}
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        bar = QHBoxLayout()
        btn = QPushButton('Обновить')
        btn.clicked.connect(self.refresh)
        bar.addWidget(btn)
        bar.addStretch(1)
        root.addLayout(bar)

        root.addWidget(QLabel('<b>WIP по участкам</b>'))
        self.wip_table = QTableWidget(0, 5)
        self.wip_table.setHorizontalHeaderLabels([
            'Участок', 'Партий', 'Шт. (всего)', 'В работе', 'Ожидает'])
        _set_table_props(self.wip_table)
        root.addWidget(self.wip_table)

        root.addWidget(QLabel('<b>Открытые проблемы по типам</b>'))
        self.issues_table = QTableWidget(0, 3)
        self.issues_table.setHorizontalHeaderLabels(
            ['Тип', 'Всего', 'Из них блокирующих'])
        _set_table_props(self.issues_table)
        root.addWidget(self.issues_table)

    def refresh(self):
        self.wip_table.setRowCount(0)
        self.issues_table.setRowCount(0)
        with self.db.get_session() as s:
            wip = production.wip_by_workshop(s)
            issues = production.open_issues_summary(s)
        for r in wip:
            row = self.wip_table.rowCount()
            self.wip_table.insertRow(row)
            cells = [
                f'{r["workshop_code"]} — {r["workshop_name"]}',
                str(r['items_count']), str(r['qty_total']),
                str(r['in_progress']), str(r['waiting']),
            ]
            for col, val in enumerate(cells):
                self.wip_table.setItem(row, col, QTableWidgetItem(val))
        self.wip_table.resizeColumnsToContents()
        for r in issues:
            row = self.issues_table.rowCount()
            self.issues_table.insertRow(row)
            for col, val in enumerate([r['kind'],
                                       str(r['count']),
                                       str(r['blockers'])]):
                self.issues_table.setItem(row, col, QTableWidgetItem(val))
        self.issues_table.resizeColumnsToContents()


# ──────────────────────────────────────────────────────────────────────────
# Главный виджет «Производство»
# ──────────────────────────────────────────────────────────────────────────

class ProductionWidget(QWidget):
    """Корневой виджет модуля «Производство»."""

    def __init__(self, db_manager, user, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.user = user or {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.orders_tab = OrdersTab(self.db, self.user)
        self.items_tab = ItemsTab(self.db, self.user)
        self.issues_tab = IssuesTab(self.db, self.user)
        self.summary_tab = SummaryTab(self.db, self.user)
        self.tabs.addTab(self.orders_tab, 'Наряды')
        self.tabs.addTab(self.items_tab, 'Партии (WIP)')
        self.tabs.addTab(self.issues_tab, 'Проблемы')
        self.tabs.addTab(self.summary_tab, 'Сводка')
        root.addWidget(self.tabs)
        # Когда переключаются вкладки — обновляем
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, idx):
        w = self.tabs.widget(idx)
        if hasattr(w, 'refresh'):
            try:
                w.refresh()
            except Exception:
                _logger.exception("Unhandled error")

    def refresh(self):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if hasattr(w, 'refresh'):
                try:
                    w.refresh()
                except Exception:
                    _logger.exception("Unhandled error")
