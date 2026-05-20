"""ATPP theme — light-only QSS with orange accent + Fluent runtime.

All chrome (title/activity bars), sidebar, and editor are light-themed.
Status bar is orange accent. Dark theme removed.
"""
from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════════════
# Brand
# ═══════════════════════════════════════════════════════════════════════════
import logging

from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication

_logger = logging.getLogger(__name__)
ACCENT_DEFAULT    = "#f97316"   # orange-500
ACCENT_HOVER      = "#ea580c"   # orange-600
ACCENT_PRESSED    = "#c2410c"   # orange-700
ACCENT_FG         = "#ffffff"
ACCENT_TINT_LIGHT = "rgba(249,115,22,0.10)"
ACCENT_TINT_DARK  = "rgba(249,115,22,0.18)"

# ═══════════════════════════════════════════════════════════════════════════
# Chrome (title bar, activity bar) — theme-aware
# ═══════════════════════════════════════════════════════════════════════════
CHROME_TITLE_BG    = "#1e293b"
CHROME_ACTIVITY_BG = "#0b1220"
CHROME_BORDER      = "#1e293b"
CHROME_TEXT        = "#e2e8f0"
CHROME_TEXT_MUTE   = "#94a3b8"
CHROME_TEXT_DIM    = "#64748b"
CHROME_HOVER       = "#1e293b"

# ═══════════════════════════════════════════════════════════════════════════
# Sidebar (theme-aware)
# ═══════════════════════════════════════════════════════════════════════════
SIDEBAR_BG_DARK   = "#0f172a"
SIDEBAR_BG_LIGHT  = "#f8fafc"
SIDEBAR_BORDER_DK = "#1e293b"
SIDEBAR_BORDER_LT = "#e2e8f0"

# ═══════════════════════════════════════════════════════════════════════════
# Editor / workspace (theme-aware)
# ═══════════════════════════════════════════════════════════════════════════
EDITOR_BG_DARK    = "#0f172a"
EDITOR_BG_LIGHT   = "#ffffff"
EDITOR_CARD_DARK  = "#1e293b"
EDITOR_CARD_LIGHT = "#f8fafc"
EDITOR_BORDER_DK  = "#334155"
EDITOR_BORDER_LT  = "#e2e8f0"
EDITOR_TAB_DARK   = "#1e293b"
EDITOR_TAB_LIGHT  = "#f1f5f9"

# ═══════════════════════════════════════════════════════════════════════════
# Text
# ═══════════════════════════════════════════════════════════════════════════
TEXT_PRIMARY_DK = "#e2e8f0"
TEXT_PRIMARY_LT = "#0f172a"
TEXT_MUTE_DK    = "#94a3b8"
TEXT_MUTE_LT    = "#475569"
TEXT_DIM_DK     = "#64748b"
TEXT_DIM_LT     = "#94a3b8"

# ═══════════════════════════════════════════════════════════════════════════
# Input (theme-aware)
# ═══════════════════════════════════════════════════════════════════════════
INPUT_BG_DARK  = "#0b1220"
INPUT_BG_LIGHT = "#ffffff"

# ═══════════════════════════════════════════════════════════════════════════
# Semantic
# ═══════════════════════════════════════════════════════════════════════════
SEM_DANGER       = "#ef4444"
SEM_DANGER_HOVER = "#dc2626"
SEM_SUCCESS      = "#22c55e"
SEM_WARNING      = "#f59e0b"
SEM_INFO         = "#3b82f6"

# ═══════════════════════════════════════════════════════════════════════════
# Status bar (always orange brand)
# ═══════════════════════════════════════════════════════════════════════════
STATUS_BG = ACCENT_DEFAULT
STATUS_FG = "#ffffff"


def _build_qss(theme: str) -> str:
    """Build full QSS for the given theme (light-only, dark removed)."""
    is_dark = False  # dark theme removed — always light

    # ── Resolve theme-dependent tokens ──
    bg          = EDITOR_BG_LIGHT
    surface     = EDITOR_CARD_LIGHT
    editor_border = EDITOR_BORDER_LT
    tab_bg      = EDITOR_TAB_LIGHT
    sb_bg       = SIDEBAR_BG_LIGHT
    sb_border   = SIDEBAR_BORDER_LT
    text        = TEXT_PRIMARY_LT
    text_mute   = TEXT_MUTE_LT
    text_dim    = TEXT_DIM_LT
    input_bg    = INPUT_BG_LIGHT
    accent_tint = ACCENT_TINT_LIGHT
    dialog_bg   = EDITOR_CARD_LIGHT
    alt_row     = "#f8fafc"
    hover_bg    = "#f1f5f9"
    scrollbar_bg= "#cbd5e1"
    scrollbar_hv= "#94a3b8"

    # ── Chrome (title bar, activity bar) — theme-aware ──
    chrome_title_bg    = CHROME_TITLE_BG    if is_dark else "#f8fafc"
    chrome_activity_bg = CHROME_ACTIVITY_BG if is_dark else "#f1f5f9"
    chrome_border      = CHROME_BORDER      if is_dark else "#e2e8f0"
    chrome_text        = CHROME_TEXT        if is_dark else TEXT_PRIMARY_LT
    chrome_text_mute   = CHROME_TEXT_MUTE   if is_dark else TEXT_MUTE_LT

    # ── Title bar search (used to be hardcoded dark) ──
    title_search_bg    = "#0b1220" if is_dark else "#ffffff"
    title_search_border = "#334155" if is_dark else "#e2e8f0"

    # ── Activity button states (used to be hardcoded dark) ──
    activity_btn_text   = "#9ca3af"  if is_dark else "#64748b"
    activity_btn_hover_bg  = "#1e293b" if is_dark else "#e2e8f0"
    activity_btn_hover_fg  = "#ffffff" if is_dark else "#0f172a"
    activity_btn_checked_fg = "#ffffff" if is_dark else ACCENT_DEFAULT

    return f"""
/* ══════════════════════════════════════════════════════════════════════════
   BASE — all themes
   ══════════════════════════════════════════════════════════════════════════ */
QWidget {{ color: {text}; background: {bg}; }}
QMainWindow {{ background: {bg}; }}
QDialog {{ background: {dialog_bg}; }}

QLabel {{ color: {text}; background: transparent; }}
QCheckBox, QRadioButton {{ color: {text}; background: transparent; }}

/* Qt6: these widgets don't inherit parent background — must be explicit */
QTabBar {{ background: transparent; }}
QScrollArea {{ background: transparent; }}
QScrollArea > QWidget#qt_scrollarea_viewport {{ background: transparent; }}

/* ══════════════════════════════════════════════════════════════════════════
   TITLE BAR — theme-aware
   ══════════════════════════════════════════════════════════════════════════ */
QWidget#title_bar {{
    background: {chrome_title_bg}; border-bottom: 1px solid {chrome_border};
}}
QLabel#title_logo {{
    background: {ACCENT_DEFAULT}; color: white;
    border-radius: 3px; font-weight: 700; font-size: 11px;
}}
QLabel#title_name {{
    color: {chrome_text}; font-weight: 600; font-size: 12px; background: transparent;
}}
QLabel#title_page {{
    color: {chrome_text_mute}; font-size: 12px; background: transparent;
}}
QLineEdit#title_search {{
    background: {title_search_bg}; color: {chrome_text};
    border: 1px solid {title_search_border}; border-radius: 4px;
    padding: 2px 8px; font-size: 11px;
}}
QLineEdit#title_search:focus {{ border-color: {ACCENT_DEFAULT}; }}

/* ══════════════════════════════════════════════════════════════════════════
   ACTIVITY BAR — theme-aware
   ══════════════════════════════════════════════════════════════════════════ */
QWidget#activity_bar {{
    background: {chrome_activity_bg}; border-right: 1px solid {chrome_border};
}}
QPushButton[role="activity-btn"] {{
    background: transparent; color: {activity_btn_text}; border: none;
    border-left: 3px solid transparent; border-radius: 0;
    text-align: center; font-size: 18px; padding: 0;
}}
QPushButton[role="activity-btn"]:hover {{
    background: {activity_btn_hover_bg}; color: {activity_btn_hover_fg};
}}
QPushButton[role="activity-btn"]:checked {{
    background: {accent_tint}; color: {activity_btn_checked_fg};
    border-left: 3px solid {ACCENT_DEFAULT};
}}

/* ══════════════════════════════════════════════════════════════════════════
   STATUS BAR — always orange
   ══════════════════════════════════════════════════════════════════════════ */
QStatusBar#main_statusbar {{
    background: {STATUS_BG}; color: {STATUS_FG};
    border: none; padding: 0 12px; min-height: 24px; font-size: 11px;
}}
QStatusBar#main_statusbar::item {{ border: none; }}
QStatusBar#main_statusbar QLabel {{
    color: {STATUS_FG}; background: transparent; padding: 0 6px;
}}
QStatusBar#main_statusbar QLabel[role="sep"] {{
    color: rgba(255,255,255,0.4); padding: 0 4px;
}}

/* ══════════════════════════════════════════════════════════════════════════
   SIDEBAR — theme-aware
   ══════════════════════════════════════════════════════════════════════════ */
QWidget#nav_panel {{
    background-color: {sb_bg}; color: {text}; border: none; border-radius: 0;
}}
QFrame#nav_section_header {{
    background: transparent; border-bottom: 1px solid {sb_border};
    padding: 0 16px; min-height: 40px;
}}
QLabel#nav_section_title {{
    color: {text_mute}; font-size: 11px; font-weight: 700;
    letter-spacing: 0.5px; text-transform: uppercase;
}}
QFrame#nav_section_header QPushButton {{
    background: transparent; color: {text_mute}; border: none;
    font-size: 14px; padding: 4px 8px;
}}
QFrame#nav_section_header QPushButton:hover {{ color: {text}; }}

QTabWidget#nav_inner_tabs::pane {{ border: none; background: {sb_bg}; }}
QTabWidget#nav_inner_tabs QTabBar {{ background: {sb_bg}; }}
QTabWidget#nav_inner_tabs QTabBar::tab {{
    background: transparent; color: {text_dim};
    padding: 8px 14px; border: none;
    border-bottom: 2px solid transparent; font-size: 12px;
}}
QTabWidget#nav_inner_tabs QTabBar::tab:selected {{
    color: {ACCENT_DEFAULT}; border-bottom-color: {ACCENT_DEFAULT}; font-weight: 600;
}}

QLineEdit#nav_filter {{
    background: {input_bg}; color: {text};
    border: 1px solid {sb_border}; border-radius: 4px;
    padding: 6px 10px; font-size: 12px;
    margin: 0 12px 8px 12px;
}}
QLineEdit#nav_filter:focus {{ border-color: {ACCENT_DEFAULT}; }}

QTreeWidget#nav_tree, QTreeView#nav_tree {{
    background: transparent; color: {text};
    border: none; padding: 0 4px;
    selection-background-color: {accent_tint};
    selection-color: {ACCENT_DEFAULT};
}}
QTreeWidget#nav_tree::item, QTreeView#nav_tree::item {{
    padding: 4px 6px; border-radius: 4px;
}}
QTreeWidget#nav_tree::item:hover {{ background: {hover_bg}; }}
QTreeWidget#nav_tree::item:selected {{
    background: {accent_tint}; color: {ACCENT_DEFAULT};
    border-left: 2px solid {ACCENT_DEFAULT};
}}

QFrame#nav_quick {{
    background: transparent; border-top: 1px solid {sb_border}; padding: 10px 12px;
}}
QFrame#nav_quick QPushButton {{
    background: {surface}; color: {text};
    border: 1px solid {sb_border}; border-radius: 4px;
    padding: 6px 12px; font-size: 11px; font-weight: 500;
}}
QFrame#nav_quick QPushButton:hover {{ border-color: {ACCENT_DEFAULT}; color: {ACCENT_DEFAULT}; }}

QFrame#nav_user {{
    background: transparent; border-top: 1px solid {sb_border}; padding: 10px 12px;
}}
QLabel#nav_user_avatar {{
    background: {ACCENT_DEFAULT}; color: white; border-radius: 16px;
    min-width: 32px; max-width: 32px; min-height: 32px; max-height: 32px;
    font-weight: 600;
}}
QLabel#nav_user_name {{
    color: {text}; font-size: 12px; font-weight: 500; background: transparent;
}}
QLabel#nav_user_role {{
    color: {text_mute}; font-size: 10px; background: transparent;
}}

QWidget#nav_panel QScrollBar:vertical {{ background: transparent; width: 6px; }}
QWidget#nav_panel QScrollBar::handle:vertical {{
    background: {sb_border}; border-radius: 3px;
}}
QWidget#nav_panel QScrollBar::handle:vertical:hover {{ background: {text_dim}; }}
QWidget#nav_panel QScrollBar::sub-line, QWidget#nav_panel QScrollBar::add-line {{ height: 0; }}

/* ══════════════════════════════════════════════════════════════════════════
   EDITOR TABS
   ══════════════════════════════════════════════════════════════════════════ */
QTabWidget#editor_tabs::pane {{
    background: {bg}; border-top: 1px solid {editor_border};
}}
QTabWidget#editor_tabs QTabBar {{
    background: {bg};
}}
QTabWidget#editor_tabs QTabBar::tab {{
    background: {tab_bg}; color: {text_mute};
    padding: 8px 16px; border: none;
    border-right: 1px solid {editor_border};
    min-width: 100px; max-width: 240px; font-size: 12px;
}}
QTabWidget#editor_tabs QTabBar::tab:selected {{
    background: {bg}; color: {text};
    border-bottom: 2px solid {ACCENT_DEFAULT}; font-weight: 600;
}}
QTabWidget#editor_tabs QTabBar::tab:hover:!selected {{ color: {text}; }}
QTabWidget#editor_tabs QTabBar::close-button:hover {{
    background: {hover_bg}; border-radius: 2px;
}}

/* Editor inner tabs */
QTabWidget#editor_inner_tabs::pane {{ border: none; background: {bg}; }}
QTabWidget#editor_inner_tabs QTabBar {{ background: {bg}; }}
QTabWidget#editor_inner_tabs QTabBar::tab {{
    background: transparent; color: {text_mute};
    padding: 8px 16px; border: none;
    border-bottom: 2px solid transparent; font-size: 12px;
}}
QTabWidget#editor_inner_tabs QTabBar::tab:selected {{
    color: {ACCENT_DEFAULT}; border-bottom-color: {ACCENT_DEFAULT}; font-weight: 600;
}}

/* ══════════════════════════════════════════════════════════════════════════
   BUTTONS
   ══════════════════════════════════════════════════════════════════════════ */
QPushButton {{
    background: {surface}; color: {text}; border: 1px solid {editor_border};
    border-radius: 6px; padding: 6px 14px; font-weight: 500;
}}
QPushButton:hover {{ background: {hover_bg}; border-color: {text_mute}; }}
QPushButton:pressed {{ background: {tab_bg}; }}
QPushButton:disabled {{ color: {text_dim}; background: {hover_bg}; border-color: {editor_border}; }}
QPushButton[primary="true"] {{
    background: {ACCENT_DEFAULT}; color: white; border: none; font-weight: 600;
}}
QPushButton[primary="true"]:hover {{ background: {ACCENT_HOVER}; }}
QPushButton[primary="true"]:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton[primary="true"]:disabled {{ background: #fdba74; }}
QPushButton[danger="true"] {{
    background: transparent; color: {SEM_DANGER};
    border: 1px solid {SEM_DANGER}; font-weight: 600;
}}
QPushButton[danger="true"]:hover {{
    background: rgba(239,68,68,0.1); border-color: {SEM_DANGER_HOVER}; color: {SEM_DANGER_HOVER};
}}

/* ══════════════════════════════════════════════════════════════════════════
   INPUTS
   ══════════════════════════════════════════════════════════════════════════ */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background: {input_bg}; color: {text}; border: 1px solid {editor_border};
    border-radius: 6px; padding: 6px 10px;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT_DEFAULT};
}}
QComboBox {{
    background: {input_bg}; color: {text}; border: 1px solid {editor_border};
    border-radius: 6px; padding: 6px 10px;
}}
QComboBox:focus {{ border-color: {ACCENT_DEFAULT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {surface}; border: 1px solid {editor_border}; border-radius: 6px;
    selection-background-color: {accent_tint}; selection-color: {ACCENT_DEFAULT};
}}

/* ══════════════════════════════════════════════════════════════════════════
   TABLES & TREES
   ══════════════════════════════════════════════════════════════════════════ */
QTableWidget, QTreeWidget, QListWidget, QTableView, QTreeView, QListView {{
    background: {surface}; color: {text}; border: 1px solid {editor_border};
    border-radius: 8px; font-size: 13px;
    alternate-background-color: {alt_row};
    selection-background-color: {accent_tint}; selection-color: {ACCENT_DEFAULT};
}}
QTableWidget::item:hover, QTreeWidget::item:hover, QListWidget::item:hover,
QTableView::item:hover, QTreeView::item:hover {{ background: {hover_bg}; }}
QHeaderView::section {{
    background: {surface}; color: {text_mute}; border: none;
    border-bottom: 1px solid {editor_border}; padding: 8px 12px;
    font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;
}}

/* ══════════════════════════════════════════════════════════════════════════
   MENU
   ══════════════════════════════════════════════════════════════════════════ */
QMenuBar {{ background: {surface}; color: {text}; border-bottom: 1px solid {editor_border}; padding: 2px; }}
QMenuBar::item:selected {{ background: {hover_bg}; border-radius: 4px; }}
QMenu {{
    background: {surface}; color: {text}; border: 1px solid {editor_border};
    border-radius: 8px; padding: 4px;
}}
QMenu::item {{ padding: 6px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background: {accent_tint}; color: {ACCENT_DEFAULT}; }}
QMenu::separator {{ height: 1px; background: {editor_border}; margin: 4px 8px; }}

/* ══════════════════════════════════════════════════════════════════════════
   WELCOME SCREEN
   ══════════════════════════════════════════════════════════════════════════ */
QWidget#welcome {{ background: {bg}; }}
QLabel#welcome_icon {{ color: {ACCENT_DEFAULT}; font-size: 72px; background: transparent; }}
QLabel#welcome_title {{ color: {text}; font-size: 28px; font-weight: 700; background: transparent; }}
QLabel#welcome_subtitle {{ color: {text_mute}; font-size: 13px; background: transparent; }}
QPushButton[role="welcome-chip"] {{
    background: {surface}; color: {text};
    border: 1px solid {editor_border}; border-radius: 6px;
    padding: 10px 20px; font-size: 12px; min-width: 200px;
}}
QPushButton[role="welcome-chip"]:hover {{ border-color: {ACCENT_DEFAULT}; color: {ACCENT_DEFAULT}; }}
QLabel#welcome_recent_lbl {{ color: {text_mute}; font-size: 11px; font-weight: 600; }}
QLabel[role="welcome-recent"] {{ color: {text}; font-size: 12px; padding: 4px; }}

/* ══════════════════════════════════════════════════════════════════════════
   FORM CARD
   ══════════════════════════════════════════════════════════════════════════ */
QFrame[role="form-card"] {{
    background: {surface}; border: 1px solid {editor_border}; border-radius: 8px;
}}

/* ══════════════════════════════════════════════════════════════════════════
   SCROLLBARS (global)
   ══════════════════════════════════════════════════════════════════════════ */
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {scrollbar_bg}; border-radius: 4px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {scrollbar_hv}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: {scrollbar_bg}; border-radius: 4px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background: {scrollbar_hv}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ══════════════════════════════════════════════════════════════════════════
   MISC
   ══════════════════════════════════════════════════════════════════════════ */
QGroupBox {{ font-weight: 600; border: 1px solid {editor_border}; border-radius: 8px; margin-top: 12px; padding-top: 16px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}
QSplitter::handle {{ background: {editor_border}; }}
QSplitter::handle:hover {{ background: {ACCENT_DEFAULT}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QToolTip {{ background: {chrome_title_bg}; color: {chrome_text}; border-radius: 6px; padding: 6px 10px; font-size: 12px; }}
QDockWidget {{ titlebar-close-icon: none; }}
QDockWidget::title {{ background: {surface}; padding: 6px 12px; border-bottom: 1px solid {editor_border}; }}
QProgressBar {{ background: {editor_border}; border-radius: 4px; height: 8px; }}
QProgressBar::chunk {{ background: {ACCENT_DEFAULT}; border-radius: 4px; }}
QMessageBox {{ background: {dialog_bg}; }}
QMessageBox QLabel {{ color: {text}; }}

/* Legacy toolbar — hidden in VSCode layout, but kept harmless */
QToolBar {{ background: {surface}; border-bottom: 1px solid {editor_border}; spacing: 6px; padding: 4px 8px; }}
QToolBar QPushButton {{
    background: transparent; color: {text_mute}; border: 1px solid {editor_border};
    border-radius: 6px; padding: 5px 12px; font-size: 12px; font-weight: 500;
}}
QToolBar QPushButton:hover {{ background: {hover_bg}; color: {text}; }}
QToolBar QPushButton[primary="true"] {{ background: {ACCENT_DEFAULT}; color: white; border: none; }}
QToolBar QPushButton[primary="true"]:hover {{ background: {ACCENT_HOVER}; }}
"""


# Legacy aliases — some external code may reference these
LIGHT_QSS = _build_qss("light")
DARK_QSS  = _build_qss("dark")


def _apply_fluent_runtime(accent_color: str) -> None:
    try:
        from qfluentwidgets import Theme, setTheme, setThemeColor
    except Exception:
        return
    try:
        setTheme(Theme.LIGHT)
        setThemeColor(QColor(accent_color))
    except Exception:
        _logger.exception("Unhandled error")


def apply_theme(
    app: QApplication,
    *,
    theme: str = "light",
    font_size: int = 9,
    accent_color: str = ACCENT_DEFAULT,
) -> None:
    # 0. Force light palette — overrides Windows dark mode at Qt level
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#0f172a"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#f97316"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#f97316"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#f97316"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    # 1. Font
    f: QFont = app.font()
    if font_size and font_size > 0:
        f.setPointSize(int(font_size))
        app.setFont(f)

    # 2. QSS — must be the last word on styling
    qss = _build_qss("light")
    app.setStyleSheet(qss)

    # Force all widgets to pick up the new QSS
    app.processEvents()
    for w in app.allWidgets():
        try:
            w.style().unpolish(w)
            w.style().polish(w)
        except RuntimeError:
            _logger.exception("Failed to polish widget style")
            pass


__all__ = [
    "ACCENT_DEFAULT", "ACCENT_HOVER", "ACCENT_PRESSED", "ACCENT_FG",
    "ACCENT_TINT_LIGHT", "ACCENT_TINT_DARK",
    "CHROME_TITLE_BG", "CHROME_ACTIVITY_BG", "CHROME_BORDER",
    "CHROME_TEXT", "CHROME_TEXT_MUTE", "CHROME_TEXT_DIM", "CHROME_HOVER",
    "SIDEBAR_BG_DARK", "SIDEBAR_BG_LIGHT", "SIDEBAR_BORDER_DK", "SIDEBAR_BORDER_LT",
    "EDITOR_BG_DARK", "EDITOR_BG_LIGHT", "EDITOR_CARD_DARK", "EDITOR_CARD_LIGHT",
    "EDITOR_BORDER_DK", "EDITOR_BORDER_LT", "EDITOR_TAB_DARK", "EDITOR_TAB_LIGHT",
    "TEXT_PRIMARY_DK", "TEXT_PRIMARY_LT", "TEXT_MUTE_DK", "TEXT_MUTE_LT",
    "TEXT_DIM_DK", "TEXT_DIM_LT",
    "INPUT_BG_DARK", "INPUT_BG_LIGHT",
    "SEM_DANGER", "SEM_DANGER_HOVER", "SEM_SUCCESS", "SEM_WARNING", "SEM_INFO",
    "STATUS_BG", "STATUS_FG",
    "LIGHT_QSS", "DARK_QSS",
    "apply_theme",
]
