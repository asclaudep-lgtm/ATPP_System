"""
Тестовый запуск приложения АТПП БЕЗ АВТОРИЗАЦИИ
"""
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from config import APP_NAME
from database import DatabaseManager
from ui import MainWindow


def main():
    """Точка входа в приложение"""
    # Создаём приложение
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # Инициализируем базу данных
    try:
        db_manager = DatabaseManager()
        db_manager.init_database()
    except Exception as e:
        QMessageBox.critical(
            None,
            "Ошибка базы данных",
            f"Не удалось инициализировать базу данных:\n{str(e)}"
        )
        return 1

    # ТЕСТОВЫЙ РЕЖИМ: создаём фиктивного пользователя без авторизации
    test_user = {
        'id': 1,
        'username': 'admin',
        'full_name': 'Администратор (ТЕСТ)',
        'email': None,
        'role': 'admin',
        'is_active': True,
        'created_at': None,
        'last_login': None
    }

    # Создаём и показываем главное окно
    main_window = MainWindow(db_manager, test_user)
    main_window.show()

    # Запускаем цикл обработки событий
    result = app.exec()

    # Закрываем соединение с БД
    db_manager.close()

    return result


if __name__ == "__main__":
    sys.exit(main())
