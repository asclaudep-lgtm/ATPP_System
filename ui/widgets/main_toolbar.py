"""
Main toolbar — quick actions that are NOT in the sidebar.

Qt6 QToolBar QSS cascade is broken (child QPushButton don't inherit
QToolBar QPushButton selectors). We apply styles explicitly.
"""
from PyQt6.QtWidgets import QToolBar, QPushButton, QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QSize, pyqtSignal

# Inline styles required — QToolBar::QPushButton cascade is broken in Qt6
_BTN_BASE = (
    "QPushButton {{"
    "  background: transparent; color: {color};"
    "  border: 1px solid {border}; border-radius: 6px;"
    "  padding: 4px 12px; font-size: 12px; font-weight: 500;"
    "  outline: none;"
    "}}"
    "QPushButton:hover {{ background: {hover}; border-color: {hover_border}; }}"
    "QPushButton:focus {{ outline: none; }}"
    "QPushButton:pressed {{ background: {pressed}; }}"
)

_STYLE_LIGHT = _BTN_BASE.format(
    color="#475569", border="#cbd5e1", hover="#f1f5f9",
    hover_border="#94a3b8", pressed="#e2e8f0",
)
_STYLE_DARK = _BTN_BASE.format(
    color="#94a3b8", border="#334155", hover="#334155",
    hover_border="#64748b", pressed="#1e293b",
)

# Special buttons — no border, compact
_SPECIAL_BTN = (
    "QPushButton {{"
    "  background: transparent; color: {color}; border: none;"
    "  border-radius: 4px; outline: none;"
    "}}"
    "QPushButton:hover {{ background: {hover}; }}"
    "QPushButton:focus {{ outline: none; }}"
    "QPushButton:pressed {{ background: {pressed}; }}"
)

_SPECIAL_LIGHT = _SPECIAL_BTN.format(
    color="#475569", hover="#e2e8f0", pressed="#cbd5e1",
)
_SPECIAL_DARK = _SPECIAL_BTN.format(
    color="#94a3b8", hover="#334155", pressed="#1e293b",
)


class MainToolBar(QToolBar):
    new_product = pyqtSignal()
    new_tp = pyqtSignal()
    open_references = pyqtSignal()
    open_documents = pyqtSignal()
    open_ktd_browser = pyqtSignal()
    refresh = pyqtSignal()
    open_users = pyqtSignal()
    open_global_search = pyqtSignal()
    open_pdo_dispatcher = pyqtSignal()
    toggle_theme = pyqtSignal()

    def __init__(self, user: dict, current_theme: str = "light", parent=None):
        super().__init__("Основная", parent)
        self.setIconSize(QSize(18, 18))
        self.setMovable(False)
        self._theme = current_theme
        self._all_btns: list[QPushButton] = []

        # Unique actions (not in sidebar)
        self._add("📋 Шаблоны КТД", self.open_ktd_browser)
        self._add("↺ Обновить", self.refresh)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        self._add("🔎  Ctrl+P", self.open_global_search)

        # Theme toggle
        self._theme_btn = QPushButton("🌙" if current_theme == "light" else "☀")
        self._theme_btn.setFixedSize(36, 28)
        self._theme_btn.setToolTip("Переключить тему")
        self._theme_btn.clicked.connect(self.toggle_theme)
        self.addWidget(self._theme_btn)

        self._apply_styles()

    def _add(self, text, signal):
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        btn.clicked.connect(signal)
        self.addWidget(btn)
        self._all_btns.append(btn)
        return btn

    def _apply_styles(self):
        style = _STYLE_DARK if self._theme == "dark" else _STYLE_LIGHT
        special = _SPECIAL_DARK if self._theme == "dark" else _SPECIAL_LIGHT
        for btn in self._all_btns:
            btn.setStyleSheet(style)
        self._theme_btn.setStyleSheet(special)

    def update_theme(self, theme: str):
        self._theme = theme
        self._apply_styles()
        self._theme_btn.setText("🌙" if theme == "light" else "☀")

    def update_theme_button(self, theme: str):
        self.update_theme(theme)
