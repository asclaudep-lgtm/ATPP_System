"""Activity bar — VSCode-style vertical icon strip.

Pinned to left edge between TitleBar and StatusBar.
Width fixed at 52px. Active module = orange left bar + tinted bg.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QSpacerItem, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon

from ui.fluent_compat import FLUENT_AVAILABLE
if FLUENT_AVAILABLE:
    from qfluentwidgets import FluentIcon as FIF


class ActivityButton(QPushButton):
    """Icon-only button for activity bar."""
    def __init__(self, icon, name: str, key: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.setProperty("role", "activity-btn")
        self.setCheckable(True)
        self.setFixedSize(52, 44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(name)
        if isinstance(icon, str):
            self.setText(icon)
        else:
            self.setIcon(icon)
            self.setIconSize(QSize(22, 22))


class ActivityBar(QWidget):
    """VSCode-style activity bar.

    Signals:
        module_selected(key: str)
        settings_clicked()
        profile_clicked()
    """
    module_selected = pyqtSignal(str)
    settings_clicked = pyqtSignal()
    profile_clicked = pyqtSignal()

    MODULES = [
        ("products",   "Изделия / ТП",          "❖", "DOCUMENT"),
        ("dashboard",  "Дашборд",               "▤", "VIEW"),
        ("orders",     "Производственные заказы","☰", "CLIPPING_TOOL"),
        ("pdo",        "Диспетчер ПДО",         "⧉", "TILES"),
        ("qa",         "QA-терминал",           "✓", "ACCEPT"),
        ("tooling",    "Оснастка и инструмент", "⚙", "DEVELOPER_TOOLS"),
        ("references", "Справочники",           "⧖", "LIBRARY"),
        ("documents",  "Документы",             "☷", "DOCUMENT"),
        ("users",      "Пользователи",          "☸", "PEOPLE"),
    ]
    BOTTOM = [
        ("web",       "Открыть веб-интерфейс", "🌐", "BROWSER"),
        ("settings",  "Настройки",  "⛭", "SETTING"),
        ("profile",   "Профиль",    "◉", "PEOPLE"),
    ]

    web_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("activity_bar")
        self.setFixedWidth(52)
        self._buttons = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)

        for key, name, symbol, ficon in self.MODULES:
            icon = self._make_icon(symbol, ficon)
            btn = ActivityButton(icon, name, key)
            btn.clicked.connect(lambda _=False, k=key: self._on_module(k))
            layout.addWidget(btn)
            self._buttons[key] = btn

        layout.addStretch(1)

        for key, name, symbol, ficon in self.BOTTOM:
            icon = self._make_icon(symbol, ficon)
            btn = ActivityButton(icon, name, key)
            if key == "settings":
                btn.clicked.connect(self.settings_clicked)
            elif key == "profile":
                btn.clicked.connect(self.profile_clicked)
            elif key == "web":
                btn.clicked.connect(self.web_clicked)
            btn.setCheckable(False)
            layout.addWidget(btn)

        self.set_active("products")

    def _make_icon(self, symbol: str, ficon: str):
        if FLUENT_AVAILABLE:
            try:
                return getattr(FIF, ficon).icon()
            except Exception:
                pass
        return symbol

    def _on_module(self, key: str):
        self.set_active(key)
        self.module_selected.emit(key)

    def set_active(self, key: str):
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
