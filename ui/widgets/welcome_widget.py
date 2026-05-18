"""Welcome screen — shown when no editor tabs are open."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal


class WelcomeWidget(QWidget):
    new_product_clicked = pyqtSignal()
    new_tp_clicked = pyqtSignal()
    open_dashboard_clicked = pyqtSignal()
    search_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("welcome")
        v = QVBoxLayout(self)
        v.setContentsMargins(40, 40, 40, 40)
        v.setSpacing(16)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addStretch()

        icon = QLabel("⧗")
        icon.setObjectName("welcome_icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(icon)

        title = QLabel("ATPP System")
        title.setObjectName("welcome_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        sub = QLabel(
            "Система автоматизации технологической подготовки производства")
        sub.setObjectName("welcome_subtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(sub)

        v.addSpacing(24)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(12)
        for txt, sig in [
            ("⌃P  Поиск по системе", self.search_clicked),
            ("⌃N  Новое изделие",   self.new_product_clicked),
            ("⌃T  Новый ТП",        self.new_tp_clicked),
            ("⌃D  Открыть дашборд", self.open_dashboard_clicked),
        ]:
            btn = QPushButton(txt)
            btn.setProperty("role", "welcome-chip")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(sig)
            chips_row.addWidget(btn)
        v.addLayout(chips_row)

        v.addSpacing(40)

        recent_lbl = QLabel("Недавнее")
        recent_lbl.setObjectName("welcome_recent_lbl")
        recent_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(recent_lbl)

        for item in [
            "P-001-001 — Корпус (изделие)",
            "ТП-2024-038 — Фрезерная (ТП)",
            "P-002 — Вал ведущий (изделие)",
        ]:
            lbl = QLabel(item)
            lbl.setProperty("role", "welcome-recent")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(lbl)

        v.addStretch()
