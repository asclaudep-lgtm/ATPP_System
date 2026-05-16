"""
Theme & appearance settings dialog — Fluent Design.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QSpinBox,
    QHBoxLayout, QDialogButtonBox, QMessageBox,
)

from modules import settings
from ui.theme import apply_theme
from ui.fluent_compat import BodyLabel, PrimaryPushButton, PushButton


class AppearanceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки внешнего вида")
        self.setMinimumWidth(440)

        lay = QVBoxLayout(self)
        lay.setSpacing(16)
        lay.setContentsMargins(24, 20, 24, 20)

        form = QFormLayout()
        form.setSpacing(12)

        self.theme_cmb = QComboBox()
        self.theme_cmb.addItem("Светлая", "light")
        self.theme_cmb.addItem("Тёмная", "dark")
        cur_theme = settings.get("theme", "light")
        idx = self.theme_cmb.findData(cur_theme)
        if idx >= 0:
            self.theme_cmb.setCurrentIndex(idx)
        form.addRow("Тема:", self.theme_cmb)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(7, 18)
        self.font_spin.setValue(int(settings.get("font_size", 9) or 9))
        self.font_spin.setSuffix(" pt")
        form.addRow("Размер шрифта:", self.font_spin)

        self.lang_cmb = QComboBox()
        self.lang_cmb.addItem("Русский", "ru")
        self.lang_cmb.addItem("English (in progress)", "en")
        cur_lang = settings.get("language", "ru")
        idx = self.lang_cmb.findData(cur_lang)
        if idx >= 0:
            self.lang_cmb.setCurrentIndex(idx)
        form.addRow("Язык интерфейса:", self.lang_cmb)

        self.step_spin = QSpinBox()
        self.step_spin.setRange(1, 100)
        self.step_spin.setValue(int(settings.get("op_number_step", 5) or 5))
        form.addRow("Шаг номеров операций:", self.step_spin)

        self.pad_spin = QSpinBox()
        self.pad_spin.setRange(0, 6)
        self.pad_spin.setValue(int(settings.get("op_number_pad", 3) or 0))
        self.pad_spin.setToolTip("0 — без ведущих нулей. 3 — формат «005», «010».")
        form.addRow("Формат (ведущие нули):", self.pad_spin)

        lay.addLayout(form)

        hint = BodyLabel(
            "Тема и размер шрифта применяются сразу.\n"
            "Смена языка вступает в силу после перезапуска приложения."
        )
        lay.addWidget(hint)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = PushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = PrimaryPushButton("OK")
        ok_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(ok_btn)
        lay.addLayout(btn_layout)

    def _on_accept(self):
        theme = self.theme_cmb.currentData()
        font_size = int(self.font_spin.value())
        lang = self.lang_cmb.currentData()
        step = int(self.step_spin.value())
        pad = int(self.pad_spin.value())

        settings.set("theme", theme)
        settings.set("font_size", font_size)
        settings.set("language", lang)
        settings.set("op_number_step", step)
        settings.set("op_number_pad", pad)

        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                apply_theme(app, theme=theme, font_size=font_size)
        except Exception:
            pass

        if lang != settings.get("language"):
            QMessageBox.information(
                self, "Язык интерфейса",
                "Изменение языка вступит в силу после перезапуска.",
            )
        self.accept()
