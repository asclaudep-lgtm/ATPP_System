"""
Диалог авторизации (Fluent Design).

Использует виджеты ``qfluentwidgets`` при наличии библиотеки; если её нет —
автоматически откатывается на стандартные PyQt6-виджеты, чтобы не ломать
запуск в окружениях, где qfluentwidgets ещё не установлен.
"""

import logging
import os
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QVBoxLayout

from config import (  # noqa: F401  (APP_NAME may be referenced elsewhere)
    APP_NAME,
    APP_VERSION,
)

log = logging.getLogger(__name__)

# Fluent-виджеты подключаются опционально — если библиотека отсутствует,
# используются эквивалентные стандартные виджеты PyQt6.
try:
    from qfluentwidgets import (
        BodyLabel,
        CheckBox,
        FluentIcon,
        LineEdit,
        PasswordLineEdit,
        PrimaryPushButton,
        PushButton,
        SubtitleLabel,
        TitleLabel,
    )

    _FLUENT = True
except Exception as e:  # pragma: no cover - exercised only without qfluentwidgets
    log.debug("qfluentwidgets unavailable, using PyQt6 fallback widgets: %s", e)
    from PyQt6.QtWidgets import QCheckBox as CheckBox  # type: ignore
    from PyQt6.QtWidgets import QLabel as _PlainLabel
    from PyQt6.QtWidgets import QLineEdit as LineEdit  # type: ignore
    from PyQt6.QtWidgets import QPushButton as PrimaryPushButton  # type: ignore
    from PyQt6.QtWidgets import QPushButton as PushButton  # type: ignore

    class _StyledLabel(_PlainLabel):
        _font_size = 14
        _font_weight = QFont.Weight.Normal

        def __init__(self, text: str = "", parent=None):
            super().__init__(text, parent)
            f = self.font()
            f.setPointSize(self._font_size)
            f.setWeight(self._font_weight)
            self.setFont(f)

    class TitleLabel(_StyledLabel):  # type: ignore
        _font_size = 22
        _font_weight = QFont.Weight.DemiBold

    class SubtitleLabel(_StyledLabel):  # type: ignore
        _font_size = 16
        _font_weight = QFont.Weight.DemiBold

    class BodyLabel(_StyledLabel):  # type: ignore
        _font_size = 10
        _font_weight = QFont.Weight.Normal

    class PasswordLineEdit(LineEdit):  # type: ignore
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setEchoMode(LineEdit.EchoMode.Password)

    FluentIcon = None  # type: ignore
    _FLUENT = False


class AuthDialog(QDialog):
    """Диалог авторизации пользователя (Fluent style)."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.user = None
        self.login_attempts = 0
        self.max_attempts = 5

        self.setWindowTitle("Авторизация")
        self.setFixedSize(440, 540)
        self.setModal(True)

        self.init_ui()

    # ------------------------------------------------------------- UI
    def init_ui(self):
        """Инициализация интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        # Логотип
        layout.addWidget(
            self._build_logo_label(),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        # Заголовок и подзаголовок
        title = TitleLabel("УЗГА-Инжиниринг")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = SubtitleLabel("АТПП — Авторизация")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        version_label = BodyLabel(f"Версия {APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setProperty("muted", True)
        layout.addWidget(version_label)

        layout.addSpacing(16)

        # Поле логина
        login_row = QHBoxLayout()
        login_label = BodyLabel("Логин:")
        login_label.setFixedWidth(96)
        self.login_input = LineEdit()
        self.login_input.setPlaceholderText("Введите логин")
        self.login_input.returnPressed.connect(self.on_login)
        login_row.addWidget(login_label)
        login_row.addWidget(self.login_input)
        layout.addLayout(login_row)

        # Поле пароля. PasswordLineEdit из qfluentwidgets уже умеет показать/спрятать
        # символы по встроенной иконке-глазу — отдельная кнопка не нужна.
        password_row = QHBoxLayout()
        password_label = BodyLabel("Пароль:")
        password_label.setFixedWidth(96)
        self.password_input = PasswordLineEdit()
        self.password_input.setPlaceholderText("Введите пароль")
        self.password_input.returnPressed.connect(self.on_login)
        password_row.addWidget(password_label)
        password_row.addWidget(self.password_input)
        layout.addLayout(password_row)

        # Запомнить меня
        self.remember_checkbox = CheckBox("Запомнить меня")
        layout.addWidget(self.remember_checkbox)

        layout.addSpacing(8)

        # Кнопки
        buttons_row = QHBoxLayout()
        self.login_btn = PrimaryPushButton("Войти")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self.on_login)

        cancel_btn = PushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)

        # Иконки только если qfluentwidgets установлен и FluentIcon доступен.
        if _FLUENT and FluentIcon is not None:
            try:
                self.login_btn.setIcon(FluentIcon.ACCEPT)
                cancel_btn.setIcon(FluentIcon.CANCEL)
            except Exception:
                _logger.exception("Unhandled error")

        buttons_row.addWidget(self.login_btn)
        buttons_row.addWidget(cancel_btn)
        layout.addLayout(buttons_row)

        # Подсказка
        hint_label = BodyLabel(
            "Обратитесь к администратору для получения учётных данных"
        )
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setWordWrap(True)
        hint_label.setProperty("muted", True)
        layout.addWidget(hint_label)

        # Фокус на поле логина
        self.login_input.setFocus()

    def _build_logo_label(self) -> QLabel:
        """Загрузить логотип из файла, иначе нарисовать программно."""
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_pix: Optional[QPixmap] = None
        try:
            logo_path = self._find_logo_path()
            if logo_path and os.path.exists(logo_path):
                logo_pix = QPixmap(logo_path)
                if not logo_pix.isNull():
                    logo_pix = logo_pix.scaled(
                        200,
                        120,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
        except Exception:
            logo_pix = None

        if logo_pix is None or logo_pix.isNull():
            logo_pix = QPixmap(120, 120)
            logo_pix.fill(QColor("white"))
            painter = QPainter(logo_pix)
            painter.setPen(QColor("#f97316"))  # ACCENT_DEFAULT
            painter.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
            painter.drawText(logo_pix.rect(), Qt.AlignmentFlag.AlignCenter, "УЗГА")
            painter.end()

        logo_label.setPixmap(logo_pix)
        return logo_label

    # --------------------------------------------------------- handlers
    def on_login(self):
        """Обработка нажатия «Войти»."""
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
            return

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
        """Получить авторизованного пользователя."""
        return self.user

    def _find_logo_path(self) -> Optional[str]:
        """Попытаться найти логотип в наиболее распространённых местах."""
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
        for path in candidates:
            if os.path.exists(path):
                return path
        return None
