"""
ATPP Fluent theme — unified QSS + qfluentwidgets integration.

Single source of truth for both light and dark themes.
Orange accent (#f97316), Fluent spacing (4px grid), Segoe UI font stack.
"""
from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

# ═══════════════════════════════════════════════════════════════════════════════
# Fluent Design palette
# ═══════════════════════════════════════════════════════════════════════════════
ACCENT = "#f97316"
ACCENT_HOVER = "#ea580c"
ACCENT_DISABLED = "#fdba74"
ACCENT_10 = "rgba(249,115,22,0.1)"

# Light theme
LIGHT_BG = "#F3F3F3"
LIGHT_SURFACE = "#FFFFFF"
LIGHT_BORDER = "#E0E0E0"
LIGHT_BORDER_STRONG = "#CCCCCC"
LIGHT_TEXT = "#1A1A1A"
LIGHT_TEXT_SECONDARY = "#616161"
LIGHT_HOVER = "#F5F5F5"
LIGHT_ALT_ROW = "#FAFAFA"
LIGHT_HEADER_BG = "#F9F9F9"
LIGHT_HEADER_TEXT = "#757575"
LIGHT_INPUT_BG = "#FFFFFF"
LIGHT_SIDEBAR_BG = "#0F172A"
LIGHT_SIDEBAR_TEXT = "#CBD5E1"

# Dark theme
DARK_BG = "#1F1F1F"
DARK_SURFACE = "#2B2B2B"
DARK_BORDER = "#383838"
DARK_BORDER_STRONG = "#454545"
DARK_TEXT = "#E8E8E8"
DARK_TEXT_SECONDARY = "#A0A0A0"
DARK_HOVER = "#333333"
DARK_ALT_ROW = "#262626"
DARK_HEADER_BG = "#2B2B2B"
DARK_HEADER_TEXT = "#A0A0A0"
DARK_INPUT_BG = "#1A1A1A"
DARK_SIDEBAR_BG = "#0F172A"
DARK_SIDEBAR_TEXT = "#CBD5E1"

# ═══════════════════════════════════════════════════════════════════════════════
# Shared spacing / radius constants (not used in QSS directly, for reference)
# ═══════════════════════════════════════════════════════════════════════════════
# Grid: 4px base → 4, 8, 12, 16, 20, 24, 32
# Radius: 4 (small), 6 (default), 8 (card), 12 (dialog)


def _build_qss(pal: dict) -> str:
    """Build QSS from palette dictionary."""
    return f"""
/* ── Global ── */
QWidget {{ color: {pal['text']}; }}
QMainWindow {{ background: {pal['bg']}; }}
QDialog {{ background: {pal['surface']}; }}

/* ── Toolbar ── */
QToolBar {{
    background: {pal['surface']};
    border-bottom: 1px solid {pal['border']};
    spacing: 8px; padding: 4px 12px;
}}
QToolBar QPushButton {{
    background: transparent; color: {pal['text_secondary']};
    border: 1px solid {pal['border']};
    border-radius: 6px; padding: 4px 12px; font-size: 12px; font-weight: 500;
}}
QToolBar QPushButton:hover {{ background: {pal['hover']}; border-color: {pal['border_strong']}; }}
QToolBar QPushButton[primary="true"] {{
    background: {ACCENT}; color: white; border: none; font-weight: 600;
}}
QToolBar QPushButton[primary="true"]:hover {{ background: {ACCENT_HOVER}; }}

/* ── Menu bar ── */
QMenuBar {{ background: {pal['surface']}; color: {pal['text']}; border-bottom: 1px solid {pal['border']}; padding: 2px; }}
QMenuBar::item:selected {{ background: {pal['hover']}; border-radius: 4px; }}
QMenu {{
    background: {pal['surface']}; color: {pal['text']};
    border: 1px solid {pal['border']}; border-radius: 8px; padding: 4px;
}}
QMenu::item {{ padding: 6px 24px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACCENT_10}; color: {ACCENT}; }}
QMenu::separator {{ height: 1px; background: {pal['border']}; margin: 4px 8px; }}

/* ── Status bar ── */
QStatusBar {{
    background: {pal['surface']}; color: {pal['header_text']};
    border-top: 1px solid {pal['border']}; font-size: 11px;
}}

/* ── Tab widget ── */
QTabWidget::pane {{ border: none; background: {pal['bg']}; }}
QTabBar::tab {{
    background: transparent; color: {pal['text_secondary']};
    padding: 8px 20px; border: none; border-bottom: 2px solid transparent;
    margin-right: 2px; font-size: 12px;
}}
QTabBar::tab:selected {{
    color: {ACCENT}; font-weight: 600;
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{ color: {pal['text']}; background: {pal['hover']}; }}
QTabBar::close-button {{ border-radius: 3px; }}
QTabBar::close-button:hover {{ background: {pal['border']}; }}

/* ── Buttons ── */
QPushButton {{
    background: {pal['surface']}; color: {pal['text']};
    border: 1px solid {pal['border']};
    border-radius: 6px; padding: 8px 16px; font-weight: 500;
}}
QPushButton:hover {{ background: {pal['hover']}; border-color: {pal['border_strong']}; }}
QPushButton:pressed {{ background: {pal['border']}; }}
QPushButton:disabled {{
    color: {pal['header_text']}; background: {pal['hover']};
    border-color: {pal['border']};
}}
QPushButton[primary="true"] {{
    background: {ACCENT}; color: white; border: none; font-weight: 600;
}}
QPushButton[primary="true"]:hover {{ background: {ACCENT_HOVER}; }}
QPushButton[primary="true"]:pressed {{ background: #c2410c; }}
QPushButton[primary="true"]:disabled {{ background: {ACCENT_DISABLED}; }}

/* ── Inputs ── */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background: {pal['input_bg']}; color: {pal['text']};
    border: 1px solid {pal['border']};
    border-radius: 6px; padding: 8px 12px;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT}; border-width: 2px; padding: 7px 11px;
}}
QComboBox {{
    background: {pal['input_bg']}; color: {pal['text']};
    border: 1px solid {pal['border']};
    border-radius: 6px; padding: 8px 12px;
}}
QComboBox:focus {{ border-color: {ACCENT}; border-width: 2px; padding: 7px 11px; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{
    background: {pal['surface']}; border: 1px solid {pal['border']};
    border-radius: 6px;
    selection-background-color: {ACCENT_10}; selection-color: {pal['text']};
}}

/* ── Tables & Trees ── */
QTableWidget, QTreeWidget, QListWidget, QTableView, QTreeView, QListView {{
    background: {pal['surface']}; color: {pal['text']};
    border: 1px solid {pal['border']};
    border-radius: 8px; font-size: 13px;
    alternate-background-color: {pal['alt_row']};
    selection-background-color: {ACCENT_10}; selection-color: {pal['text']};
}}
QTableWidget::item:hover, QTreeWidget::item:hover, QListWidget::item:hover,
QTableView::item:hover, QTreeView::item:hover {{ background: {pal['hover']}; }}
QHeaderView::section {{
    background: {pal['header_bg']}; color: {pal['header_text']};
    border: none; border-bottom: 1px solid {pal['border']};
    padding: 10px 12px; font-size: 11px; text-transform: uppercase;
    font-weight: 600; letter-spacing: 0.5px;
}}

/* ── GroupBox / Frame ── */
QGroupBox {{
    font-weight: 600; border: 1px solid {pal['border']};
    border-radius: 8px; margin-top: 16px; padding-top: 20px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 16px; padding: 0 8px; }}

/* ── Scrollbars ── */
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {pal['border_strong']}; border-radius: 4px; min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {pal['header_text']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{
    background: {pal['border_strong']}; border-radius: 4px; min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{ background: {pal['header_text']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Splitter ── */
QSplitter::handle {{ background: {pal['border']}; }}
QSplitter::handle:hover {{ background: {ACCENT}; }}

/* ── Tooltips ── */
QToolTip {{
    background: {pal['sidebar_bg']}; color: {pal['sidebar_text']};
    border: none; border-radius: 6px; padding: 8px 12px; font-size: 12px;
}}

/* ── Dock widget ── */
QDockWidget {{ titlebar-close-icon: none; }}
QDockWidget::title {{
    background: {pal['header_bg']}; padding: 8px 16px;
    border-bottom: 1px solid {pal['border']};
}}

/* ── Progress bar ── */
QProgressBar {{
    background: {pal['border']}; border: none; border-radius: 4px;
    height: 8px; text-align: center; font-size: 0;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}

/* ── Message box / Dialogs ── */
QMessageBox {{ background: {pal['surface']}; }}
QMessageBox QLabel {{ color: {pal['text']}; }}

/* ── Sidebar panel (always dark) ── */
QWidget#nav_panel {{
    background-color: #0f172a; color: #cbd5e1;
    border: none; border-radius: 0;
}}

/* Nav header */
QFrame#nav_header {{
    background: #0f172a; border-bottom: 1px solid #1e293b;
}}

QLabel#nav_logo {{
    background: {ACCENT}; color: white; border-radius: 6px;
    font-weight: bold; font-size: 14px;
}}

QLabel#nav_title {{
    color: white; font-weight: 600; font-size: 14px;
}}

/* Nav quick actions */
QFrame#nav_actions {{
    background: #0f172a; border-bottom: 1px solid #1e293b;
}}

QPushButton#nav_action_btn {{
    border-radius: 6px; padding: 0 12px; font-size: 12px; font-weight: 500;
}}
QPushButton#nav_action_btn[accent="orange"] {{
    background: rgba(249,115,22,0.15); color: #fb923c;
    border: 1px solid rgba(249,115,22,0.3);
}}
QPushButton#nav_action_btn[accent="orange"]:hover {{
    background: rgba(249,115,22,0.25);
}}
QPushButton#nav_action_btn[accent="purple"] {{
    background: rgba(139,92,246,0.15); color: #a78bfa;
    border: 1px solid rgba(139,92,246,0.3);
}}
QPushButton#nav_action_btn[accent="purple"]:hover {{
    background: rgba(139,92,246,0.25);
}}

/* Nav modules scroll area */
QScrollArea#nav_modules_scroll {{
    background: #0f172a; border: none;
}}
QScrollArea#nav_modules_scroll QScrollBar:vertical {{
    width: 4px; background: transparent;
}}
QScrollArea#nav_modules_scroll QScrollBar::handle:vertical {{
    background: #334155; border-radius: 2px;
}}

QWidget#nav_modules_widget {{
    background: #0f172a;
}}

/* Nav section labels */
QLabel#nav_section_label {{
    color: #64748b; font-size: 10px; font-weight: 700;
    letter-spacing: 1px; padding: 8px 16px 4px 16px;
}}

/* Nav module buttons */
QPushButton[module_btn="true"] {{
    text-align: left; padding: 0 16px; border: none;
    border-left: 3px solid transparent; border-radius: 0;
    font-size: 13px; color: #94a3b8; background: transparent;
}}
QPushButton[module_btn="true"]:hover {{
    background: #1e293b; color: #e2e8f0;
}}
QPushButton[module_btn="true"]:checked {{
    background: rgba(249,115,22,0.12); color: #fb923c;
    border-left: 3px solid {ACCENT};
}}

/* Nav tabs */
QTabWidget#nav_tabs::pane {{
    border: none; background: #0f172a;
}}
QTabWidget#nav_tabs QTabBar::tab {{
    background: #1e293b; color: #94a3b8;
    padding: 4px 12px; border: none; font-size: 11px;
}}
QTabWidget#nav_tabs QTabBar::tab:selected {{
    background: #0f172a; color: #fb923c;
}}

/* Nav tree */
QTreeWidget#nav_tree {{
    background: #0f172a; color: #cbd5e1;
    border: none; font-size: 12px;
}}
QTreeWidget#nav_tree::item:hover {{ background: #1e293b; }}
QTreeWidget#nav_tree::item:selected {{
    background: rgba(249,115,22,0.12); color: #fb923c;
}}

/* Nav footer */
QFrame#nav_footer {{
    background: #0f172a; border-top: 1px solid #1e293b;
}}

QLabel#nav_avatar {{
    background: #334155; color: #e2e8f0;
    border-radius: 16px; font-weight: 600; font-size: 13px;
}}

QLabel#nav_user_info {{
    color: #cbd5e1; font-size: 11px;
}}

/* Nav search */
QLineEdit#nav_search {{
    background: #1e293b; color: #e2e8f0;
    border: 1px solid #334155; border-radius: 6px;
    padding: 6px 12px; margin: 8px 12px; font-size: 12px;
}}
QLineEdit#nav_search:focus {{
    border-color: {ACCENT}; border-width: 2px; padding: 5px 11px;
}}
"""


LIGHT_QSS = _build_qss({
    "bg": LIGHT_BG, "surface": LIGHT_SURFACE,
    "border": LIGHT_BORDER, "border_strong": LIGHT_BORDER_STRONG,
    "text": LIGHT_TEXT, "text_secondary": LIGHT_TEXT_SECONDARY,
    "hover": LIGHT_HOVER, "alt_row": LIGHT_ALT_ROW,
    "header_bg": LIGHT_HEADER_BG, "header_text": LIGHT_HEADER_TEXT,
    "input_bg": LIGHT_INPUT_BG,
    "sidebar_bg": LIGHT_SIDEBAR_BG, "sidebar_text": LIGHT_SIDEBAR_TEXT,
})

DARK_QSS = _build_qss({
    "bg": DARK_BG, "surface": DARK_SURFACE,
    "border": DARK_BORDER, "border_strong": DARK_BORDER_STRONG,
    "text": DARK_TEXT, "text_secondary": DARK_TEXT_SECONDARY,
    "hover": DARK_HOVER, "alt_row": DARK_ALT_ROW,
    "header_bg": DARK_HEADER_BG, "header_text": DARK_HEADER_TEXT,
    "input_bg": DARK_INPUT_BG,
    "sidebar_bg": DARK_SIDEBAR_BG, "sidebar_text": DARK_SIDEBAR_TEXT,
})


def apply_theme(app: QApplication, *, theme: str = "light", font_size: int = 9) -> None:
    """Apply QSS theme, Fluent integration, and base font.

    theme: 'light' | 'dark'
    font_size: base font size in points (9 = ~12px on Windows)
    """
    if theme == "dark":
        app.setStyleSheet(DARK_QSS)
    else:
        app.setStyleSheet(LIGHT_QSS)

    # Apply qfluentwidgets native theme
    try:
        from ui.fluent_compat import apply_qfluent_accent, apply_qfluent_theme
        apply_qfluent_theme(theme)
        apply_qfluent_accent(ACCENT)
    except Exception:
        pass

    f: QFont = app.font()
    if font_size and font_size > 0:
        f.setPointSize(int(font_size))
        app.setFont(f)


def current_accent() -> str:
    return ACCENT
