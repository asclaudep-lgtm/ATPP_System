"""
Унифицированный запуск приложения ATPP.

Логика:
- пытается загрузить UI-модели из разных путей (ATPP_System.ui, ui)
- инициализирует БД, показывает диалог авторизации и главное окно
- при отсутствии UI-модулей выводит fallback UI
"""
import sys
from typing import Optional

from PyQt6.QtWidgets import QApplication, QMessageBox

from utils.logger import setup_logging, get_logger

log = get_logger(__name__)

try:
    from ATPP_System.ui import MainWindow, AuthDialog
except Exception:
    try:
        from ui import MainWindow, AuthDialog
    except Exception:
        MainWindow = None
        AuthDialog = None

from database import DatabaseManager
from config import APP_NAME


def _fallback_ui(app: QApplication) -> int:
    log.warning("Fallback UI start (no UI modules loaded)")
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
    fb = QWidget()
    fb.setWindowTitle("ATPP System (fallback)")
    lay = QVBoxLayout(fb)
    lay.addWidget(QLabel("ATPP System (fallback UI)"))
    exit_btn = QPushButton("Выход")
    exit_btn.clicked.connect(app.quit)
    lay.addWidget(exit_btn)
    fb.show()
    return app.exec_()


def launch() -> int:
    setup_logging()
    log.info("App start (launcher)")
    # Create QApplication
    try:
        app = QApplication(sys.argv)
    except Exception as e:
        log.error("QApplication init failed: %s", e)
        return 1
    app.setApplicationName(APP_NAME)

    # Применяем тему / шрифт / язык из пользовательских настроек
    try:
        from modules import settings as user_settings
        from ui.theme import apply_theme
        apply_theme(
            app,
            theme=user_settings.get('theme', 'light'),
            font_size=int(user_settings.get('font_size', 9) or 9),
        )
    except Exception as e:
        log.warning("apply_theme failed: %s", e)

    # Локализация: загружаем .qm если есть и язык не русский
    try:
        from PyQt6.QtCore import QTranslator, QLocale
        from modules import settings as user_settings
        from pathlib import Path
        lang = user_settings.get('language', 'ru')
        if lang and lang != 'ru':
            qm_path = Path(__file__).resolve().parent / 'resources' / 'i18n' / f'atpp_{lang}.qm'
            if qm_path.exists():
                tr = QTranslator(app)
                if tr.load(str(qm_path)):
                    app.installTranslator(tr)
                    log.debug("Translator loaded: %s", qm_path.name)
    except Exception as e:
        log.warning("translator init failed: %s", e)

    # Initialize DB
    try:
        db_manager = DatabaseManager()
        db_manager.init_database()
        try:
            summary = db_manager.summarize_data()
            log.debug("DB seed summary: %s", summary)
        except Exception:
            pass
    except Exception as e:
        QMessageBox.critical(None, "Ошибка базы данных", f"Не удалось инициализировать базу данных:\n{str(e)}")
        return 1

    # Daily auto-backup (silent, non-blocking on errors)
    try:
        from modules import backup as _backup
        _bp = _backup.daily_backup_if_needed()
        if _bp is not None:
            log.info("Daily backup snapshot: %s", _bp)
    except Exception as e:
        log.warning("auto-backup failed: %s", e)

    # UI availability
    if MainWindow is None or AuthDialog is None:
        return _fallback_ui(app)

    # Authentication dialog
    auth_dialog = AuthDialog(db_manager)
    ret = auth_dialog.exec()
    try:
        accepted = AuthDialog.DialogCode.Accepted
    except Exception:
        accepted = 1
    if ret != accepted:
        return 0

    user = auth_dialog.get_user()
    if not user:
        return 0

    if not isinstance(user, dict):
        try:
            user = {
                'id': getattr(user, 'id', None),
                'username': getattr(user, 'username', None),
                'full_name': getattr(user, 'full_name', None),
                'email': getattr(user, 'email', None),
                'role': getattr(user, 'role', 'user'),
                'is_active': getattr(user, 'is_active', True),
            }
        except Exception:
            user = None
    if not user:
        return 0

    # D15: если пользователю выставлен флаг must_change_password —
    # принудительно открываем диалог смены пароля до запуска главного окна.
    try:
        if user.get('must_change_password'):
            from ui.dialogs.change_password_dialog import ChangePasswordDialog
            cd = ChangePasswordDialog(db_manager, user, forced=True)
            ret = cd.exec()
            if ret != accepted:
                # Пользователь отказался — не пускаем в систему.
                QMessageBox.warning(
                    None, 'Смена пароля',
                    'Пароль не был изменён. Вход в систему отменён.')
                db_manager.close()
                return 0
    except Exception as e:
        log.warning('forced password change skipped: %s', e)

    try:
        # MainWindow expects a dict-like user (uses .get('role'), .get('id'), ...)
        main_window = MainWindow(db_manager, user)
        main_window.show()
        log.info("MainWindow shown with user: %s",
                 user.get('username') if isinstance(user, dict) else user)
    except Exception as e:
        QMessageBox.critical(None, "Ошибка запуска", f"Не удалось открыть главное окно: {e}")
        db_manager.close()
        return 1

    result = app.exec()
    # C13: фиксируем выход из системы (если БД ещё доступна).
    try:
        if user and user.get('id'):
            db_manager.end_user_session(user.get('id'))
    except Exception as e:
        log.warning('end_user_session at shutdown skipped: %s', e)
    db_manager.close()
    return result


__all__ = ["launch"]
