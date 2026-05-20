"""
v8: Быстрая модалка глобального поиска (Ctrl+P).

Обёртка над ``GlobalSearchWidget`` в формате модального диалога: поле
ввода в фокусе, Enter — искать, Esc — закрыть. Двойной клик по строке
закрывает диалог и эмиттит ``tp_open(tp_id)`` в главное окно.

Это не заменяет вкладку «Глобальный поиск» из меню Сервис — там полный
постоянный виджет с прокруткой и фильтрами. Здесь — быстрый «прыжок».
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QDialog, QVBoxLayout

from ui.widgets.global_search import GlobalSearchWidget

_logger = logging.getLogger(__name__)
class GlobalSearchDialog(QDialog):
    """Поп-ап глобального поиска (Ctrl+P)."""

    tp_open = pyqtSignal(int)

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager

        self.setWindowTitle('Поиск (Ctrl+P)')
        self.setModal(True)
        self.resize(900, 520)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._widget = GlobalSearchWidget(db_manager, parent=self)
        self._widget.tp_open.connect(self._on_tp_open)
        lay.addWidget(self._widget)

        # Esc закрывает диалог.
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.reject)

        # Фокусируем поле ввода сразу же.
        try:
            self._widget.q_in.setFocus()
            self._widget.q_in.selectAll()
        except Exception:
            _logger.exception("Unhandled error")

    def _on_tp_open(self, tp_id: int):
        # Эмиттим наружу и закрываем диалог — открытие ТП произойдёт в
        # главном окне.
        self.tp_open.emit(int(tp_id))
        self.accept()
