"""
Диалог управления подписями утверждения ТП.

Показывает: какие роли подписали ТП, кто, когда, с каким комментарием.
Текущий пользователь может добавить подпись своей роли (одной из).
"""
from typing import Dict

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database.models import SignerRole, TechProcess
from modules import workflow


class SignaturesDialog(QDialog):
    """Управление подписями: добавить / снять / автоутверждение."""

    def __init__(self, db_manager, tp_id: int,
                 current_user: Dict, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.tp_id = tp_id
        self.user = current_user or {}
        self.setWindowTitle(f'Подписи — ТП #{tp_id}')
        self.resize(720, 420)
        self._build_ui()
        self._reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._status_lbl = QLabel('—')
        self._status_lbl.setStyleSheet('font-weight: bold; padding: 4px;')
        layout.addWidget(self._status_lbl)

        # Таблица всех ролей и их состояния
        self.tbl = QTableWidget(len(SignerRole), 4, self)
        self.tbl.setHorizontalHeaderLabels(['Роль', 'Кто', 'Когда', 'Комментарий'])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.verticalHeader().setVisible(False)
        layout.addWidget(self.tbl, 1)

        # Добавление подписи
        add_row = QHBoxLayout()
        add_row.addWidget(QLabel('Подписать как:'))
        self.role_cb = QComboBox()
        for r in SignerRole:
            self.role_cb.addItem(r.value, r.value)
        add_row.addWidget(self.role_cb, 1)
        self.cmt_in = QLineEdit()
        self.cmt_in.setPlaceholderText('Комментарий (необязательно)')
        add_row.addWidget(self.cmt_in, 2)
        sign_btn = QPushButton('Подписать')
        sign_btn.clicked.connect(self._on_sign)
        add_row.addWidget(sign_btn)
        unsign_btn = QPushButton('Снять подпись')
        unsign_btn.clicked.connect(self._on_unsign)
        add_row.addWidget(unsign_btn)
        layout.addLayout(add_row)

        # Снятие с утверждения / закрытие
        bottom = QHBoxLayout()
        unlock_btn = QPushButton('🔓 Снять с утверждения…')
        unlock_btn.clicked.connect(self._on_unlock)
        bottom.addWidget(unlock_btn)
        bottom.addStretch()
        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _reload(self):
        with self.db.get_session() as s:
            tp = s.get(TechProcess, self.tp_id)
            sigs_by_role = {x.role: x for x in workflow.get_signatures(s, self.tp_id)}
            req = workflow.DEFAULT_REQUIRED_ROLES

            self._status_lbl.setText(
                f'Статус: {tp.status.value} | '
                f'Подписей: {len(sigs_by_role)} из {len(req)} обязательных'
            )

            for row, role in enumerate(SignerRole):
                self.tbl.setItem(row, 0, QTableWidgetItem(
                    role.value + (' *' if role.value in req else '')
                ))
                sig = sigs_by_role.get(role.value)
                if sig is not None:
                    who = ''
                    if sig.user is not None:
                        who = sig.user.full_name or sig.user.username
                    when = sig.signed_at.strftime('%d.%m.%Y %H:%M') if sig.signed_at else ''
                    self.tbl.setItem(row, 1, QTableWidgetItem(who))
                    self.tbl.setItem(row, 2, QTableWidgetItem(when))
                    self.tbl.setItem(row, 3, QTableWidgetItem(sig.comment or ''))
                else:
                    for col in (1, 2, 3):
                        self.tbl.setItem(row, col, QTableWidgetItem('—'))
        self.tbl.resizeColumnsToContents()

    def _selected_role(self) -> str:
        row = self.tbl.currentRow()
        if row < 0:
            row = self.role_cb.currentIndex()
        return list(SignerRole)[row].value

    def _on_sign(self):
        role = self.role_cb.currentData() or self.role_cb.currentText()
        comment = self.cmt_in.text().strip() or None
        with self.db.get_session() as s:
            workflow.add_signature(s, self.tp_id, role,
                                   user_id=self.user.get('id'),
                                   comment=comment)
            approved = workflow.try_auto_approve(s, self.tp_id,
                                                 user_id=self.user.get('id'))
        msg = f'Подпись «{role}» сохранена.'
        if approved:
            msg += '\n\nВсе обязательные подписи получены — ТП автоматически переведён в «Утверждён».'
        QMessageBox.information(self, 'Подпись', msg)
        self.cmt_in.clear()
        self._reload()

    def _on_unsign(self):
        role = self._selected_role()
        if QMessageBox.question(self, 'Снять подпись',
                                f'Снять подпись «{role}»?') != QMessageBox.StandardButton.Yes:
            return
        with self.db.get_session() as s:
            workflow.remove_signature(s, self.tp_id, role,
                                      user_id=self.user.get('id'))
        self._reload()

    def _on_unlock(self):
        from PyQt6.QtWidgets import QInputDialog
        reason, ok = QInputDialog.getText(
            self, 'Снять с утверждения',
            'Причина снятия с утверждения (обязательно):'
        )
        if not ok:
            return
        reason = (reason or '').strip()
        if not reason:
            QMessageBox.warning(self, 'Снять с утверждения',
                                'Причина обязательна.')
            return
        with self.db.get_session() as s:
            ok = workflow.unlock_for_edit(s, self.tp_id,
                                          user_id=self.user.get('id') or 0,
                                          reason=reason)
        if ok:
            QMessageBox.information(self, 'Снято с утверждения',
                                    'ТП возвращён в «Черновик» и снова доступен для редактирования.')
        else:
            QMessageBox.warning(self, 'Снять с утверждения',
                                'ТП не находится в утверждённом / архивном статусе.')
        self._reload()
