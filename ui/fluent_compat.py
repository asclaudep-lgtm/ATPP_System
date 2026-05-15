"""
Fluent widget compatibility layer.

Provides drop-in Fluent-widget imports with graceful fallback to PyQt6.
Usage: `from ui.fluent_compat import PrimaryPushButton, LineEdit, ...`
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit as _QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton as _QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QTreeWidget,
    QVBoxLayout,
)

# ---------------------------------------------------------------------------
# Try to load qfluentwidgets
# ---------------------------------------------------------------------------
_qfw = False
_qfw_theme = None
_qfw_setTheme = None

try:
    import qfluentwidgets  # noqa: F401
    from qfluentwidgets import (  # noqa: F401
        BodyLabel,
        FluentIcon,
        LineEdit,
        MessageBoxBase,
        NavigationInterface,
        PasswordLineEdit,
        PrimaryPushButton,
        PushButton,
        StrongBodyLabel,
        SubtitleLabel,
        TableWidget,
        TitleLabel,
    )

    _qfw = True

    # qfluentwidgets.setTheme / setThemeColor
    try:
        from qfluentwidgets import setTheme as _qfw_setTheme
        from qfluentwidgets import setThemeColor as _qfw_setThemeColor
        from qfluentwidgets import Theme as _qfw_theme
    except ImportError:
        _qfw_setTheme = None
        _qfw_setThemeColor = None
        _qfw_theme = None

except ImportError:
    _qfw = False

# ---------------------------------------------------------------------------
# Fallback stubs when qfluentwidgets is not installed
# ---------------------------------------------------------------------------

if not _qfw:
    class _FluentPushButton(_QPushButton):
        """qfluentwidgets-compatible push button stub."""
        def __init__(self, text: str = "", parent=None):
            super().__init__(text, parent)

    class _FluentPrimaryPushButton(_QPushButton):
        """Primary accent button — uses [primary=\"true\"] QSS property."""
        def __init__(self, text: str = "", parent=None):
            super().__init__(text, parent)
            self.setProperty("primary", True)

    class _FluentLineEdit(_QLineEdit):
        """Styled line edit."""
        pass

    class _FluentPasswordLineEdit(_QLineEdit):
        """Password field with toggle visibility."""
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setEchoMode(_QLineEdit.EchoMode.Password)

    class _FluentTitleLabel(QLabel):
        """Large section title."""
        def __init__(self, text: str = "", parent=None):
            super().__init__(text, parent)
            f = self.font()
            f.setPointSize(16)
            f.setBold(True)
            self.setFont(f)

    class _FluentSubtitleLabel(QLabel):
        """Medium subtitle."""
        def __init__(self, text: str = "", parent=None):
            super().__init__(text, parent)
            f = self.font()
            f.setPointSize(12)
            f.setBold(True)
            self.setFont(f)

    class _FluentBodyLabel(QLabel):
        """Body text."""
        def __init__(self, text: str = "", parent=None):
            super().__init__(text, parent)

    class _FluentStrongBodyLabel(QLabel):
        """Strong (bold) body text."""
        def __init__(self, text: str = "", parent=None):
            super().__init__(text, parent)
            f = self.font()
            f.setBold(True)
            self.setFont(f)

    class _FluentTableWidget(QTableWidget):
        """Table with alternating row colors handled by global QSS."""
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAlternatingRowColors(True)

    # Re-export with same names
    PushButton = _FluentPushButton
    PrimaryPushButton = _FluentPrimaryPushButton
    LineEdit = _FluentLineEdit
    PasswordLineEdit = _FluentPasswordLineEdit
    TitleLabel = _FluentTitleLabel
    SubtitleLabel = _FluentSubtitleLabel
    BodyLabel = _FluentBodyLabel
    StrongBodyLabel = _FluentStrongBodyLabel
    TableWidget = _FluentTableWidget

    class FluentIcon:
        """Stub: returns empty QIcon or a simple circle."""
        @staticmethod
        def _circle(color: str = "#0078D4") -> QIcon:
            px = QPixmap(16, 16)
            px.fill(Qt.GlobalColor.transparent)
            p = QPainter(px)
            p.setBrush(QColor(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(2, 2, 12, 12)
            p.end()
            return QIcon(px)

        @staticmethod
        def icon(name: str):
            return FluentIcon._circle()

        ADD = _circle()
        DELETE = _circle()
        EDIT = _circle()
        SAVE = _circle()
        SEARCH = _circle()
        SETTING = _circle()
        HOME = _circle()
        INFO = _circle()
        VIEW = _circle()
        HIDE = _circle()

    # NavigationInterface stub (important: this is used in main_window)
    class NavigationInterface:
        """Stub navigation interface (QTreeWidget fallback)."""
        pass

    # Message box stub
    class MessageBoxBase(QDialog):
        """Stub: simple QDialog for message boxes."""
        def __init__(self, parent=None):
            super().__init__(parent)


# ---------------------------------------------------------------------------
# Apply qfluentwidgets theme globally
# ---------------------------------------------------------------------------

def apply_qfluent_theme(theme: str = "light") -> None:
    """Apply qfluentwidgets theme.  theme: 'light' | 'dark'."""
    if not _qfw_setTheme or not _qfw_theme:
        return
    try:
        if theme == "dark":
            _qfw_setTheme(_qfw_theme.DARK)
        else:
            _qfw_setTheme(_qfw_theme.LIGHT)
    except Exception:
        pass


def apply_qfluent_accent(color: str = "#f97316") -> None:
    """Apply accent color to qfluentwidgets. Default: orange."""
    if not _qfw_setThemeColor:
        return
    try:
        _qfw_setThemeColor(color)
    except Exception:
        pass


QFLUENT_AVAILABLE: bool = _qfw
