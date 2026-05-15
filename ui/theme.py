"""
ATPP theme — web-style QSS, единый для светлой и тёмной тем.

Использует property-селекторы Qt (например QPushButton[primary="true"])
вместо inline-стилей. При смене темы достаточно вызвать apply_theme() —
все виджеты обновятся автоматически.
"""
from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

# ═══════════════════════════════════════════════════════════════════════════
# Светлая тема (web-style: sidebar тёмный, workspace светлый)
# ═══════════════════════════════════════════════════════════════════════════

LIGHT_QSS = """
/* ── Global ── */
QWidget { color: #334155; }
QMainWindow { background: #f1f5f9; }
QDialog { background: #ffffff; }

/* ── Toolbar ── */
QToolBar {
    background: #ffffff; border-bottom: 1px solid #e5e7eb;
    spacing: 6px; padding: 4px 8px;
}
QToolBar QPushButton {
    background: transparent; color: #475569; border: 1px solid #cbd5e1;
    border-radius: 6px; padding: 5px 12px; font-size: 12px; font-weight: 500;
}
QToolBar QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; }
QToolBar QPushButton[primary="true"] {
    background: #f97316; color: white; border: none; font-weight: 600;
}
QToolBar QPushButton[primary="true"]:hover { background: #ea580c; }

/* ── Menu bar ── */
QMenuBar { background: #ffffff; color: #334155; border-bottom: 1px solid #e5e7eb; padding: 2px; }
QMenuBar::item:selected { background: #f1f5f9; border-radius: 4px; }
QMenu { background: #ffffff; color: #334155; border: 1px solid #e5e7eb; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 6px 20px; border-radius: 4px; }
QMenu::item:selected { background: rgba(249,115,22,0.1); color: #f97316; }
QMenu::separator { height: 1px; background: #e5e7eb; margin: 4px 8px; }

/* ── Status bar ── */
QStatusBar { background: #ffffff; color: #64748b; border-top: 1px solid #e5e7eb; font-size: 11px; }

/* ── Tab widget (workspace) ── */
QTabWidget::pane { border: none; background: #f1f5f9; }
QTabBar::tab {
    background: #e5e7eb; color: #475569; padding: 7px 18px;
    border: none; border-radius: 8px 8px 0 0; margin-right: 2px; font-size: 12px;
}
QTabBar::tab:selected { background: #f1f5f9; color: #f97316; font-weight: 600; }
QTabBar::tab:hover:!selected { background: #cbd5e1; }
QTabBar::close-button { border-radius: 3px; }
QTabBar::close-button:hover { background: #e5e7eb; }

/* ── Buttons ── */
QPushButton {
    background: #ffffff; color: #334155; border: 1px solid #cbd5e1;
    border-radius: 6px; padding: 6px 14px; font-weight: 500;
}
QPushButton:hover { background: #f8fafc; border-color: #94a3b8; }
QPushButton:pressed { background: #f1f5f9; }
QPushButton:disabled { color: #94a3b8; background: #f1f5f9; border-color: #e5e7eb; }
QPushButton[primary="true"] {
    background: #f97316; color: white; border: none; font-weight: 600;
}
QPushButton[primary="true"]:hover { background: #ea580c; }
QPushButton[primary="true"]:disabled { background: #fdba74; }

/* ── Inputs ── */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background: #ffffff; color: #334155; border: 1px solid #cbd5e1;
    border-radius: 6px; padding: 6px 10px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border-color: #f97316; }
QComboBox {
    background: #ffffff; color: #334155; border: 1px solid #cbd5e1;
    border-radius: 6px; padding: 6px 10px;
}
QComboBox:focus { border-color: #f97316; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px;
    selection-background-color: rgba(249,115,22,0.1); selection-color: #334155;
}

/* ── Tables & Trees ── */
QTableWidget, QTreeWidget, QListWidget, QTableView, QTreeView, QListView {
    background: #ffffff; color: #334155; border: 1px solid #e5e7eb;
    border-radius: 8px; font-size: 13px;
    alternate-background-color: #f8fafc;
    selection-background-color: rgba(249,115,22,0.1); selection-color: #334155;
}
QTableWidget::item:hover, QTreeWidget::item:hover, QListWidget::item:hover,
QTableView::item:hover, QTreeView::item:hover { background: #f1f5f9; }
QHeaderView::section {
    background: #f8fafc; color: #64748b; border: none;
    border-bottom: 1px solid #e5e7eb; padding: 8px 12px;
    font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;
}

/* ── GroupBox / Frame ── */
QGroupBox { font-weight: 600; border: 1px solid #e5e7eb; border-radius: 8px; margin-top: 12px; padding-top: 16px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }

/* ── Scrollbars ── */
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 8px; }
QScrollBar::handle:horizontal { background: #cbd5e1; border-radius: 4px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #94a3b8; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Splitter ── */
QSplitter::handle { background: #e5e7eb; }
QSplitter::handle:hover { background: #f97316; }

/* ── Tooltips ── */
QToolTip {
    background: #1e293b; color: #f1f5f9; border: none;
    border-radius: 6px; padding: 6px 10px; font-size: 12px;
}

/* ── Dock widget ── */
QDockWidget { titlebar-close-icon: none; }
QDockWidget::title { background: #f8fafc; padding: 6px 12px; border-bottom: 1px solid #e5e7eb; }

/* ── Progress bar ── */
QProgressBar {
    background: #e5e7eb; border: none; border-radius: 4px; height: 8px; text-align: center; font-size: 0;
}
QProgressBar::chunk { background: #f97316; border-radius: 4px; }

/* ── Message box / Dialogs ── */
QMessageBox { background: #ffffff; }
QMessageBox QLabel { color: #334155; }

/* ── Sidebar panel (dark, fixed) ── */
QWidget#nav_panel, QTreeWidget#nav_panel, QListWidget#nav_panel {
    background-color: #0f172a; color: #cbd5e1; border: none; border-radius: 0;
}
"""

# ═══════════════════════════════════════════════════════════════════════════
# Тёмная тема
# ═══════════════════════════════════════════════════════════════════════════

DARK_QSS = """
QWidget { color: #e2e8f0; }
QMainWindow { background: #0f172a; }
QDialog { background: #1e293b; }

QToolBar { background: #1e293b; border-bottom: 1px solid #334155; spacing: 6px; padding: 4px 8px; }
QToolBar QPushButton {
    background: transparent; color: #94a3b8; border: 1px solid #334155;
    border-radius: 6px; padding: 5px 12px; font-size: 12px; font-weight: 500;
}
QToolBar QPushButton:hover { background: #334155; color: #e2e8f0; }
QToolBar QPushButton[primary="true"] { background: #f97316; color: white; border: none; }
QToolBar QPushButton[primary="true"]:hover { background: #ea580c; }

QMenuBar { background: #1e293b; color: #e2e8f0; border-bottom: 1px solid #334155; }
QMenuBar::item:selected { background: #334155; border-radius: 4px; }
QMenu { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 6px 20px; border-radius: 4px; }
QMenu::item:selected { background: rgba(249,115,22,0.2); color: #fb923c; }
QMenu::separator { height: 1px; background: #334155; margin: 4px 8px; }

QStatusBar { background: #1e293b; color: #94a3b8; border-top: 1px solid #334155; font-size: 11px; }

QTabWidget::pane { border: none; background: #0f172a; }
QTabBar::tab {
    background: #1e293b; color: #94a3b8; padding: 7px 18px;
    border: none; border-radius: 8px 8px 0 0; margin-right: 2px; font-size: 12px;
}
QTabBar::tab:selected { background: #0f172a; color: #fb923c; font-weight: 600; }
QTabBar::tab:hover:!selected { background: #334155; }
QTabBar::close-button:hover { background: #334155; }

QPushButton {
    background: #1e293b; color: #e2e8f0; border: 1px solid #334155;
    border-radius: 6px; padding: 6px 14px; font-weight: 500;
}
QPushButton:hover { background: #334155; }
QPushButton:pressed { background: #475569; }
QPushButton:disabled { color: #64748b; background: #162032; border-color: #1e293b; }
QPushButton[primary="true"] { background: #f97316; color: white; border: none; }
QPushButton[primary="true"]:hover { background: #ea580c; }

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; padding: 6px 10px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border-color: #f97316; }
QComboBox { background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px; padding: 6px 10px; }
QComboBox:focus { border-color: #f97316; }
QComboBox QAbstractItemView {
    background: #1e293b; border: 1px solid #334155; border-radius: 6px;
    selection-background-color: rgba(249,115,22,0.2); selection-color: #fb923c;
}

QTableWidget, QTreeWidget, QListWidget, QTableView, QTreeView, QListView {
    background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 8px;
    alternate-background-color: #162032;
    selection-background-color: rgba(249,115,22,0.2); selection-color: #fb923c;
}
QTableWidget::item:hover, QTreeWidget::item:hover, QListWidget::item:hover,
QTableView::item:hover, QTreeView::item:hover { background: #1a2740; }
QHeaderView::section {
    background: #1e293b; color: #94a3b8; border: none;
    border-bottom: 1px solid #334155; padding: 8px 12px;
    font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;
}

QGroupBox { font-weight: 600; border: 1px solid #334155; border-radius: 8px; margin-top: 12px; padding-top: 16px; }

QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #475569; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #64748b; }
QScrollBar:horizontal { background: transparent; height: 8px; }
QScrollBar::handle:horizontal { background: #475569; border-radius: 4px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #64748b; }

QSplitter::handle { background: #334155; }
QSplitter::handle:hover { background: #f97316; }

QToolTip { background: #f1f5f9; color: #0f172a; border-radius: 6px; padding: 6px 10px; font-size: 12px; }
QDockWidget::title { background: #1e293b; padding: 6px 12px; border-bottom: 1px solid #334155; }
QProgressBar { background: #334155; border-radius: 4px; height: 8px; }
QProgressBar::chunk { background: #f97316; border-radius: 4px; }

QMessageBox { background: #1e293b; }
QMessageBox QLabel { color: #e2e8f0; }

QWidget#nav_panel, QTreeWidget#nav_panel, QListWidget#nav_panel {
    background-color: #0f172a; color: #cbd5e1; border: none; border-radius: 0;
}
"""


def apply_theme(app: QApplication, *, theme: str = 'light', font_size: int = 9) -> None:
    """Применить тему и базовый шрифт.

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
