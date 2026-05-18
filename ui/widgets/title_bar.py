"""TitleBar — slim 30px top strip.

Layout: [logo][app name][·····][page title (center)][···][search field][window controls]
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut


class TitleBar(QWidget):
    """VSCode-style title bar.

    Signals:
        search_requested(text: str)   — emitted on Enter in search field
        search_focused()              — emitted when Ctrl+P pressed
    """
    search_requested = pyqtSignal(str)
    search_focused = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("title_bar")
        self.setFixedHeight(30)

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 0, 10, 0)
        h.setSpacing(8)

        logo = QLabel("A")
        logo.setObjectName("title_logo")
        logo.setFixedSize(18, 18)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(logo)

        name = QLabel("ATPP System")
        name.setObjectName("title_name")
        h.addWidget(name)

        h.addStretch(1)

        self.page_title = QLabel("Главная")
        self.page_title.setObjectName("title_page")
        h.addWidget(self.page_title)

        h.addStretch(1)

        self.search = QLineEdit()
        self.search.setObjectName("title_search")
        self.search.setFixedWidth(360)
        self.search.setFixedHeight(22)
        self.search.setPlaceholderText("⚲  Поиск изделий, ТП, операций…    ⌃P")
        self.search.returnPressed.connect(
            lambda: self.search_requested.emit(self.search.text()))
        h.addWidget(self.search)

        QShortcut(QKeySequence("Ctrl+P"), self,
                  lambda: (self.search.setFocus(), self.search.selectAll(),
                           self.search_focused.emit()))

    def set_page_title(self, text: str):
        self.page_title.setText(text)
