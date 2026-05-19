"""
Диалог подтверждения регистрации в едином журнале ТП/МТП.

Используется при создании нового изделия и при создании
варианта ТП. Пользователь может:
- зарегистрировать сразу (auto-номер)
- задать номера вручную
- отказаться от регистрации (но запись будет создана с
  excluded=True если установить флаг «Записать как исключённую»)
"""
from __future__ import annotations

from typing import Optional, Dict, Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QDialogButtonBox, QGroupBox, QPlainTextEdit,
    QComboBox,
)

import logging
_logger = logging.getLogger(__name__)


class JournalRegisterDialog(QDialog):
    """Диалог подтверждения регистрации в журнале.

    Параметры конструктора:
        db_manager      — менеджер БД (для генерации следующего номера)
        title           — заголовок диалога ("Регистрация изделия", и т.д.)
        prompt          — большая надпись сверху
        defaults        — словарь со значениями по умолчанию для полей
        is_variant      — True если регистрируем вариант (показать флажок
                          «Это вариант — записать в журнал отдельной строкой»)
        register_default — Кнопка по умолчанию: True (Зарегистрировать) или
                          False (Не регистрировать)
    """

    def __init__(self, db_manager, title: str, prompt: str,
                 defaults: Optional[Dict[str, Any]] = None,
                 is_variant: bool = False,
                 register_default: bool = True,
                 parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.defaults = defaults or {}
        self.is_variant = is_variant
        self.register_default = register_default

        self.setWindowTitle(title)
        self.setMinimumWidth(560)

        self._result_data: Optional[Dict[str, Any]] = None
        self._build_ui(prompt)
        self._fill_defaults()
        # Если в defaults уже задан tp_number — не перезатирать
        if not (defaults or {}).get('tp_number'):
            self._suggest_numbers()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self, prompt: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 10)

        lbl = QLabel(prompt)
        lbl.setWordWrap(True)
        lbl.setStyleSheet('font-size: 13px; padding: 0 0 6px 0;')
        root.addWidget(lbl)

        # ── Что регистрируем ───────────────────────────────────
        ids_box = QGroupBox('Номера для регистрации')
        ids_layout = QFormLayout(ids_box)
        ids_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.tp_chk = QCheckBox('Регистрировать в журнале ТП')
        self.tp_chk.setChecked(True)
        self.tp_chk.toggled.connect(self._on_kind_changed)
        ids_layout.addRow(self.tp_chk)

        self.tp_in = QLineEdit()
        self.tp_in.setPlaceholderText('УЗГА.02101.NNNNN')
        ids_layout.addRow('Номер ТП:', self.tp_in)

        self.mtp_chk = QCheckBox('Регистрировать в журнале МТП')
        self.mtp_chk.setChecked(True)
        self.mtp_chk.toggled.connect(self._on_kind_changed)
        ids_layout.addRow(self.mtp_chk)

        self.mtp_in = QLineEdit()
        self.mtp_in.setPlaceholderText('УЗГА.02101.NNNNN '
                                       '(обычно совпадает с № ТП)')
        ids_layout.addRow('Номер МТП:', self.mtp_in)

        self.same_chk = QCheckBox('Использовать одинаковый номер для ТП и МТП')
        self.same_chk.setChecked(True)
        self.same_chk.toggled.connect(self._on_same_toggled)
        ids_layout.addRow(self.same_chk)

        suggest_btn = QPushButton('Предложить следующий номер')
        suggest_btn.clicked.connect(self._suggest_numbers)
        ids_layout.addRow(suggest_btn)

        root.addWidget(ids_box)

        # ── Атрибуты записи ───────────────────────────────────
        attr_box = QGroupBox('Атрибуты записи')
        attr = QFormLayout(attr_box)
        attr.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.executor_in = QLineEdit()
        self.executor_in.setPlaceholderText('ФИО исполнителя')
        attr.addRow('Исполнитель:', self.executor_in)

        self.product_type_in = QLineEdit()
        self.product_type_in.setPlaceholderText(
            'тип самолёта / номер машины (для МТП)')
        attr.addRow('Тип изделия:', self.product_type_in)

        self.project_in = QLineEdit()
        self.project_in.setPlaceholderText('например, Ремонт; '
                                           'Серия 1; Опытный экз.')
        attr.addRow('Проект:', self.project_in)

        self.notes_in = QPlainTextEdit()
        self.notes_in.setMaximumHeight(60)
        self.notes_in.setPlaceholderText('Примечание')
        attr.addRow('Примечание:', self.notes_in)

        root.addWidget(attr_box)

        # ── Опции ─────────────────────────────────────────────
        opt_box = QGroupBox('Опции')
        opt_layout = QVBoxLayout(opt_box)
        self.exclude_chk = QCheckBox(
            'Записать сразу как исключённую (видна в журнале, '
            'но не попадает в выгрузки)')
        self.exclude_chk.setToolTip(
            'Полезно если запись надо оставить в истории, но '
            'не печатать в текущем журнале.')
        opt_layout.addWidget(self.exclude_chk)

        if self.is_variant:
            note = QLabel(
                '⚠ Это вариант исполнения существующего изделия. '
                'Если вариант технически отличается — стоит регистрировать '
                'отдельной строкой. Если это просто другая редакция того же '
                'ТП — можно нажать «Не регистрировать» и оставить '
                'изначальную запись.')
            note.setWordWrap(True)
            note.setStyleSheet('color: #b58900; padding-top: 4px;')
            opt_layout.addWidget(note)

        root.addWidget(opt_box)

        # ── Кнопки ───────────────────────────────────────────
        btns_row = QHBoxLayout()
        btns_row.addStretch(1)

        self.skip_btn = QPushButton('Не регистрировать')
        self.skip_btn.clicked.connect(self._on_skip)
        btns_row.addWidget(self.skip_btn)

        self.ok_btn = QPushButton('✓ Зарегистрировать')
        self.ok_btn.setDefault(True)
        self.ok_btn.setStyleSheet(
            'background:#27ae60; color:white; padding:6px 14px;'
            'font-weight:bold;')
        self.ok_btn.clicked.connect(self._on_register)
        btns_row.addWidget(self.ok_btn)

        cancel_btn = QPushButton('Отмена')
        cancel_btn.clicked.connect(self.reject)
        btns_row.addWidget(cancel_btn)

        root.addLayout(btns_row)

        if not self.register_default:
            self.skip_btn.setDefault(True)
            self.ok_btn.setDefault(False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _fill_defaults(self):
        d = self.defaults
        self.tp_in.setText(d.get('tp_number', '') or '')
        self.mtp_in.setText(d.get('mtp_number', '') or '')
        self.executor_in.setText(d.get('executor', '') or '')
        self.product_type_in.setText(d.get('product_type', '') or '')
        self.project_in.setText(d.get('project', '') or '')
        self.notes_in.setPlainText(d.get('notes', '') or '')

    def _on_kind_changed(self):
        # ТП-номер — обязателен только если хотя бы один журнал отмечен
        any_on = self.tp_chk.isChecked() or self.mtp_chk.isChecked()
        self.ok_btn.setEnabled(any_on)

    def _on_same_toggled(self, on: bool):
        self.mtp_in.setEnabled(not on)
        if on:
            self.mtp_in.setText(self.tp_in.text().strip())
        # синхронно обновлять при печати
        try:
            self.tp_in.textChanged.disconnect(self._sync_mtp)
        except Exception:
            _logger.exception("Unhandled error")
        if on:
            self.tp_in.textChanged.connect(self._sync_mtp)

    def _sync_mtp(self, text: str):
        if self.same_chk.isChecked():
            self.mtp_in.setText(text)

    def _suggest_numbers(self):
        try:
            from modules.journal import next_number
            with self.db.get_session() as s:
                nx = next_number(s)
            self.tp_in.setText(nx)
            if self.same_chk.isChecked():
                self.mtp_in.setText(nx)
        except Exception:
            _logger.exception("Unhandled error")

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def _on_skip(self):
        self._result_data = None
        self.done(QDialog.DialogCode.Rejected)

    def _on_register(self):
        tp_number = self.tp_in.text().strip()
        mtp_number = self.mtp_in.text().strip()
        if self.same_chk.isChecked():
            mtp_number = tp_number
        # Валидация: хотя бы один из чекбоксов должен быть отмечен
        if not (self.tp_chk.isChecked() or self.mtp_chk.isChecked()):
            return
        # Если ТП-журнал отмечен — нужен tp_number
        if self.tp_chk.isChecked() and not tp_number:
            return
        if self.mtp_chk.isChecked() and not mtp_number:
            return

        self._result_data = {
            'tp_number': tp_number,
            'mtp_number': mtp_number,
            'in_tp': self.tp_chk.isChecked(),
            'in_mtp': self.mtp_chk.isChecked(),
            'executor': self.executor_in.text().strip(),
            'product_type': self.product_type_in.text().strip(),
            'project': self.project_in.text().strip(),
            'notes': self.notes_in.toPlainText().strip(),
            'excluded': self.exclude_chk.isChecked(),
        }
        self.accept()

    def get_data(self) -> Optional[Dict[str, Any]]:
        return self._result_data
