"""
Темы оформления ATPP — веб-стиль (orange-акцент) + светлая/тёмная.

Применяется через apply_theme(). Цвета согласованы с веб-SPA (Tailwind).
"""
from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

# ── Общий для обеих тем: оранжевый акцент, скругления, карточки ──

_BASE_QSS = """
/* Кнопки */
QPushButton {
    border: 1px solid #cbd5e1; padding: 6px 14px; border-radius: 6px;
    font-weight: 500; font-size: 13px;
}
QPushButton:hover { background-color: #f1f5f9; }
QPushButton:disabled { color: #94a3b8; background-color: #f1f5f9; }
QPushButton[primary="true"] {
    background-color: #f97316; color: white; border: none;
}
QPushButton[primary="true"]:hover { background-color: #ea580c; }

/* Поля ввода */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px;
    font-size: 13px;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #f97316;
}

/* Таблицы и деревья */
QHeaderView::section {
    padding: 6px 10px; border: none; border-bottom: 1px solid #e5e7eb;
    font-size: 11px; text-transform: uppercase; font-weight: 600;
    letter-spacing: 0.5px;
}
QTableWidget, QTreeWidget, QListWidget {
    border: 1px solid #e5e7eb; border-radius: 8px;
    font-size: 13px;
}
QTableWidget::item:hover, QTreeWidget::item:hover, QListWidget::item:hover { background-color: #f8fafc; }
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: rgba(249,115,22,0.12); color: inherit;
}

/* Вкладки */
QTabWidget::pane { border: 1px solid #e5e7eb; border-radius: 0 8px 8px 8px; }
QTabBar::tab {
    padding: 8px 16px; border: 1px solid transparent;
    border-radius: 8px 8px 0 0; font-size: 13px;
}
QTabBar::tab:selected { background: white; border-color: #e5e7eb #e5e7eb white; color: #f97316; font-weight: 600; }
QTabBar::tab:hover:!selected { background: #f8fafc; }

/* Скроллбары */
QScrollBar:vertical { width: 10px; border-radius: 4px; }
QScrollBar::handle:vertical { border-radius: 4px; min-height: 24px; }
QScrollBar:horizontal { height: 10px; border-radius: 4px; }
QScrollBar::handle:horizontal { border-radius: 4px; min-width: 24px; }

/* Подсказки */
QToolTip {
    padding: 6px 10px; border-radius: 6px; font-size: 12px;
}
"""

# ── Светлая тема (web-style) ──

LIGHT_QSS = _BASE_QSS + """
QWidget { color: #334155; }
QMainWindow, QDialog { background-color: #f1f5f9; }
QFrame[card="true"], QGroupBox[card="true"] {
    background-color: white; border: 1px solid #e5e7eb; border-radius: 12px;
}
QMenuBar { background-color: white; color: #334155; border-bottom: 1px solid #e5e7eb; }
QMenuBar::item:selected { background-color: #f8fafc; }
QMenu { background-color: white; color: #334155; border: 1px solid #e5e7eb; border-radius: 8px; padding: 4px; }
QMenu::item:selected { background-color: rgba(249,115,22,0.1); border-radius: 4px; }
QToolBar { background-color: white; border-bottom: 1px solid #e5e7eb; spacing: 6px; }
QStatusBar { background-color: white; color: #64748b; border-top: 1px solid #e5e7eb; font-size: 12px; }
QHeaderView::section { background-color: #f8fafc; color: #64748b; }
QScrollBar:vertical { background: #f1f5f9; }
QScrollBar::handle:vertical { background: #cbd5e1; }
QScrollBar:horizontal { background: #f1f5f9; }
QScrollBar::handle:horizontal { background: #cbd5e1; }
QScrollBar::handle:hover { background: #94a3b8; }
QToolTip { background-color: #1e293b; color: #f1f5f9; }

/* Оранжевые акценты: панель навигации, активные элементы */
QTreeWidget#nav_panel, QListWidget#nav_panel {
    background-color: #0f172a; color: #cbd5e1; border: none; border-radius: 0;
    font-size: 13px;
}
QTreeWidget#nav_panel::item:hover, QListWidget#nav_panel::item:hover {
    background-color: #1e293b;
}
QTreeWidget#nav_panel::item:selected, QListWidget#nav_panel::item:selected {
    background-color: rgba(249,115,22,0.15); color: #fb923c;
    border-left: 3px solid #f97316;
}
"""

# ── Тёмная тема (web-style dark) ──

DARK_QSS = _BASE_QSS + """
QWidget { color: #e2e8f0; }
QMainWindow, QDialog { background-color: #1a1a2e; }
QFrame[card="true"], QGroupBox[card="true"] {
    background-color: #1e293b; border: 1px solid #334155; border-radius: 12px;
}
QMenuBar { background-color: #1e293b; color: #e2e8f0; border-bottom: 1px solid #334155; }
QMenuBar::item:selected { background-color: #334155; }
QMenu { background-color: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px; padding: 4px; }
QMenu::item:selected { background-color: rgba(249,115,22,0.2); border-radius: 4px; }
QToolBar { background-color: #1e293b; border-bottom: 1px solid #334155; spacing: 6px; }
QStatusBar { background-color: #1e293b; color: #94a3b8; border-top: 1px solid #334155; font-size: 12px; }
QHeaderView::section { background-color: #1e293b; color: #94a3b8; }
QTabWidget::pane { border-color: #334155; }
QTabBar::tab:selected { background: #1e293b; border-color: #334155 #334155 #1e293b; color: #f97316; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #0f172a; border-color: #334155; color: #e2e8f0;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border-color: #f97316; }
QTableWidget, QTreeWidget, QListWidget {
    background-color: #0f172a; color: #e2e8f0;
    alternate-background-color: #162032;
    selection-background-color: rgba(249,115,22,0.2); selection-color: #fb923c;
    border-color: #334155;
}
QTableWidget::item:hover, QTreeWidget::item:hover, QListWidget::item:hover { background-color: #1a2740; }
QPushButton {
    background-color: #1e293b; color: #e2e8f0; border-color: #334155;
}
QPushButton:hover { background-color: #334155; }
QPushButton:disabled { color: #64748b; background-color: #162032; }
QScrollBar:vertical { background: #1a1a2e; }
QScrollBar::handle:vertical { background: #475569; }
QScrollBar:horizontal { background: #1a1a2e; }
QScrollBar::handle:horizontal { background: #475569; }
QScrollBar::handle:hover { background: #64748b; }
QToolTip { background-color: #f1f5f9; color: #1e293b; }

/* Сайдбар-навигация: всегда тёмный, как в вебе */
QTreeWidget#nav_panel, QListWidget#nav_panel {
    background-color: #0f172a; color: #cbd5e1; border: none; border-radius: 0;
    font-size: 13px;
}
QTreeWidget#nav_panel::item:hover, QListWidget#nav_panel::item:hover {
    background-color: #1e293b;
}
QTreeWidget#nav_panel::item:selected, QListWidget#nav_panel::item:selected {
    background-color: rgba(249,115,22,0.15); color: #fb923c;
    border-left: 3px solid #f97316;
}
"""


def apply_theme(app: QApplication, *, theme: str = 'light', font_size: int = 9) -> None:
    """Применить тему и базовый шрифт к QApplication.

    Безопасно вызывать многократно (на старте и при смене настроек).
    theme: 'light' | 'dark'
    """
    if theme == 'dark':
        app.setStyleSheet(DARK_QSS)
    else:
        app.setStyleSheet(LIGHT_QSS)

    f: QFont = app.font()
    if font_size and font_size > 0:
        f.setPointSize(int(font_size))
        app.setFont(f)
