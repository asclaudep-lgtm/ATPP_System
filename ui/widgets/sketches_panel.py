"""
Виджет «Эскизы» для прикрепления изображений и PDF к операции / переходу.

Используется внутри OperationDialog и TransitionDialog.
"""
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QSize, QFileInfo
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QInputDialog, QFileIconProvider, QMenu,
)

from config import SKETCHES_DIR
from database.models import Sketch, Operation, Transition


_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.webp', '.gif'}
_PDF_EXTS = {'.pdf'}


def _detect_file_type(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in _IMAGE_EXTS:
        return 'image'
    if ext in _PDF_EXTS:
        return 'pdf'
    return None


def _open_path(path: str):
    """Открыть файл в системной программе. Кросс-платформенно."""
    import sys, os, subprocess
    try:
        if sys.platform.startswith('win'):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])
    except Exception:
        pass


class SketchesPanel(QWidget):
    """
    Менеджер эскизов для одной сущности — операции или перехода.

    parent_kind: 'operation' | 'transition'
    parent_id:   id операции или перехода. Если None — операция/переход
                 ещё не сохранены, и панель показывает заглушку.
    """

    def __init__(self, db_manager, parent_kind: str, parent_id: int | None,
                 product_designation: str = '', parent=None):
        super().__init__(parent)
        assert parent_kind in ('operation', 'transition')
        self.db_manager = db_manager
        self.parent_kind = parent_kind
        self.parent_id = parent_id
        self.product_designation = product_designation or ''
        # v7.7-fix: список путей, выбранных до того, как операция/переход
        # сохранены в БД. После сохранения вызвать flush_pending_to(new_id).
        self._pending_paths: list[str] = []
        self._init_ui()
        self.refresh()

    # ---------------------------------------------------------------- UI
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        # Список
        self._list = QListWidget()
        self._list.setIconSize(QSize(64, 64))
        self._list.setSpacing(2)
        self._list.itemDoubleClicked.connect(self._open_selected)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._context_menu)
        # Drag-and-drop файлов из ОС
        self._list.setAcceptDrops(True)
        self._list.dragEnterEvent = self._list_drag_enter
        self._list.dragMoveEvent = self._list_drag_move
        self._list.dropEvent = self._list_drop
        layout.addWidget(self._list, stretch=1)

        self._hint = QLabel(
            '<i>Можно перетащить файлы из проводника прямо сюда '
            'или нажать «Добавить файл…».</i>'
        )
        self._hint.setStyleSheet('color:#888; font-size:11px;')
        layout.addWidget(self._hint)

        # Кнопки
        btns = QHBoxLayout()
        self._add_btn = QPushButton("➕  Добавить файл…")
        self._add_btn.clicked.connect(self._add_files)
        btns.addWidget(self._add_btn)

        self._open_btn = QPushButton("👁  Просмотреть")
        self._open_btn.clicked.connect(self._open_selected)
        btns.addWidget(self._open_btn)

        self._title_btn = QPushButton("✏  Подпись…")
        self._title_btn.clicked.connect(self._edit_title)
        btns.addWidget(self._title_btn)

        self._up_btn = QPushButton("↑")
        self._up_btn.setToolTip("Переместить выше")
        self._up_btn.setFixedWidth(36)
        self._up_btn.clicked.connect(lambda: self._move_selected(-1))
        btns.addWidget(self._up_btn)

        self._down_btn = QPushButton("↓")
        self._down_btn.setToolTip("Переместить ниже")
        self._down_btn.setFixedWidth(36)
        self._down_btn.clicked.connect(lambda: self._move_selected(1))
        btns.addWidget(self._down_btn)

        self._del_btn = QPushButton("🗑  Удалить")
        self._del_btn.clicked.connect(self._delete_selected)
        btns.addWidget(self._del_btn)

        btns.addStretch()
        layout.addLayout(btns)

    # ---------------------------------------------------------------- drag-and-drop
    def _list_drag_enter(self, e):
        # v7.7-fix: разрешаем приём даже до сохранения родительской сущности.
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def _list_drag_move(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def _list_drop(self, e):
        if not e.mimeData().hasUrls():
            e.ignore()
            return
        paths = []
        for url in e.mimeData().urls():
            local = url.toLocalFile()
            if local:
                paths.append(local)
        if paths:
            self._accept_paths(paths)
        e.acceptProposedAction()

    # ---------------------------------------------------------------- reorder
    def _move_selected(self, delta: int):
        sk_id = self._selected_sketch_id()
        if sk_id is None or not self._has_parent():
            return
        with self.db_manager.get_session() as s:
            items = self._query_filter(s.query(Sketch)).order_by(
                Sketch.sort_order, Sketch.id
            ).all()
            ids = [it.id for it in items]
            if sk_id not in ids:
                return
            i = ids.index(sk_id)
            j = i + delta
            if j < 0 or j >= len(ids):
                return
            ids[i], ids[j] = ids[j], ids[i]
            for order, _id in enumerate(ids):
                obj = next(it for it in items if it.id == _id)
                obj.sort_order = order
        self.refresh()
        # Восстанавливаем выделение
        for r in range(self._list.count()):
            it = self._list.item(r)
            if it.data(Qt.ItemDataRole.UserRole) == sk_id:
                self._list.setCurrentRow(r)
                break

    # ---------------------------------------------------------------- helpers
    def _has_parent(self) -> bool:
        return self.parent_id is not None

    def _storage_dir(self) -> Path:
        """data/sketches/<деталь>/<op|tr>_<id>/"""
        from config import _sanitize_designation
        designation = _sanitize_designation(self.product_designation or '_')
        sub = f'{self.parent_kind}_{self.parent_id}'
        d = SKETCHES_DIR / designation / sub
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _query_filter(self, q):
        if self.parent_kind == 'operation':
            return q.filter_by(operation_id=self.parent_id)
        return q.filter_by(transition_id=self.parent_id)

    # ---------------------------------------------------------------- public
    def refresh(self):
        self._list.clear()

        # v7.7-fix: кнопка «Добавить файл…» доступна всегда. Если родителя
        # ещё нет — файлы накапливаются в pending-списке и сохранятся в БД
        # сразу после accept() диалога операции / перехода.
        self._add_btn.setEnabled(True)
        for w in (self._open_btn, self._title_btn, self._del_btn):
            w.setEnabled(True)

        provider = QFileIconProvider()

        # Сначала pending-файлы (если есть)
        for idx, p in enumerate(self._pending_paths):
            src_path = Path(p)
            title = src_path.stem[:200] or src_path.name
            kind = (_detect_file_type(src_path) or 'file').upper()
            size_kb = max(1, src_path.stat().st_size // 1024) if src_path.exists() else 0
            item = QListWidgetItem(
                f"⏳ {title}    [{kind}, {size_kb} КБ, ждёт сохранения]"
            )
            item.setForeground(Qt.GlobalColor.darkGray)
            if _detect_file_type(src_path) == 'image' and src_path.exists():
                pix = QPixmap(str(src_path))
                if not pix.isNull():
                    item.setIcon(QIcon(pix.scaled(
                        64, 64,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )))
            if item.icon().isNull():
                item.setIcon(provider.icon(QFileInfo(str(src_path))))
            # маркер: ('pending', idx)
            item.setData(Qt.ItemDataRole.UserRole, ('pending', idx))
            item.setToolTip(str(src_path))
            self._list.addItem(item)

        if not self._has_parent():
            n_pend = len(self._pending_paths)
            if n_pend:
                self._info_label.setText(
                    f"⏳ Файлов ожидает сохранения: <b>{n_pend}</b>. "
                    "Они будут прикреплены к операции/переходу после нажатия «Сохранить»."
                )
            else:
                self._info_label.setText(
                    "Прикрепите эскизы. Они сохранятся в БД после нажатия «Сохранить»."
                )
            return

        with self.db_manager.get_session() as s:
            sketches = self._query_filter(s.query(Sketch)).order_by(
                Sketch.sort_order, Sketch.id
            ).all()
            n_pend = len(self._pending_paths)
            pend_txt = (f", ожидает сохранения: <b>{n_pend}</b>" if n_pend else '')
            self._info_label.setText(
                f"Прикреплено эскизов: <b>{len(sketches)}</b>{pend_txt}. "
                "Двойной клик — открыть в системной программе."
            )
            for sk in sketches:
                full = Path(sk.stored_path)
                if not full.is_absolute():
                    full = SKETCHES_DIR.parent / full  # хранилище относит. data/
                title = sk.title or sk.original_filename or full.name
                kind = (sk.file_type or '').upper() or 'FILE'
                created = sk.created_at.strftime('%d.%m.%Y %H:%M') if sk.created_at else ''
                size_kb = max(1, full.stat().st_size // 1024) if full.exists() else 0
                item = QListWidgetItem(
                    f"{title}    [{kind}, {size_kb} КБ, {created}]"
                )
                # Превью для картинок
                if sk.file_type == 'image' and full.exists():
                    pix = QPixmap(str(full))
                    if not pix.isNull():
                        item.setIcon(QIcon(pix.scaled(
                            64, 64,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )))
                if item.icon().isNull():
                    item.setIcon(provider.icon(QFileInfo(str(full))))
                # маркер: ('db', sk.id)
                item.setData(Qt.ItemDataRole.UserRole, ('db', sk.id))
                item.setToolTip(str(full))
                self._list.addItem(item)

    # ---------------------------------------------------------------- actions
    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выбрать эскизы",
            "",
            "Изображения и PDF (*.png *.jpg *.jpeg *.bmp *.tif *.tiff "
            "*.webp *.gif *.pdf);;Все файлы (*.*)"
        )
        if files:
            self._accept_paths(files)

    # v7.7-fix: общая точка приёма путей — из drag-drop и из «Добавить файл…».
    def _accept_paths(self, paths: list[str]):
        # Если родитель ещё не сохранён — копим pending и не пишем в БД.
        if not self._has_parent():
            valid = []
            skipped = []
            for p in paths:
                sp = Path(p)
                if not sp.exists() or sp.is_dir():
                    skipped.append(sp.name)
                    continue
                if _detect_file_type(sp) is None:
                    skipped.append(sp.name)
                    continue
                valid.append(str(sp))
            self._pending_paths.extend(valid)
            if skipped:
                QMessageBox.information(
                    self, "Часть файлов пропущена",
                    "Эти файлы не подходят (нужны .png/.jpg/.jpeg/.bmp/.tif"
                    "/.tiff/.webp/.gif/.pdf) или отсутствуют:\n\n"
                    + "\n".join(skipped)
                )
            self.refresh()
            return
        # Родитель уже есть — сразу копируем и пишем в БД.
        self._import_paths(paths)

    def _import_paths(self, paths: list[str]):
        """Скопировать файлы во внутреннее хранилище и завести Sketch‑записи."""
        added, skipped = 0, []
        with self.db_manager.get_session() as s:
            existing_count = self._query_filter(s.query(Sketch)).count()
            for src in paths:
                src_path = Path(src)
                if not src_path.exists() or src_path.is_dir():
                    skipped.append(src_path.name)
                    continue
                ftype = _detect_file_type(src_path)
                if not ftype:
                    skipped.append(src_path.name)
                    continue
                stored_dir = self._storage_dir()
                stored_name = f'{uuid.uuid4().hex}{src_path.suffix.lower()}'
                stored_full = stored_dir / stored_name
                try:
                    shutil.copy2(src_path, stored_full)
                except OSError as e:
                    QMessageBox.warning(
                        self, "Ошибка копирования",
                        f"Не удалось скопировать {src_path.name}:\n{e}"
                    )
                    continue
                from config import DATA_DIR
                try:
                    rel = stored_full.relative_to(DATA_DIR)
                except ValueError:
                    rel = stored_full
                sk = Sketch(
                    operation_id=(self.parent_id if self.parent_kind == 'operation' else None),
                    transition_id=(self.parent_id if self.parent_kind == 'transition' else None),
                    title=src_path.stem[:200],
                    original_filename=src_path.name[:255],
                    stored_path=str(rel).replace('\\', '/'),
                    file_type=ftype,
                    sort_order=existing_count + added,
                    created_at=datetime.now(),
                )
                s.add(sk)
                added += 1

        if skipped:
            QMessageBox.information(
                self, "Часть файлов пропущена",
                "Эти файлы не подходят (нужны .png/.jpg/.jpeg/.bmp/.tif/.tiff"
                "/.webp/.gif/.pdf) или отсутствуют:\n\n" + "\n".join(skipped)
            )
        self.refresh()

    def _selected_marker(self):
        """v7.7-fix: возвращает ('db', sk_id) | ('pending', idx) | None."""
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _selected_sketch_id(self):
        marker = self._selected_marker()
        if isinstance(marker, tuple) and marker[0] == 'db':
            return marker[1]
        return None

    def _open_selected(self, *args):
        marker = self._selected_marker()
        # v7.7-fix: открываем pending-файл прямо из исходного пути.
        if isinstance(marker, tuple) and marker[0] == 'pending':
            idx = marker[1]
            if 0 <= idx < len(self._pending_paths):
                _open_path(self._pending_paths[idx])
            return
        sk_id = self._selected_sketch_id()
        if sk_id is None:
            return
        with self.db_manager.get_session() as s:
            sk = s.get(Sketch, sk_id)
            if sk is None:
                return
            full = Path(sk.stored_path)
            if not full.is_absolute():
                from config import DATA_DIR
                full = DATA_DIR / full
        if not full.exists():
            QMessageBox.warning(self, "Файл не найден", f"Файл отсутствует:\n{full}")
            return
        _open_path(str(full))

    def _edit_title(self):
        sk_id = self._selected_sketch_id()
        if sk_id is None:
            return
        with self.db_manager.get_session() as s:
            sk = s.get(Sketch, sk_id)
            if sk is None:
                return
            old_title = sk.title or ''
        new_title, ok = QInputDialog.getText(
            self, "Подпись эскиза",
            "Подпись (отображается в карте эскизов):",
            text=old_title,
        )
        if not ok:
            return
        with self.db_manager.get_session() as s:
            sk = s.get(Sketch, sk_id)
            if sk is not None:
                sk.title = (new_title or '').strip()[:200] or None
        self.refresh()

    def _delete_selected(self):
        marker = self._selected_marker()
        # v7.7-fix: для pending-эскиза просто убираем из списка.
        if isinstance(marker, tuple) and marker[0] == 'pending':
            idx = marker[1]
            if 0 <= idx < len(self._pending_paths):
                del self._pending_paths[idx]
            self.refresh()
            return
        sk_id = self._selected_sketch_id()
        if sk_id is None:
            return
        reply = QMessageBox.question(
            self, "Удалить эскиз",
            "Удалить выбранный эскиз? Файл также будет удалён.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        with self.db_manager.get_session() as s:
            sk = s.get(Sketch, sk_id)
            if sk is None:
                return
            full = Path(sk.stored_path)
            if not full.is_absolute():
                from config import DATA_DIR
                full = DATA_DIR / full
            try:
                if full.exists():
                    full.unlink()
            except OSError:
                pass
            s.delete(sk)
        self.refresh()

    def _context_menu(self, pos):
        item = self._list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self._list)
        act_open = menu.addAction("Открыть")
        act_title = menu.addAction("Изменить подпись…")
        menu.addSeparator()
        act_del = menu.addAction("Удалить эскиз")
        chosen = menu.exec(self._list.mapToGlobal(pos))
        if chosen == act_open:
            self._open_selected()
        elif chosen == act_title:
            self._edit_title()
        elif chosen == act_del:
            self._delete_selected()

    # ---------------------------------------------------------------- public API (v7.7-fix)
    def has_pending(self) -> bool:
        """True, если есть ещё не сохранённые в БД эскизы."""
        return bool(self._pending_paths)

    def flush_pending_to(self, new_parent_id: int):
        """После того, как операция/переход создан в БД, перенести pending-файлы.

        Вызывается из ui/widgets/tp_editor.py сразу после Session.add(op) + flush.
        """
        if not self._pending_paths:
            self.parent_id = new_parent_id
            return
        paths = list(self._pending_paths)
        self._pending_paths.clear()
        self.parent_id = new_parent_id
        self._import_paths(paths)
