"""Диалог смены пароля (D15 / D16).

Используется в двух сценариях:
1) добровольная смена через меню «Сервис → Сменить пароль…»;
2) принудительная — открывается автоматически после логина, если у
   пользователя выставлен флаг ``must_change_password = True``
   (см. main.py: проверка после ``authenticate_user``).
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from modules import password_policy


class ChangePasswordDialog(QDialog):
    def __init__(self, db_manager, current_user, *,
                 forced: bool = False, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user or {}
        self.forced = forced

        self.setWindowTitle('Смена пароля' + (' (требуется)' if forced else ''))
        self.setMinimumWidth(420)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        if self.forced:
            warn = QLabel(
                '<b>Требуется сменить пароль.</b><br>Это первый вход в '
                'систему или администратор сбросил Ваш пароль. Установите '
                'новый пароль, чтобы продолжить.')
            warn.setWordWrap(True)
            warn.setStyleSheet('background:#fff3cd; padding:8px; '
                               'border:1px solid #ffeeba; color:#856404;')
            root.addWidget(warn)

        form = QFormLayout()
        self.old_edit = QLineEdit()
        self.old_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('Текущий пароль:', self.old_edit)

        self.new_edit = QLineEdit()
        self.new_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('Новый пароль:', self.new_edit)

        self.repeat_edit = QLineEdit()
        self.repeat_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('Повторите:', self.repeat_edit)

        root.addLayout(form)

        policy = QLabel('<i>Политика:</i><br>' +
                        password_policy.describe_policy().replace('\n', '<br>'))
        policy.setStyleSheet('color:#555;')
        policy.setWordWrap(True)
        root.addWidget(policy)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText('Сменить пароль')
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _on_ok(self):
        old = self.old_edit.text()
        new = self.new_edit.text()
        rep = self.repeat_edit.text()
        username = self.current_user.get('username') or ''
        uid = self.current_user.get('id')

        if not uid:
            QMessageBox.warning(self, 'Смена пароля',
                                'Не удалось определить пользователя.')
            return
        if not old:
            QMessageBox.warning(self, 'Смена пароля',
                                'Введите текущий пароль.')
            return
        if new != rep:
            QMessageBox.warning(self, 'Смена пароля',
                                'Новый пароль и его повтор не совпадают.')
            return
        ok, problems = password_policy.validate(new, username=username)
        if not ok:
            QMessageBox.warning(self, 'Смена пароля',
                                'Пароль не соответствует политике:\n• ' +
                                '\n• '.join(problems))
            return
        # Проверяем старый пароль через authenticate_user.
        check = self.db_manager.authenticate_user(username, old)
        if not check:
            QMessageBox.warning(self, 'Смена пароля',
                                'Текущий пароль введён неверно.')
            return
        try:
            self.db_manager.change_user_password(uid, new)
        except Exception as e:
            QMessageBox.critical(self, 'Смена пароля',
                                 f'Не удалось сохранить:\n{e}')
            return
        # Снимаем флаг в локальном словаре
        self.current_user['must_change_password'] = False
        QMessageBox.information(self, 'Смена пароля',
                                'Пароль успешно изменён.')
        self.accept()
