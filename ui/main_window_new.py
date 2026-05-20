"""
Главное окно приложения
"""
from PyQt6.QtWidgets import QMainWindow

from config import APP_NAME, WINDOW_HEIGHT, WINDOW_WIDTH


class MainWindow(QMainWindow):
    """Главное окно приложения"""

    def __init__(self, db_manager, user):
        super().__init__()
        self.db_manager = db_manager
        self.user = user

        # Получаем имя пользователя из словаря
        user_display_name = user.get('full_name') or user.get('username')
        self.setWindowTitle(f"{APP_NAME} - {user_display_name}")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.init_ui()
        self.create_menu()
        self.create_toolbar()
        self.create_statusbar()
