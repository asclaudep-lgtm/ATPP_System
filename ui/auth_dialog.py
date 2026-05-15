"""
Auth dialog — Fluent Design (Win11 style, orange accent).
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QLineEdit, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor
import os
from typing import Optional

from config import APP_NAME, APP_VERSION
from ui.fluent_compat import (
    QFLUENT_AVAILABLE,
    BodyLabel,
    FluentIcon,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    TitleLabel,
)


class AuthDialog(QDialog):
    """Login dialog — Fluent Design."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.user = None
        self.login_attempts = 0
        self.max_attempts = 5

        self.setWindowTitle("Авторизация")
        self.setFixedSize(440, 520)
        self.setModal(True)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(32, 24, 32, 24)

        # Logo
        logo_label = BodyLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pix = self._load_logo()
        logo_label.setPixmap(logo_pix)
        layout.addWidget(logo_label)

        # App title
        title = TitleLabel(APP_NAME)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Version
        version = BodyLabel(f"Версия {APP_VERSION}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        layout.addSpacing(8)

        # Login field
        login_label = SubtitleLabel("Логин")
        layout.addWidget(login_label)
        self.login_input = LineEdit()
        self.login_input.setPlaceholderText("Введите логин")
        self.login_input.returnPressed.connect(self.on_login)
        layout.addWidget(self.login_input)

        layout.addSpacing(4)

        # Password field
        password_label = SubtitleLabel("Пароль")
        layout.addWidget(password_label)

        if QFLUENT_AVAILABLE and PasswordLineEdit is not None:
            self.password_input = PasswordLineEdit()
            self.password_input.setPlaceholderText("Введите пароль")
        else:
            # Fallback: manual password field + eye button
            self.password_input = LineEdit()
            self.password_input.setPlaceholderText("Введите пароль")
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.on_login)
        layout.addWidget(self.password_input)

        # Fallback visibility toggle (only when qfluentwidgets isn't available)
        if not QFLUENT_AVAILABLE:
            self.show_password_btn = PushButton("👁")
            self.show_password_btn.setFixedWidth(36)
            self.show_password_btn.setCheckable(True)
            self.show_password_btn.toggled.connect(self.toggle_password_visibility)
            layout.addWidget(self.show_password_btn)
        else:
            self.show_password_btn = None

        layout.addSpacing(4)

        # Remember me
        self.remember_checkbox = QCheckBox("Запомнить меня")
        layout.addWidget(self.remember_checkbox)

        layout.addSpacing(12)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        self.login_btn = PrimaryPushButton("Войти")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self.on_login)

        cancel_btn = PushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(self.login_btn)
        layout.addLayout(buttons_layout)

        # Hint
        hint = BodyLabel("Обратитесь к администратору для получения учётных данных")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self.setLayout(layout)
        self.login_input.setFocus()

    def _load_logo(self) -> QPixmap:
        logo_path = self._find_logo_path()
        if logo_path and os.path.exists(logo_path):
            px = QPixmap(logo_path)
            if not px.isNull():
                return px.scaled(
                    200, 120,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        # Programmatic fallback logo
        px = QPixmap(120, 120)
        px.fill(QColor("white"))
        painter = QPainter(px)
        painter.setPen(QColor("#2c3e50"))
        painter.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "УЗГА")
        painter.end()
        return px

    def toggle_password_visibility(self, checked):
        if checked:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

    def on_login(self):
        username = self.login_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля")
            return

        if self.login_attempts >= self.max_attempts:
            QMessageBox.critical(
                self,
                "Блокировка",
                f"Превышено количество попыток входа ({self.max_attempts})\n"
                "Приложение будет закрыто.",
            )
            self.reject()
            return

        user = self.db_manager.authenticate_user(username, password)
        if user:
            self.user = user
            self.accept()
        else:
            self.login_attempts += 1
            remaining = self.max_attempts - self.login_attempts
            if remaining > 0:
                QMessageBox.warning(
                    self,
                    "Ошибка входа",
                    f"Неверный логин или пароль\nОсталось попыток: {remaining}",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Блокировка",
                    "Превышено количество попыток входа\nПриложение будет закрыто.",
                )
                self.reject()
            self.password_input.clear()
            self.password_input.setFocus()

    def get_user(self):
        return self.user

    def _find_logo_path(self) -> Optional[str]:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        candidates = [
            os.path.join(os.getcwd(), "assets", "logo.png"),
            os.path.join(os.getcwd(), "logo.png"),
            os.path.join(base_dir, "assets", "logo.png"),
            os.path.join(base_dir, "assets", "logo.jpg"),
            os.path.join(base_dir, "logo.png"),
            os.path.join(base_dir, "assets", "logo.svg"),
            os.path.join(base_dir, "logo.svg"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None
