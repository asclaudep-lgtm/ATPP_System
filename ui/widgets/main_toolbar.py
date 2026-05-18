"""MainToolBar — legacy shim.

Replaced by ActivityBar + TitleBar in VSCode layout.
Kept as empty class for backward compatibility with imports and tests.
"""
from PyQt6.QtWidgets import QToolBar


class MainToolBar(QToolBar):
    """Legacy toolbar — hidden, replaced by ActivityBar + TitleBar."""

    def __init__(self, user=None, current_theme=None, parent=None):
        super().__init__(parent)
        self.hide()
