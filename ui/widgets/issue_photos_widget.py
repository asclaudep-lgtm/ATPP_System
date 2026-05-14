"""Виджет «Фотографии проблемы» (A5).

Показывает миниатюры уже прикреплённых фотографий и позволяет добавить
новые / удалить выбранную. Используется в IssueDialog и ResolveIssueDialog.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListView, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from modules import issue_photos


class IssuePhotosWidget(QWidget):
    """Управление фотографиями одной проблемы.

    Если ``issue_id`` ещё не создан (issue только готовится к сохранению),
    можно работать в режиме «pending»: пользователь выбирает файлы,
    они хранятся в self.pending_paths, потом владелец диалога вызывает
    flush(issue_id) — это копирует все pending-файлы в БД.
    """

    def __init__(self, db_manager, current_user,
                 issue_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_user = current_user or {}
        self.issue_id = issue_id
        self.pending_paths: list[str] = []
        self._build()
        if issue_id:
            self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        header.addWidget(QLabel('<b>Фотографии</b>'))
        header.addStretch(1)
        self.btn_add = QPushButton('+ Добавить фото…')
        self.btn_add.clicked.connect(self._on_add)
        header.addWidget(self.btn_add)
        self.btn_remove = QPushButton('Удалить')
        self.btn_remove.clicked.connect(self._on_remove)
        header.addWidget(self.btn_remove)
        root.addLayout(header)

        self.list = QListWidget()
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setIconSize(QSize(120, 90))
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setSpacing(8)
        self.list.setMinimumHeight(140)
        self.list.itemDoubleClicked.connect(self._on_open)
        root.addWidget(self.list)

        self.hint = QLabel(
            'Поддерживаются PNG, JPG, BMP, GIF, WEBP. Двойной клик — '
            'открыть оригинал в системе.')
        self.hint.setStyleSheet('color: gray;')
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

    def _on_add(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Добавить фотографии', '',
            'Изображения (*.png *.jpg *.jpeg *.bmp *.gif *.webp)')
        if not files:
            return
        if self.issue_id:
            try:
                with self.db_manager.get_session() as s:
                    for f in files:
                        issue_photos.attach_photo(
                            s, issue_id=self.issue_id,
                            source_path=f,
                            uploaded_by=self.current_user.get('id'),
                        )
            except Exception as e:
                QMessageBox.warning(self, 'Фото', f'Не удалось сохранить:\n{e}')
            self.refresh()
        else:
            # pending-режим: запоминаем пути, прикрепим после сохранения issue.
            self.pending_paths.extend(files)
            self._render_items_from_paths(self.pending_paths)

    def _on_remove(self):
        item = self.list.currentItem()
        if item is None:
            QMessageBox.information(self, 'Удаление', 'Выберите фото.')
            return
        photo_id = item.data(Qt.ItemDataRole.UserRole)
        if photo_id is None:
            # pending — просто удаляем из списка
            path = item.data(Qt.ItemDataRole.UserRole + 1)
            if path in self.pending_paths:
                self.pending_paths.remove(path)
            self._render_items_from_paths(self.pending_paths)
            return
        ans = QMessageBox.question(
            self, 'Удалить фото?',
            'Удалить фотографию из проблемы?')
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            with self.db_manager.get_session() as s:
                issue_photos.remove_photo(s, photo_id)
        except Exception as e:
            QMessageBox.warning(self, 'Удаление',
                                f'Не удалось удалить:\n{e}')
        self.refresh()

    def _on_open(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole + 1)
        if not path:
            return
        # Открываем в системе
        try:
            import os as _os
            import subprocess
            import sys as _sys
            if _sys.platform.startswith('win'):
                _os.startfile(path)  # type: ignore[attr-defined]
            elif _sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            from utils.logger import get_logger
            get_logger(__name__).warning('Cannot open file: %s', e)

    def refresh(self):
        if self.issue_id is None:
            self._render_items_from_paths(self.pending_paths)
            return
        with self.db_manager.get_session() as s:
            photos = issue_photos.list_photos(s, self.issue_id)
            rows = [(p.id, p.file_path, p.caption or '') for p in photos]
        self.list.clear()
        for pid, path, caption in rows:
            self._add_item(path, photo_id=pid, caption=caption)

    def _render_items_from_paths(self, paths: list[str]):
        self.list.clear()
        for p in paths:
            self._add_item(p, photo_id=None)

    def _add_item(self, path: str, *, photo_id: Optional[int] = None,
                  caption: str = ''):
        name = Path(path).name
        item = QListWidgetItem(name if not caption else f'{name}\n{caption}')
        pix = QPixmap(path)
        if not pix.isNull():
            item.setIcon(QIcon(pix.scaled(
                120, 90, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)))
        item.setData(Qt.ItemDataRole.UserRole, photo_id)
        item.setData(Qt.ItemDataRole.UserRole + 1, path)
        item.setToolTip(path)
        self.list.addItem(item)

    def flush_pending(self, issue_id: int) -> int:
        """После создания issue — копируем все pending-файлы в БД."""
        if not self.pending_paths:
            return 0
        attached = 0
        try:
            with self.db_manager.get_session() as s:
                for f in self.pending_paths:
                    try:
                        issue_photos.attach_photo(
                            s, issue_id=issue_id,
                            source_path=f,
                            uploaded_by=self.current_user.get('id'),
                        )
                        attached += 1
                    except Exception as e:  # noqa: BLE001
                        print(f'[photos] skip {f}: {e}')
        finally:
            self.pending_paths.clear()
        return attached
