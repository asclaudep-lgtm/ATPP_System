"""
Темы оформления и базовые настройки шрифта.

Темы делаются через QSS — это безопаснее, чем ставить QPalette: палитра
ломает рендеринг иконок и подсказок в Qt6 на некоторых системах.
"""
from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

LIGHT_QSS = ""  # системная

DARK_QSS = """
QWidget {
    background-color: #2b2b2b;
    color: #e6e6e6;
}
QMainWindow, QDialog, QFrame, QGroupBox {
    background-color: #2b2b2b;
}
QMenuBar { background-color: #353535; color: #e6e6e6; }
QMenuBar::item:selected { background-color: #4a4a4a; }
QMenu { background-color: #353535; color: #e6e6e6; }
QMenu::item:selected { background-color: #4a4a4a; }
QToolBar { background-color: #353535; border: 0; }
QStatusBar { background-color: #353535; color: #e6e6e6; }
QTabWidget::pane { border: 1px solid #4a4a4a; }
QTabBar::tab {
    background-color: #353535; color: #e6e6e6;
    padding: 6px 14px; border: 1px solid #4a4a4a;
}
QTabBar::tab:selected { background-color: #2b2b2b; }
QPushButton {
    background-color: #3a3a3a; color: #e6e6e6;
    border: 1px solid #555; padding: 5px 12px; border-radius: 3px;
}
QPushButton:hover { background-color: #4a4a4a; }
QPushButton:disabled { color: #888; background-color: #2f2f2f; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #1f1f1f; color: #e6e6e6;
    border: 1px solid #555; padding: 3px;
}
QHeaderView::section {
    background-color: #353535; color: #e6e6e6;
    border: 1px solid #444; padding: 4px;
}
QTableWidget, QTreeWidget, QListWidget {
    background-color: #1f1f1f; color: #e6e6e6;
    alternate-background-color: #262626;
    selection-background-color: #2c5d8e;
    selection-color: #ffffff;
    gridline-color: #3a3a3a;
}
QTreeWidget::item:hover, QTableWidget::item:hover, QListWidget::item:hover {
    background-color: #333;
}
QScrollBar:vertical {
    background: #2b2b2b; width: 12px;
}
QScrollBar::handle:vertical { background: #555; min-height: 24px; border-radius: 4px; }
QToolTip {
    background-color: #1f1f1f; color: #e6e6e6;
    border: 1px solid #555;
}
"""


def apply_theme(app: QApplication, *, theme: str = 'light', font_size: int = 9) -> None:
    """Применить тему и базовый шрифт к QApplication.

    Безопасно вызывать многократно (на старте и при смене настроек).
    """
    if theme == 'dark':
        app.setStyleSheet(DARK_QSS)
    else:
        app.setStyleSheet(LIGHT_QSS)

    # Базовый шрифт. Сохраняем семейство по умолчанию, меняем только размер.
    f: QFont = app.font()
    if font_size and font_size > 0:
        f.setPointSize(int(font_size))
        app.setFont(f)
