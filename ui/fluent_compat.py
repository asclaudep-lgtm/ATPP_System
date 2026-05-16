"""
Совместимый слой Fluent Design для постепенной миграции виджетов.

Использование:
    from ui.fluent_compat import (
        PushButton,           # вместо QPushButton
        PrimaryPushButton,    # для главной кнопки формы
        LineEdit,             # вместо QLineEdit
        PasswordLineEdit,     # пароль с иконкой-глазом
        ComboBox, CheckBox, RadioButton, SwitchButton,
        BodyLabel, SubtitleLabel, TitleLabel,
        FluentIcon, InfoBar, InfoBarPosition,
    )

Если установлен ``qfluentwidgets`` — импортируются настоящие Fluent-виджеты.
Если библиотека отсутствует — модуль предоставляет тонкие алиасы на
стандартные виджеты PyQt6, чтобы код продолжал работать без переписывания.

Это позволяет одним и тем же импортом писать «новый» Fluent-стиль кода
и не получать ImportError в окружениях без qfluentwidgets (например,
в CI без полного набора зависимостей).
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

try:
    from qfluentwidgets import (
        BodyLabel,
        CaptionLabel,
        CheckBox,
        ComboBox,
        DoubleSpinBox,
        FluentIcon,
        HyperlinkButton,
        InfoBar,
        InfoBarIcon,
        InfoBarPosition,
        LineEdit,
        MessageBoxBase,
        PasswordLineEdit,
        PrimaryPushButton,
        ProgressBar,
        PushButton,
        RadioButton,
        SearchLineEdit,
        SpinBox,
        StrongBodyLabel,
        SubtitleLabel,
        SwitchButton,
        TextEdit,
        Theme,
        TitleLabel,
        ToolButton,
        TransparentPushButton,
        TreeWidget,
        setTheme,
        setThemeColor,
    )

    _FLUENT_AVAILABLE = True
except Exception as e:  # pragma: no cover - fallback path
    log.debug(
        "qfluentwidgets unavailable, using PyQt6 fallback in ui.fluent_compat: %s",
        e,
    )
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import (  # noqa: I001 - грубо собранный fallback-импорт
        QCheckBox as CheckBox,
    )
    from PyQt6.QtWidgets import (
        QComboBox as ComboBox,
    )
    from PyQt6.QtWidgets import (
        QDoubleSpinBox as DoubleSpinBox,
    )
    from PyQt6.QtWidgets import (
        QLabel,
        QPushButton,
    )
    from PyQt6.QtWidgets import (
        QLineEdit as LineEdit,
    )
    from PyQt6.QtWidgets import (
        QProgressBar as ProgressBar,
    )
    from PyQt6.QtWidgets import (
        QRadioButton as RadioButton,
    )
    from PyQt6.QtWidgets import (
        QSpinBox as SpinBox,
    )
    from PyQt6.QtWidgets import (
        QTextEdit as TextEdit,
    )
    from PyQt6.QtWidgets import (
        QToolButton as ToolButton,
    )
    from PyQt6.QtWidgets import (
        QTreeWidget as TreeWidget,
    )

    class PrimaryPushButton(QPushButton):  # type: ignore
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setDefault(True)

    class PushButton(QPushButton):  # type: ignore
        pass

    class TransparentPushButton(QPushButton):  # type: ignore
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setFlat(True)

    class HyperlinkButton(QPushButton):  # type: ignore
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setFlat(True)
            f = self.font()
            f.setUnderline(True)
            self.setFont(f)

    class PasswordLineEdit(LineEdit):  # type: ignore
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setEchoMode(LineEdit.EchoMode.Password)

    class SearchLineEdit(LineEdit):  # type: ignore
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setClearButtonEnabled(True)

    class SwitchButton(CheckBox):  # type: ignore
        pass

    class _StyledLabel(QLabel):
        _font_size = 14
        _font_weight = QFont.Weight.Normal

        def __init__(self, text: str = "", parent=None):
            super().__init__(text, parent)
            f = self.font()
            f.setPointSize(self._font_size)
            f.setWeight(self._font_weight)
            self.setFont(f)

    class TitleLabel(_StyledLabel):  # type: ignore
        _font_size = 22
        _font_weight = QFont.Weight.DemiBold

    class SubtitleLabel(_StyledLabel):  # type: ignore
        _font_size = 16
        _font_weight = QFont.Weight.DemiBold

    class StrongBodyLabel(_StyledLabel):  # type: ignore
        _font_size = 11
        _font_weight = QFont.Weight.DemiBold

    class BodyLabel(_StyledLabel):  # type: ignore
        _font_size = 10
        _font_weight = QFont.Weight.Normal

    class CaptionLabel(_StyledLabel):  # type: ignore
        _font_size = 9
        _font_weight = QFont.Weight.Normal

    FluentIcon = None  # type: ignore

    class _InfoBarPositionFallback:
        TOP = 0
        TOP_RIGHT = 1
        BOTTOM = 2
        BOTTOM_RIGHT = 3
        NONE = 4

    InfoBarPosition = _InfoBarPositionFallback  # type: ignore

    class _InfoBarIconFallback:
        INFORMATION = 0
        SUCCESS = 1
        WARNING = 2
        ERROR = 3

    InfoBarIcon = _InfoBarIconFallback  # type: ignore

    class InfoBar:  # type: ignore
        """Безопасный fallback: показывает сообщение через QMessageBox."""

        @staticmethod
        def _show(parent, title: str, content: str, kind: str = "info") -> None:
            from PyQt6.QtWidgets import QMessageBox

            mb = QMessageBox(parent)
            mb.setWindowTitle(title)
            mb.setText(content)
            if kind == "success":
                mb.setIcon(QMessageBox.Icon.Information)
            elif kind == "warning":
                mb.setIcon(QMessageBox.Icon.Warning)
            elif kind == "error":
                mb.setIcon(QMessageBox.Icon.Critical)
            else:
                mb.setIcon(QMessageBox.Icon.Information)
            mb.exec()

        @staticmethod
        def info(title, content, parent=None, **_kw):
            InfoBar._show(parent, title, content, "info")

        @staticmethod
        def success(title, content, parent=None, **_kw):
            InfoBar._show(parent, title, content, "success")

        @staticmethod
        def warning(title, content, parent=None, **_kw):
            InfoBar._show(parent, title, content, "warning")

        @staticmethod
        def error(title, content, parent=None, **_kw):
            InfoBar._show(parent, title, content, "error")

    class MessageBoxBase:  # type: ignore
        """Минимальная заглушка — реальные диалоги должны проверять qfluentwidgets."""

    # Заглушки для setTheme / setThemeColor (no-op).
    # Имена в camelCase намеренно — повторяет API qfluentwidgets, чтобы внешние
    # вызовы были идентичными. ruff: noqa: N802
    def setTheme(_theme, save: bool = False):  # type: ignore  # noqa: N802
        return None

    def setThemeColor(_color, save: bool = False):  # type: ignore  # noqa: N802
        return None

    class Theme:  # type: ignore
        LIGHT = "light"
        DARK = "dark"
        AUTO = "auto"

    _FLUENT_AVAILABLE = False


#: True, если qfluentwidgets реально доступен в окружении.
FLUENT_AVAILABLE = _FLUENT_AVAILABLE


__all__ = [
    "FLUENT_AVAILABLE",
    # Кнопки
    "PushButton",
    "PrimaryPushButton",
    "TransparentPushButton",
    "HyperlinkButton",
    "ToolButton",
    # Поля ввода
    "LineEdit",
    "PasswordLineEdit",
    "SearchLineEdit",
    "TextEdit",
    "SpinBox",
    "DoubleSpinBox",
    "ComboBox",
    # Переключатели
    "CheckBox",
    "RadioButton",
    "SwitchButton",
    # Метки
    "BodyLabel",
    "StrongBodyLabel",
    "CaptionLabel",
    "SubtitleLabel",
    "TitleLabel",
    # Контейнеры / таблицы
    "TreeWidget",
    "ProgressBar",
    "MessageBoxBase",
    # Иконки и нотификации
    "FluentIcon",
    "InfoBar",
    "InfoBarIcon",
    "InfoBarPosition",
    # Тема
    "setTheme",
    "setThemeColor",
    "Theme",
]
