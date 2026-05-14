"""
Диалог авторизации
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
import os
from typing import Optional
from config import APP_NAME, APP_VERSION


class AuthDialog(QDialog):
    """Диалог авторизации пользователя"""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.user = None
        self.login_attempts = 0
        self.max_attempts = 5
        
        self.setWindowTitle("Авторизация")
        self.setFixedSize(420, 500)
        self.setModal(True)
        
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Логотип: сначала попробуем загрузить файл, если он есть; иначе используем программную отрисовку
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Attempt to load logo from file; otherwise draw programmatically
        logo_pix = None
        try:
            logo_path = self._find_logo_path()
            if logo_path and os.path.exists(logo_path):
                logo_pix = QPixmap(logo_path)
                if not logo_pix.isNull():
                    logo_pix = logo_pix.scaled(
                        200, 120,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
        except Exception:
            logo_pix = None
        if logo_pix is None or logo_pix.isNull():
            # Построение простого графического лого программно (без зависимости от SVG/PNG файлов)
            logo_pix = QPixmap(120, 120)
            logo_pix.fill(QColor('white'))
            painter = QPainter(logo_pix)
            painter.setPen(QColor('#2c3e50'))
            painter.setFont(QFont('Arial', 18, QFont.Bold))
            painter.drawText(logo_pix.rect(), Qt.AlignmentFlag.AlignCenter, 'УЗГА')
            painter.end()
        logo_label.setPixmap(logo_pix)
        layout.addWidget(logo_label)

        
        # Версия
        version_label = QLabel(f"Версия {APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(version_label)
        
        layout.addSpacing(20)
        
        # Поле логина
        login_layout = QHBoxLayout()
        login_label = QLabel("Логин:")
        login_label.setFixedWidth(100)
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Введите логин")
        self.login_input.returnPressed.connect(self.on_login)
        login_layout.addWidget(login_label)
        login_layout.addWidget(self.login_input)
        layout.addLayout(login_layout)
        
        # Поле пароля
        password_layout = QHBoxLayout()
        password_label = QLabel("Пароль:")
        password_label.setFixedWidth(100)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Введите пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.on_login)
        
        self.show_password_btn = QPushButton("👁")
        self.show_password_btn.setFixedWidth(30)
        self.show_password_btn.setCheckable(True)
        self.show_password_btn.toggled.connect(self.toggle_password_visibility)
        
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        password_layout.addWidget(self.show_password_btn)
        layout.addLayout(password_layout)
        
        # Запомнить меня
        self.remember_checkbox = QCheckBox("Запомнить меня")
        layout.addWidget(self.remember_checkbox)
        
        layout.addSpacing(10)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("Войти")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self.on_login)
        self.login_btn.setStyleSheet("")
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("")
        
        buttons_layout.addWidget(self.login_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        
        # Подсказка
        hint_label = QLabel("Обратитесь к администратору для получения учётных данных")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setStyleSheet("color: #95a5a6; font-size: 10px;")
        layout.addWidget(hint_label)
        
        self.setLayout(layout)
        
        # Фокус на поле логина
        self.login_input.setFocus()
    
    def toggle_password_visibility(self, checked):
        """Переключение видимости пароля"""
        if checked:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
    
    def on_login(self):
        """Обработка входа"""
        username = self.login_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля")
            return
        
        # Проверка количества попыток
        if self.login_attempts >= self.max_attempts:
            QMessageBox.critical(
                self, 
                "Блокировка", 
                f"Превышено количество попыток входа ({self.max_attempts})\n"
                "Приложение будет закрыто."
            )
            self.reject()
            return
        
        # Аутентификация
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
                    f"Неверный логин или пароль\n"
                    f"Осталось попыток: {remaining}"
                )
            else:
                QMessageBox.critical(
                    self,
                    "Блокировка",
                    "Превышено количество попыток входа\n"
                    "Приложение будет закрыто."
                )
                self.reject()
            
            # Очищаем пароль
            self.password_input.clear()
            self.password_input.setFocus()
    
    def get_user(self):
        """Получить авторизованного пользователя"""
        return self.user

    def _find_logo_path(self) -> Optional[str]:
        # Try several common locations for the logo to be robust across environments
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        candidates = [
            os.path.join(os.getcwd(), 'assets', 'logo.png'),
            os.path.join(os.getcwd(), 'logo.png'),
            os.path.join(base_dir, 'assets', 'logo.png'),
            os.path.join(base_dir, 'assets', 'logo.jpg'),
            os.path.join(base_dir, 'logo.png'),
            os.path.join(base_dir, 'assets', 'logo.svg'),
            os.path.join(base_dir, 'logo.svg'),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None
