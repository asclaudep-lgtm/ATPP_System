"""Status bar widget — DB indicator, user role, version."""

from PyQt6.QtWidgets import QStatusBar, QLabel
from PyQt6.QtCore import pyqtSignal

from config import APP_VERSION


class MainStatusBar(QStatusBar):
    notification_count_changed = pyqtSignal(int)

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self._user = user

        self._status_label = QLabel("Готово")
        self.addWidget(self._status_label)

        # DB indicator
        self._db_label = QLabel()
        self._build_db_label()
        self.addPermanentWidget(self._db_label)
        self.addPermanentWidget(QLabel(" | "))

        # User/role
        role_labels = {
            'admin': 'Администратор',
            'technologist': 'Технолог',
            'engineer': 'Инженер',
            'master': 'Мастер участка',
            'worker': 'Рабочий',
            'qc': 'Контролёр ОТК',
            'user': 'Пользователь',
        }
        role = role_labels.get(user.get('role', 'user'), user.get('role', ''))
        user_lbl = QLabel(
            f"  {user.get('full_name') or user.get('username')}  [{role}]  "
        )
        user_lbl.setStyleSheet("color: #2c3e50; font-weight: bold;")
        self.addPermanentWidget(user_lbl)

        version_lbl = QLabel(f"  v{APP_VERSION}  ")
        version_lbl.setStyleSheet("color: #95a5a6;")
        self.addPermanentWidget(version_lbl)

    def _build_db_label(self):
        try:
            from config import DATABASE_URL as db_url
            if db_url.lower().startswith('sqlite'):
                db_text = 'БД: SQLite (локальная)'
                db_color = '#7f8c8d'
            elif db_url.lower().startswith(('postgresql', 'postgres')):
                from urllib.parse import urlparse
                u = db_url
                if u.startswith('postgresql+'):
                    u = 'postgresql://' + u.split('://', 1)[1]
                p = urlparse(u)
                host = p.hostname or '?'
                db = (p.path or '/').lstrip('/') or '?'
                db_text = f'БД: postgres @ {host}/{db}'
                db_color = '#16a085'
            else:
                db_text = 'БД: ?'
                db_color = '#c0392b'
        except Exception:
            db_text = 'БД: ?'
            db_color = '#c0392b'
        self._db_label.setText(f"  {db_text}  ")
        self._db_label.setStyleSheet(f"color: {db_color}; font-weight: bold;")

    def set_message(self, msg: str):
        self._status_label.setText(msg)
