"""Диалоги модуля «Производство».

- ReleaseDialog: технолог передаёт ТП в производство (создаёт WorkOrder).
- RegisterDialog: мастер регистрирует наряд, разбивая его на партии.
- IssueDialog:   ввод проблемы (нет материала / инструмента / КД и т.п.).
- ResolveIssueDialog: закрытие проблемы.
- BarcodePreviewDialog: показывает штрих-код партии.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QTextEdit, QVBoxLayout,
)

from database.models import (
    IssueKind, IssueSeverity, ProductionIssue, RouteStepStatus, TechProcess,
    User, Workshop, WorkOrder, WorkOrderItem,
)


class ReleaseDialog(QDialog):
    """Технолог: «Передать ТП в производство»."""

    def __init__(self, db_manager, current_user, parent=None,
                 default_tp_id: Optional[int] = None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.default_tp_id = default_tp_id
        self.created_wo_id: Optional[int] = None

        self.setWindowTitle('Передать ТП в производство')
        self.setMinimumWidth(480)
        self._build()
        self._load_tps()

    def _build(self):
        form = QFormLayout()

        self.tp_combo = QComboBox()
        form.addRow('Технологический процесс:', self.tp_combo)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 1_000_000)
        self.qty_spin.setValue(1)
        form.addRow('Количество (всего, шт.):', self.qty_spin)

        self.order_edit = QLineEdit()
        self.order_edit.setPlaceholderText('например, ORD-2025-001')
        form.addRow('Заказ (опц.):', self.order_edit)

        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(0, 9)
        self.priority_spin.setValue(0)
        self.priority_spin.setToolTip('0 — обычный, 9 — срочный')
        form.addRow('Приоритет:', self.priority_spin)

        self.due_edit = QDateEdit()
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setSpecialValueText(' — ')
        self.due_edit.setDate(self.due_edit.minimumDate())
        form.addRow('Срок (опц.):', self.due_edit)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        form.addRow('Примечание:', self.notes_edit)

        layout = QVBoxLayout(self)
        layout.addLayout(form)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText('Передать')
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _load_tps(self):
        with self.db_manager.get_session() as s:
            tps = (s.query(TechProcess)
                   .filter(TechProcess.is_deleted.is_(False))
                   .order_by(TechProcess.number).all())
            self.tp_combo.clear()
            for tp in tps:
                product = tp.product.designation if tp.product else '—'
                self.tp_combo.addItem(
                    f'{tp.number}  ({product}) — {tp.status.value}',
                    userData=tp.id,
                )
                if self.default_tp_id and tp.id == self.default_tp_id:
                    self.tp_combo.setCurrentIndex(self.tp_combo.count() - 1)

    def _on_ok(self):
        from modules import production
        tp_id = self.tp_combo.currentData()
        if not tp_id:
            QMessageBox.warning(self, 'Передача в производство',
                                'Выберите технологический процесс.')
            return
        due = self.due_edit.date().toPyDate()
        if due == self.due_edit.minimumDate().toPyDate():
            due = None
        try:
            with self.db_manager.get_session() as s:
                wo = production.release_to_production(
                    s, user=self.current_user,
                    tech_process_id=tp_id,
                    qty_total=self.qty_spin.value(),
                    customer_order=self.order_edit.text().strip() or None,
                    priority=self.priority_spin.value(),
                    due_date=due,
                    notes=self.notes_edit.toPlainText().strip() or None,
                )
                s.flush()
                self.created_wo_id = wo.id
                wo_number = wo.number
        except production.ProductionError as e:
            QMessageBox.warning(self, 'Передача в производство', str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, 'Передача в производство',
                                 f'Не удалось создать наряд:\n{e}')
            return
        QMessageBox.information(
            self, 'Передача в производство',
            f'Наряд {wo_number} создан и передан в производство.\n'
            f'Теперь мастер участка должен зарегистрировать его.',
        )
        self.accept()


class RegisterDialog(QDialog):
    """Мастер: регистрация наряда (разбивка на партии)."""

    def __init__(self, db_manager, current_user, work_order_id: int,
                 parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.work_order_id = work_order_id
        self.created_items: list[int] = []

        self.setWindowTitle('Регистрация наряда')
        self.setMinimumWidth(520)
        self._build()
        self._load()

    def _build(self):
        form = QFormLayout()
        self.info_lbl = QLabel('—')
        self.info_lbl.setWordWrap(True)
        form.addRow('Наряд:', self.info_lbl)

        self.workshop_combo = QComboBox()
        form.addRow('Начальный участок:', self.workshop_combo)

        self.split_edit = QLineEdit()
        self.split_edit.setPlaceholderText(
            'оставьте пустым — одна партия; '
            'пример: 50,50  или  1,1,1,1 …')
        form.addRow('Разбивка партий:', self.split_edit)

        self.help_lbl = QLabel(
            'Сумма размеров партий должна совпадать с количеством наряда.\n'
            'Каждой партии будет выдан штрих-код Code128.')
        self.help_lbl.setStyleSheet('color: gray;')

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.help_lbl)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText('Зарегистрировать')
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _load(self):
        with self.db_manager.get_session() as s:
            wo = s.query(WorkOrder).get(self.work_order_id)
            if wo is None:
                self.info_lbl.setText('Наряд не найден.')
                return
            tp = wo.tech_process
            product = tp.product if tp else None
            self.info_lbl.setText(
                f'<b>{wo.number}</b> · {wo.qty_total} шт.<br>'
                f'ТП {tp.number if tp else "—"}, '
                f'деталь: {product.designation if product else "—"}'
            )
            self.split_edit.setText(str(wo.qty_total))

            wss = (s.query(Workshop)
                   .filter(Workshop.is_active.is_(True))
                   .order_by(Workshop.sort_order, Workshop.id).all())
            for w in wss:
                self.workshop_combo.addItem(f'{w.code} — {w.name}',
                                            userData=w.id)

    def _parse_split(self, text: str) -> Optional[list[int]]:
        text = text.strip()
        if not text:
            return None
        try:
            sizes = [int(x.strip()) for x in text.replace(';', ',').split(',')
                     if x.strip()]
        except ValueError:
            raise ValueError('Размеры партий должны быть целыми числами через запятую.')
        if any(s <= 0 for s in sizes):
            raise ValueError('Каждый размер партии должен быть > 0.')
        return sizes

    def _on_ok(self):
        from modules import production
        try:
            sizes = self._parse_split(self.split_edit.text())
        except ValueError as e:
            QMessageBox.warning(self, 'Регистрация', str(e))
            return
        ws_id = self.workshop_combo.currentData()
        if not ws_id:
            QMessageBox.warning(self, 'Регистрация',
                                'Выберите начальный участок.')
            return
        try:
            with self.db_manager.get_session() as s:
                items = production.register_work_order(
                    s, user=self.current_user,
                    work_order_id=self.work_order_id,
                    initial_workshop_id=ws_id,
                    split_into=sizes,
                )
                s.flush()
                self.created_items = [i.id for i in items]
                count = len(items)
        except production.ProductionError as e:
            QMessageBox.warning(self, 'Регистрация', str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, 'Регистрация',
                                 f'Не удалось зарегистрировать:\n{e}')
            return
        QMessageBox.information(
            self, 'Регистрация',
            f'Создано партий: {count}.\n'
            f'Партии находятся на начальном участке. Откройте список '
            f'партий и распечатайте ярлыки.',
        )
        self.accept()


class IssueDialog(QDialog):
    """Открытие проблемы в производстве."""

    def __init__(self, db_manager, current_user, work_order_id: int,
                 work_order_item_id: Optional[int] = None,
                 workshop_id: Optional[int] = None,
                 operation_id: Optional[int] = None,
                 parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.work_order_id = work_order_id
        self.work_order_item_id = work_order_item_id
        self.workshop_id = workshop_id
        self.operation_id = operation_id
        self.created_issue_id: Optional[int] = None

        self.setWindowTitle('Проблема в производстве')
        self.setMinimumWidth(520)
        self._build()

    def _build(self):
        form = QFormLayout()

        self.kind_combo = QComboBox()
        for k in IssueKind:
            self.kind_combo.addItem(k.value, userData=k)
        form.addRow('Тип проблемы:', self.kind_combo)

        self.severity_combo = QComboBox()
        for sev in IssueSeverity:
            self.severity_combo.addItem(sev.value, userData=sev)
        self.severity_combo.setCurrentIndex(1)  # MEDIUM
        form.addRow('Серьёзность:', self.severity_combo)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText('Кратко: что не так')
        form.addRow('Заголовок:', self.title_edit)

        self.descr_edit = QPlainTextEdit()
        self.descr_edit.setPlaceholderText(
            'Подробности (опц.): какой материал/инструмент, что в КД '
            'непонятно и т.п.')
        self.descr_edit.setMaximumHeight(100)
        form.addRow('Описание:', self.descr_edit)

        self.assignee_combo = QComboBox()
        self.assignee_combo.addItem('— не назначено —', userData=None)
        with self.db_manager.get_session() as s:
            users = (s.query(User)
                     .filter(User.is_active.is_(True))
                     .order_by(User.full_name).all())
            for u in users:
                label = f'{u.full_name or u.username} [{u.role}]'
                self.assignee_combo.addItem(label, userData=u.id)
        form.addRow('Ответственный:', self.assignee_combo)

        self.blocks_chk = QCheckBox('Блокирует производство (наряд → ON_HOLD)')
        form.addRow('', self.blocks_chk)

        layout = QVBoxLayout(self)
        layout.addLayout(form)

        # A5: фотографии — пока issue не создан, виджет работает в pending-режиме
        from ui.widgets.issue_photos_widget import IssuePhotosWidget
        self.photos_widget = IssuePhotosWidget(
            self.db_manager, self.current_user, issue_id=None, parent=self)
        layout.addWidget(self.photos_widget)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText('Открыть проблему')
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _on_ok(self):
        from modules import production
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, 'Проблема',
                                'Укажите краткий заголовок.')
            return
        try:
            with self.db_manager.get_session() as s:
                issue = production.open_issue(
                    s, user=self.current_user,
                    work_order_id=self.work_order_id,
                    work_order_item_id=self.work_order_item_id,
                    workshop_id=self.workshop_id,
                    operation_id=self.operation_id,
                    kind=self.kind_combo.currentData(),
                    severity=self.severity_combo.currentData(),
                    title=self.title_edit.text(),
                    description=self.descr_edit.toPlainText().strip() or None,
                    assignee_id=self.assignee_combo.currentData(),
                    blocks_production=self.blocks_chk.isChecked(),
                )
                s.flush()
                self.created_issue_id = issue.id
        except production.ProductionError as e:
            QMessageBox.warning(self, 'Проблема', str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, 'Проблема',
                                 f'Не удалось сохранить:\n{e}')
            return
        # A5: после создания issue — переносим pending-фотографии
        try:
            self.photos_widget.flush_pending(self.created_issue_id)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, 'Фото',
                                f'Issue создан, но фото не сохранены:\n{e}')
        self.accept()


class ResolveIssueDialog(QDialog):
    """Закрытие проблемы с указанием, как именно её решили."""

    def __init__(self, db_manager, current_user, issue_id: int, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.issue_id = issue_id

        self.setWindowTitle('Закрыть проблему')
        self.setMinimumWidth(480)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        self.info_lbl = QLabel('—')
        self.info_lbl.setWordWrap(True)
        layout.addWidget(self.info_lbl)

        # A5: показываем фотографии, прикреплённые к проблеме (можно
        # дополнить новыми прямо при закрытии).
        from ui.widgets.issue_photos_widget import IssuePhotosWidget
        self.photos_widget = IssuePhotosWidget(
            self.db_manager, self.current_user,
            issue_id=self.issue_id, parent=self)
        layout.addWidget(self.photos_widget)

        layout.addWidget(QLabel('Как проблема была решена:'))
        self.resolution_edit = QPlainTextEdit()
        layout.addWidget(self.resolution_edit)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText('Закрыть')
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _load(self):
        with self.db_manager.get_session() as s:
            issue = s.query(ProductionIssue).get(self.issue_id)
            if issue is None:
                self.info_lbl.setText('Проблема не найдена.')
                return
            self.info_lbl.setText(
                f'<b>[{issue.kind.value}] {issue.title}</b><br>'
                f'Серьёзность: {issue.severity.value}<br>'
                f'Открыта: {issue.opened_at:%Y-%m-%d %H:%M}<br>'
                f'{issue.description or ""}'
            )

    def _on_ok(self):
        from modules import production
        text = self.resolution_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, 'Закрытие',
                                'Опишите, как проблема была решена.')
            return
        try:
            with self.db_manager.get_session() as s:
                production.resolve_issue(
                    s, user=self.current_user,
                    issue_id=self.issue_id, resolution=text,
                )
        except production.ProductionError as e:
            QMessageBox.warning(self, 'Закрытие', str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, 'Закрытие', f'Ошибка: {e}')
            return
        self.accept()


class BarcodePreviewDialog(QDialog):
    """Просмотр и сохранение штрих-кода партии."""

    def __init__(self, db_manager, item_id: int, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.item_id = item_id
        self.setWindowTitle('Штрих-код партии')
        self.setMinimumWidth(500)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        self.info_lbl = QLabel('—')
        self.info_lbl.setWordWrap(True)
        layout.addWidget(self.info_lbl)
        self.image_lbl = QLabel('(штрих-код)')
        self.image_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_lbl)
        bar = QHBoxLayout()
        save_btn = QPushButton('Сохранить PNG…')
        save_btn.clicked.connect(self._save_png)
        bar.addWidget(save_btn)
        bar.addStretch(1)
        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(self.accept)
        bar.addWidget(close_btn)
        layout.addLayout(bar)
        self._png_data: Optional[bytes] = None

    def _load(self):
        from modules import barcode_gen
        with self.db_manager.get_session() as s:
            item = s.query(WorkOrderItem).get(self.item_id)
            if item is None:
                self.info_lbl.setText('Партия не найдена.')
                return
            text = barcode_gen.label_text(item)
            barcode_value = item.barcode
        try:
            png = barcode_gen.generate_png(barcode_value)
        except barcode_gen.BarcodeError as e:
            self.info_lbl.setText(f'<span style="color:red;">{e}</span>')
            return
        self._png_data = png
        pix = QPixmap()
        pix.loadFromData(png)
        self.image_lbl.setPixmap(pix)
        self.info_lbl.setText(f'<pre>{text}</pre><b>{barcode_value}</b>')

    def _save_png(self):
        if not self._png_data:
            QMessageBox.warning(self, 'Сохранение', 'Штрих-код не сгенерирован.')
            return
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, 'Сохранить штрих-код', 'barcode.png',
            'PNG (*.png)')
        if not path:
            return
        with open(path, 'wb') as f:
            f.write(self._png_data)
        QMessageBox.information(self, 'Сохранение', f'Сохранено: {path}')


# ──────────────────────────────────────────────────────────────────────────
# Возврат партии на доработку (REWORK)
# ──────────────────────────────────────────────────────────────────────────

class ReworkDialog(QDialog):
    """Возврат партии на предыдущую операцию.

    Показывает партию и список выполненных операций. Пользователь выбирает,
    на какую именно операцию вернуть партию (по умолчанию — на ближайшую
    предыдущую DONE) и обязательно указывает причину.
    """

    def __init__(self, db_manager, current_user, item_id: int, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.item_id = item_id

        self.setWindowTitle('Возврат партии на доработку')
        self.setMinimumWidth(540)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)

        self.info_lbl = QLabel('—')
        self.info_lbl.setWordWrap(True)
        layout.addWidget(self.info_lbl)

        form = QFormLayout()
        self.target_combo = QComboBox()
        form.addRow('Вернуть на операцию:', self.target_combo)
        layout.addLayout(form)

        layout.addWidget(QLabel('Причина возврата на доработку *:'))
        self.reason_edit = QPlainTextEdit()
        self.reason_edit.setPlaceholderText(
            'Например: на ОТК выявлено отклонение по размеру, '
            'требуется повторная обработка на токарной операции')
        self.reason_edit.setMaximumHeight(110)
        layout.addWidget(self.reason_edit)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText('Вернуть на доработку')
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _load(self):
        with self.db_manager.get_session() as s:
            item = s.query(WorkOrderItem).get(self.item_id)
            if item is None:
                self.info_lbl.setText('Партия не найдена.')
                return
            wo = item.work_order
            self.info_lbl.setText(
                f'<b>Партия {item.serial}</b> · {item.qty} шт.<br>'
                f'Наряд: {wo.number if wo else "—"}<br>'
                f'Текущий статус: {item.status.value}'
            )
            done_steps = sorted(
                (s for s in item.route_steps
                 if s.status == RouteStepStatus.DONE),
                key=lambda x: x.seq,
            )
            for st in done_steps:
                op = st.operation
                ws = st.workshop
                label = f'#{st.seq} {op.name if op else "—"}'
                if ws:
                    label += f' ({ws.code})'
                self.target_combo.addItem(label, userData=st.seq)
        if self.target_combo.count():
            # По умолчанию — последняя выполненная (ближайший откат назад).
            self.target_combo.setCurrentIndex(self.target_combo.count() - 1)

    def _on_ok(self):
        from modules import production
        reason = self.reason_edit.toPlainText().strip()
        if not reason:
            QMessageBox.warning(
                self, 'Доработка',
                'Укажите причину возврата на доработку.')
            return
        target_seq = self.target_combo.currentData()
        try:
            with self.db_manager.get_session() as s:
                production.rework_partition(
                    s, user=self.current_user,
                    item_id=self.item_id, reason=reason,
                    target_seq=target_seq,
                )
        except production.ProductionError as e:
            QMessageBox.warning(self, 'Доработка', str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, 'Доработка',
                                 f'Не удалось вернуть партию:\n{e}')
            return
        self.accept()


# ──────────────────────────────────────────────────────────────────────────
# Отмена наряда
# ──────────────────────────────────────────────────────────────────────────

class CancelWorkOrderDialog(QDialog):
    """Отмена наряда с обязательным комментарием.

    Показывает текущее состояние наряда (статус, выработка) и просит
    указать причину отмены — без неё кнопка «Отменить наряд» не работает.
    """

    def __init__(self, db_manager, current_user, work_order_id: int,
                 parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user
        self.work_order_id = work_order_id
        self.canceled = False

        self.setWindowTitle('Отмена наряда')
        self.setMinimumWidth(520)
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        self.info_lbl = QLabel('—')
        self.info_lbl.setWordWrap(True)
        layout.addWidget(self.info_lbl)

        warn = QLabel(
            '<span style="color:#c0392b;">'
            '⚠ Наряд будет отменён. Все незавершённые партии получат статус '
            '«Брак», их шаги — «Пропущена». Уже изготовленные годные '
            'детали остаются учтёнными в наряде.</span>'
        )
        warn.setWordWrap(True)
        layout.addWidget(warn)

        layout.addWidget(QLabel('Причина отмены *:'))
        self.reason_edit = QPlainTextEdit()
        self.reason_edit.setPlaceholderText(
            'Например: заказ снят клиентом / приоритет изменён / '
            'обнаружена ошибка в КД')
        self.reason_edit.setMaximumHeight(120)
        layout.addWidget(self.reason_edit)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText('Отменить наряд')
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText('Не отменять')
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def _load(self):
        with self.db_manager.get_session() as s:
            wo = s.query(WorkOrder).get(self.work_order_id)
            if wo is None:
                self.info_lbl.setText('Наряд не найден.')
                return
            tp = wo.tech_process
            product = wo.product
            in_progress = sum(1 for it in wo.items
                              if it.status.name == 'IN_PROGRESS')
            self.info_lbl.setText(
                f'<b>{wo.number}</b> · ТП {tp.number if tp else "—"}<br>'
                f'Деталь: {product.designation if product else "—"} '
                f'{product.name if product else ""}<br>'
                f'Статус: {wo.status.value}<br>'
                f'Партий: {len(wo.items)} · в работе: {in_progress} · '
                f'годных: {wo.qty_done or 0} / {wo.qty_total} · '
                f'брак: {wo.qty_scrap or 0}'
            )

    def _on_ok(self):
        from modules import production
        reason = self.reason_edit.toPlainText().strip()
        if not reason:
            QMessageBox.warning(self, 'Отмена наряда',
                                'Укажите причину отмены наряда.')
            return
        try:
            with self.db_manager.get_session() as s:
                production.cancel_work_order(
                    s, user=self.current_user,
                    work_order_id=self.work_order_id,
                    reason=reason,
                )
                self.canceled = True
        except production.ProductionError as e:
            QMessageBox.warning(self, 'Отмена наряда', str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, 'Отмена наряда',
                                 f'Не удалось отменить наряд:\n{e}')
            return
        self.accept()
