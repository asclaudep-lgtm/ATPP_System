"""
Диалог управления пользователями (только для admin)
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QCheckBox,
    QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QAbstractItemView, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from database.models import User


ROLES = {
    'admin': 'Администратор',
    'technologist': 'Технолог',
    'engineer': 'Инженер',
    'master': 'Мастер участка',
    'worker': 'Рабочий',
    'qc': 'Контролёр ОТК',
    'user': 'Пользователь',
}


class UsersDialog(QDialog):
    """Управление пользователями системы"""

    def __init__(self, db_manager, current_user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user

        self.setWindowTitle("Управление пользователями")
        self.setMinimumSize(800, 500)
        self.setModal(True)

        self._init_ui()
        self._load_users()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Управление пользователями")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        # Таблица пользователей
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(6)
        self.users_table.setHorizontalHeaderLabels(["ID", "Логин", "ФИО", "Email", "Роль", "Активен"])
        self.users_table.setColumnHidden(0, True)
        self.users_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.users_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.users_table.setAlternatingRowColors(True)
        self.users_table.selectionModel().selectionChanged.connect(self._on_user_selected)
        layout.addWidget(self.users_table)

        # Форма
        form_frame = QFrame()
        form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        fl = QFormLayout(form_frame)
        fl.setSpacing(8)
        fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.login_edit = QLineEdit()
        self.login_edit.setPlaceholderText("Логин (латиница, цифры, _)")
        fl.addRow("Логин *:", self.login_edit)

        self.fullname_edit = QLineEdit()
        self.fullname_edit.setPlaceholderText("Фамилия Имя Отчество")
        fl.addRow("ФИО:", self.fullname_edit)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("email@example.com")
        fl.addRow("Email:", self.email_edit)

        self.role_combo = QComboBox()
        for role_key, role_label in ROLES.items():
            self.role_combo.addItem(role_label, role_key)
        fl.addRow("Роль:", self.role_combo)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Пароль (оставьте пустым для сохранения текущего)")
        fl.addRow("Пароль:", self.password_edit)

        self.active_check = QCheckBox("Активен")
        self.active_check.setChecked(True)
        fl.addRow("Статус:", self.active_check)

        layout.addWidget(form_frame)

        # Кнопки
        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("Добавить")
        self.add_btn.clicked.connect(self._add_user)

        self.edit_btn = QPushButton("Сохранить изменения")
        self.edit_btn.clicked.connect(self._edit_user)

        self.reset_pw_btn = QPushButton("Сбросить пароль")
        self.reset_pw_btn.clicked.connect(self._reset_password)

        self.clear_btn = QPushButton("Очистить форму")
        self.clear_btn.clicked.connect(self._clear_form)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)

        for btn in [self.add_btn, self.edit_btn, self.reset_pw_btn, self.clear_btn]:
            btn.setFixedHeight(30)
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _load_users(self):
        session = self.db_manager.Session()
        try:
            users = session.query(User).order_by(User.username).all()
            self.users_table.setRowCount(0)
            for u in users:
                row = self.users_table.rowCount()
                self.users_table.insertRow(row)
                self.users_table.setItem(row, 0, QTableWidgetItem(str(u.id)))
                self.users_table.setItem(row, 1, QTableWidgetItem(u.username or ''))
                self.users_table.setItem(row, 2, QTableWidgetItem(u.full_name or ''))
                self.users_table.setItem(row, 3, QTableWidgetItem(u.email or ''))
                self.users_table.setItem(row, 4, QTableWidgetItem(ROLES.get(u.role, u.role or '')))
                self.users_table.setItem(row, 5, QTableWidgetItem("Да" if u.is_active else "Нет"))

                # Цвет неактивных
                if not u.is_active:
                    for col in range(self.users_table.columnCount()):
                        item = self.users_table.item(row, col)
                        if item:
                            item.setForeground(Qt.GlobalColor.gray)
        finally:
            session.close()

    def _on_user_selected(self):
        row = self.users_table.currentRow()
        if row < 0:
            return
        self.login_edit.setText(self.users_table.item(row, 1).text())
        self.fullname_edit.setText(self.users_table.item(row, 2).text())
        self.email_edit.setText(self.users_table.item(row, 3).text())

        role_label = self.users_table.item(row, 4).text()
        for role_key, rl in ROLES.items():
            if rl == role_label:
                idx = self.role_combo.findData(role_key)
                if idx >= 0:
                    self.role_combo.setCurrentIndex(idx)
                break

        active_text = self.users_table.item(row, 5).text()
        self.active_check.setChecked(active_text == "Да")
        self.password_edit.clear()

    def _get_selected_id(self):
        row = self.users_table.currentRow()
        if row < 0:
            return None
        return int(self.users_table.item(row, 0).text())

    def _add_user(self):
        login = self.login_edit.text().strip()
        password = self.password_edit.text()

        if not login:
            QMessageBox.warning(self, "Ошибка", "Введите логин")
            return
        if not password:
            QMessageBox.warning(self, "Ошибка", "Введите пароль для нового пользователя")
            return

        from modules import password_policy
        ok, problems = password_policy.validate(password, username=login)
        if not ok:
            QMessageBox.warning(
                self, "Ошибка",
                "Пароль не соответствует политике:\n• " + "\n• ".join(problems))
            return

        try:
            self.db_manager.create_user(
                username=login,
                password=password,
                full_name=self.fullname_edit.text().strip() or None,
                email=self.email_edit.text().strip() or None,
                role=self.role_combo.currentData(),
                must_change_password=True,
            )
            self._load_users()
            self._clear_form()
            QMessageBox.information(self, "Готово", f"Пользователь «{login}» создан")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось создать пользователя:\n{e}")

    def _edit_user(self):
        user_id = self._get_selected_id()
        if not user_id:
            QMessageBox.information(self, "Выбор", "Выберите пользователя для редактирования")
            return

        cur_login = self.current_user.get('username', '')
        with self.db_manager.get_session() as session:
            user = session.get(User, user_id)
            if not user:
                return
            user.full_name = self.fullname_edit.text().strip() or None
            user.email = self.email_edit.text().strip() or None
            user.role = self.role_combo.currentData()
            user.is_active = self.active_check.isChecked()

            pw = self.password_edit.text()
            if pw:
                from modules import password_policy
                ok, problems = password_policy.validate(
                    pw, username=user.username)
                if not ok:
                    QMessageBox.warning(
                        self, "Ошибка",
                        "Пароль не соответствует политике:\n• " +
                        "\n• ".join(problems))
                    return
                user.password_hash = self.db_manager._hash_password(pw)
                # При смене пароля админом — заставляем сменить при входе.
                user.must_change_password = True

        self._load_users()
        QMessageBox.information(self, "Готово", "Данные пользователя обновлены")

    def _reset_password(self):
        user_id = self._get_selected_id()
        if not user_id:
            QMessageBox.information(self, "Выбор", "Выберите пользователя")
            return
        pw = self.password_edit.text()
        if not pw:
            QMessageBox.warning(self, "Ошибка", "Введите новый пароль в поле «Пароль»")
            return

        with self.db_manager.get_session() as session:
            user = session.get(User, user_id)
            if not user:
                return
            from modules import password_policy
            ok, problems = password_policy.validate(pw, username=user.username)
            if not ok:
                QMessageBox.warning(
                    self, "Ошибка",
                    "Пароль не соответствует политике:\n• " +
                    "\n• ".join(problems))
                return
            user.password_hash = self.db_manager._hash_password(pw)
            user.must_change_password = True

        self._load_users()
        self.password_edit.clear()
        QMessageBox.information(
            self, "Готово",
            "Пароль сброшен. Пользователь обязан сменить его при входе.")

    def _clear_form(self):
        self.login_edit.clear()
        self.fullname_edit.clear()
        self.email_edit.clear()
        self.password_edit.clear()
        self.role_combo.setCurrentIndex(0)
        self.active_check.setChecked(True)
        self.users_table.clearSelection()
