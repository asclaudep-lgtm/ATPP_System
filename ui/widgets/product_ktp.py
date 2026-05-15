"""
ProductKTPWidget — карточка КТП (Конкретные ТП) для одной детали.

Открывается двойным кликом по детали в дереве «Группа». Содержит:
- шапку с обозначением + наименованием + материалом/массой;
- список вариантов исполнения ТП (статус-бейджи, "по умолчанию");
- встроенный редактор маршрутки выбранного варианта (TPEditorWidget);
- кнопки «Новый вариант», «Копировать», «Переименовать», «Удалить»,
  «Сравнить два», «По умолчанию».

v7.7 (a–i, 8 улучшений):
  ▸ b: цветные бейджи статуса
  ▸ c: окно сравнения двух вариантов (модальное)
  ▸ d: чекбокс «По умолчанию для производства» (один на деталь)
  ▸ i: плейсхолдер «у этой детали ещё нет ТП — создайте первый вариант»
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QStackedWidget, QMessageBox,
    QInputDialog, QMenu, QSizePolicy, QToolButton,
)

from database.models import (
    Product, TechProcess, TPStatus, Operation, Equipment,
)


# Цвет + эмодзи + подпись для статусов ТП
STATUS_BADGE = {
    TPStatus.DRAFT:    ('#7f8c8d', '⚪', 'Черновик'),
    TPStatus.REVIEW:   ('#f1c40f', '🟡', 'На согласовании'),
    TPStatus.REWORK:   ('#e67e22', '🔁', 'На доработке'),
    TPStatus.APPROVED: ('#27ae60', '🟢', 'Утверждён'),
    TPStatus.ARCHIVED: ('#34495e', '⚫', 'Архив'),
}


# ──────────────────────────────────────────────────────────────────────────────
# Виджет элемента списка вариантов (одна строка)
# ──────────────────────────────────────────────────────────────────────────────
class _VariantRow(QWidget):
    """Кастомная строка списка: бейдж · номер · вариант · [по умолчанию]."""

    def __init__(self, tp_data: dict, parent=None):
        super().__init__(parent)
        self._tp = tp_data
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(8)

        status = self._tp.get('status') or TPStatus.DRAFT
        color, emoji, status_label = STATUS_BADGE.get(
            status, ('#777', '·', str(status)))

        # Цветной бейдж (узкий вертикальный прямоугольник + emoji)
        badge = QLabel(f"  {emoji}  ")
        badge.setFixedWidth(36)
        lay.addWidget(badge)

        # Имя варианта
        variant_name = self._tp.get('execution_variant') or 'Основной вариант'
        title = QLabel(f"<b>{variant_name}</b>")
        title.setStyleSheet("font-size: 13px;")
        lay.addWidget(title)

        # Номер ТП + версия
        sub = QLabel(
            f"<span style='color:#666'>"
            f"{self._tp.get('number','')} · v{self._tp.get('version','1.0')}"
            f"</span>"
        )
        sub.setStyleSheet("font-size: 11px;")
        lay.addWidget(sub)

        # Маркер "по умолчанию"
        if self._tp.get('is_default_for_product'):
            star = QLabel('⭐')
            star.setToolTip('По умолчанию для производства')
            star.setStyleSheet("font-size: 14px;")
            lay.addWidget(star)

        lay.addStretch()

        # v8: индикатор готовности ТП.
        completeness_score = self._tp.get('completeness_score')
        completeness_missing = self._tp.get('completeness_missing') or []
        if completeness_score is not None:
            from modules.completeness import score_label, score_tooltip
            cmp_lbl = QLabel(
                f"{score_label(int(completeness_score))}  "
                f"{int(completeness_score)}%"
            )
            cmp_lbl.setToolTip(
                score_tooltip(int(completeness_score),
                              list(completeness_missing))
            )
            lay.addWidget(cmp_lbl)

        # Подпись статуса (мелким текстом справа)
        st = QLabel(status_label)
        lay.addWidget(st)


# ──────────────────────────────────────────────────────────────────────────────
# Главный виджет КТП
# ──────────────────────────────────────────────────────────────────────────────
class ProductKTPWidget(QWidget):
    """Вкладка «КТП» для одной детали со списком вариантов ТП."""

    tp_changed = pyqtSignal(int)   # tp_id — для обновления дерева в main_window

    def __init__(self, db_manager, product_id: int, user: dict, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.product_id = product_id
        self.user = user

        self._product = self._load_product()
        self._variants: list[dict] = []
        self._editor_cache: dict[int, QWidget] = {}  # tp_id -> TPEditorWidget

        self._init_ui()
        self._reload_variants()

    # ───────── LOAD ──────────────────────────────────────────
    def _load_product(self) -> dict:
        s = self.db_manager.Session()
        try:
            p = s.get(Product, self.product_id)
            if not p:
                return {}
            mat = ''
            if p.material:
                mat = (p.material.name or '')
                if p.material.grade:
                    mat = f"{mat} {p.material.grade}".strip()
            return {
                'id': p.id,
                'designation': p.designation or '',
                'name': p.name or '',
                'material': mat,
                'mass': p.mass,
                'accuracy_class': p.accuracy_class or '',
                'roughness': p.roughness or '',
                'blank_type': p.blank_type or '',
            }
        finally:
            s.close()

    def _load_variants(self) -> list[dict]:
        from modules.completeness import score_tp
        s = self.db_manager.Session()
        try:
            tps = (s.query(TechProcess)
                   .filter(TechProcess.product_id == self.product_id,
                           ((TechProcess.is_deleted == False)
                            | (TechProcess.is_deleted.is_(None))))
                   .order_by(TechProcess.is_default_for_product.desc(),
                             TechProcess.number)
                   .all())
            rows = []
            for tp in tps:
                try:
                    score, missing = score_tp(tp)
                except Exception:
                    score, missing = None, []
                rows.append({
                    'id': tp.id,
                    'number': tp.number,
                    'version': tp.version or '1.0',
                    'execution_variant': tp.execution_variant,
                    'status': tp.status,
                    'is_default_for_product':
                        bool(getattr(tp, 'is_default_for_product', False)),
                    'completeness_score': score,
                    'completeness_missing': missing,
                })
            return rows
        finally:
            s.close()

    # ───────── UI ────────────────────────────────────────────
    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── ЛЕВО: список вариантов + кнопки ──
        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(6, 6, 6, 6)
        left_l.setSpacing(4)

        title_l = QLabel("<b>Варианты ТП</b>")
        title_l.setStyleSheet("font-size: 13px;")
        left_l.addWidget(title_l)

        self.variants_list = QListWidget()
        self.variants_list.setAlternatingRowColors(True)
        self.variants_list.setSelectionMode(
            self.variants_list.SelectionMode.ExtendedSelection)
        self.variants_list.itemSelectionChanged.connect(self._on_variant_selected)
        self.variants_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.variants_list.customContextMenuRequested.connect(
            self._show_variants_context_menu)
        left_l.addWidget(self.variants_list, 1)

        # Кнопки управления вариантами
        btn_row1 = QHBoxLayout()
        btn_new = QPushButton("➕ Новый ТП")
        btn_new.clicked.connect(self._on_new_variant)

        btn_copy = QPushButton("⎘ Копия")
        btn_copy.setToolTip("Создать копию выбранного варианта")
        btn_copy.clicked.connect(self._on_copy_variant)

        btn_rename = QPushButton("✏ Переименовать")
        btn_rename.clicked.connect(self._on_rename_variant)

        btn_row1.addWidget(btn_new)
        btn_row1.addWidget(btn_copy)
        btn_row1.addWidget(btn_rename)
        left_l.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        btn_default = QPushButton("⭐ По умолчанию")
        btn_default.setToolTip(
            "Сделать этот вариант ТП используемым по умолчанию для нарядов")
        btn_default.clicked.connect(self._on_set_default)

        btn_compare = QPushButton("🔀 Сравнить два")
        btn_compare.setToolTip(
            "Выберите 2 варианта в списке (Ctrl+клик) и нажмите для сравнения")
        btn_compare.clicked.connect(self._on_compare)

        btn_del = QPushButton("🗑 Удалить")
        btn_del.clicked.connect(self._on_delete_variant)

        btn_row2.addWidget(btn_default)
        btn_row2.addWidget(btn_compare)
        btn_row2.addWidget(btn_del)
        left_l.addLayout(btn_row2)

        # ── ПРАВО: stacked editor ──
        self.editor_stack = QStackedWidget()
        self._placeholder_index = self.editor_stack.addWidget(
            self._make_placeholder())

        splitter.addWidget(left)
        splitter.addWidget(self.editor_stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1000])

        root.addWidget(splitter, 1)
        self._splitter = splitter

    def _make_header(self) -> QFrame:
        frame = QFrame()
        lay = QHBoxLayout(frame)
        lay.setSpacing(20)

        left = QVBoxLayout()
        left.setSpacing(2)
        prod = QLabel(
            f"<b>{self._product.get('designation','')}</b>  "
            f"{self._product.get('name','')}")
        prod.setStyleSheet("font-size:14px;")
        left.addWidget(prod)

        info_parts = []
        if self._product.get('material'):
            info_parts.append(f"Материал: {self._product['material']}")
        if self._product.get('mass') is not None:
            info_parts.append(f"Масса: {self._product['mass']:.3f} кг")
        if self._product.get('accuracy_class'):
            info_parts.append(f"Класс точности: {self._product['accuracy_class']}")
        if self._product.get('roughness'):
            info_parts.append(f"Шероховатость: {self._product['roughness']}")
        info = QLabel("  ·  ".join(info_parts) if info_parts
                      else '<span style="color:#999">Параметры детали не заданы</span>')
        left.addWidget(info)

        lay.addLayout(left)
        lay.addStretch()
        return frame

    def _make_placeholder(self) -> QWidget:
        """Большой плейсхолдер для случая, когда вариантов нет (улучшение #i)."""
        w = QWidget()
        l = QVBoxLayout(w)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("📝  У этой детали пока нет ни одного ТП")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(title)
        sub = QLabel(
            "Создайте первый вариант ТП — например, «Универсальное оборудование» "
            "или «Обработка ЧПУ». Несколько вариантов одной детали — это нормально."
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        l.addWidget(sub)
        l.addSpacing(10)
        btn = QPushButton("➕  Создать первый вариант ТП")
        btn.clicked.connect(self._on_new_variant)
        wrap = QHBoxLayout()
        wrap.addStretch()
        wrap.addWidget(btn)
        wrap.addStretch()
        l.addLayout(wrap)
        return w

    # ───────── HELPERS ───────────────────────────────────────
    def _reload_variants(self):
        """Перезагрузить список вариантов и обновить UI."""
        sel_id = self._current_tp_id()

        self._variants = self._load_variants()
        self.variants_list.clear()

        for v in self._variants:
            it = QListWidgetItem()
            it.setData(Qt.ItemDataRole.UserRole, v['id'])
            row = _VariantRow(v)
            it.setSizeHint(row.sizeHint())
            self.variants_list.addItem(it)
            self.variants_list.setItemWidget(it, row)

        if not self._variants:
            self.editor_stack.setCurrentIndex(self._placeholder_index)
            return

        # Восстановить выделение или взять первый
        target_id = sel_id if any(v['id'] == sel_id for v in self._variants) \
            else self._variants[0]['id']
        for i in range(self.variants_list.count()):
            it = self.variants_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == target_id:
                self.variants_list.setCurrentRow(i)
                break

    def _current_tp_id(self) -> int | None:
        it = self.variants_list.currentItem()
        if not it:
            return None
        return it.data(Qt.ItemDataRole.UserRole)

    def _selected_tp_ids(self) -> list[int]:
        return [it.data(Qt.ItemDataRole.UserRole)
                for it in self.variants_list.selectedItems()]

    def _on_variant_selected(self):
        tp_id = self._current_tp_id()
        if tp_id is None:
            self.editor_stack.setCurrentIndex(self._placeholder_index)
            return
        # Кешируем редакторы
        if tp_id not in self._editor_cache:
            from ui.widgets.tp_editor import TPEditorWidget
            ed = TPEditorWidget(self.db_manager, tp_id, self.user, self)
            ed.tp_changed.connect(self._on_inner_tp_changed)
            self._editor_cache[tp_id] = ed
            self.editor_stack.addWidget(ed)
        self.editor_stack.setCurrentWidget(self._editor_cache[tp_id])

    def _on_inner_tp_changed(self, tp_id: int):
        # Обновляем имя/статус в списке вариантов и пробрасываем наверх
        self._reload_variants()
        self.tp_changed.emit(tp_id)

    # ───────── ACTIONS ───────────────────────────────────────
    def _on_new_variant(self):
        from ui.dialogs.tp_dialog import TPDialog
        dlg = TPDialog(self.db_manager,
                       product_id=self.product_id, parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        data = dlg.get_data()
        try:
            with self.db_manager.get_session() as s:
                tp = TechProcess(
                    number=data['number'],
                    product_id=data['product_id'],
                    tp_type=data.get('tp_type'),
                    technology_type=data.get('technology_type'),
                    version=data.get('version', '1.0'),
                    execution_variant=data.get('execution_variant'),
                    description=data.get('description'),
                    status=TPStatus.DRAFT,
                    author_id=(self.user or {}).get('id'),
                )
                s.add(tp)
                s.flush()
                new_id = tp.id
            self._reload_variants()
            self.tp_changed.emit(new_id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось создать вариант ТП:\n{e}")

    def _on_copy_variant(self):
        tp_id = self._current_tp_id()
        if tp_id is None:
            QMessageBox.information(self, "Копия",
                                    "Выберите вариант для копирования.")
            return
        s = self.db_manager.Session()
        try:
            tp = s.get(TechProcess, tp_id)
            if not tp:
                return
            old_num = tp.number
            old_var = tp.execution_variant or ''
        finally:
            s.close()

        new_num, ok = QInputDialog.getText(
            self, "Копирование ТП",
            f"Номер для копии «{old_num}»:", text=f"{old_num}-копия")
        if not ok or not new_num.strip():
            return
        new_var, ok = QInputDialog.getText(
            self, "Вариант исполнения",
            "Название варианта (например, «Обработка ЧПУ»):",
            text=old_var or 'Копия')
        if not ok:
            return
        try:
            from modules.tp_designer import TPDesigner
            with self.db_manager.get_session() as s:
                designer = TPDesigner(s)
                new_tp = designer.copy_tech_process(
                    source_tp_id=tp_id,
                    new_number=new_num.strip(),
                    author_id=(self.user or {}).get('id'),
                    new_execution_variant=(new_var.strip() or None),
                )
                new_id = new_tp.id
            self._reload_variants()
            self.tp_changed.emit(new_id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось скопировать ТП:\n{e}")

    def _on_rename_variant(self):
        tp_id = self._current_tp_id()
        if tp_id is None:
            return
        s = self.db_manager.Session()
        try:
            tp = s.get(TechProcess, tp_id)
            if not tp:
                return
            cur = tp.execution_variant or ''
        finally:
            s.close()
        new_var, ok = QInputDialog.getText(
            self, "Переименовать вариант",
            "Название варианта исполнения\n"
            "(например, «Универсальное оборудование», «Обработка ЧПУ», "
            "«Опытный образец»):",
            text=cur)
        if not ok:
            return
        try:
            with self.db_manager.get_session() as s:
                tp = s.get(TechProcess, tp_id)
                tp.execution_variant = new_var.strip() or None
            self._reload_variants()
            self.tp_changed.emit(tp_id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось переименовать:\n{e}")

    def _on_set_default(self):
        tp_id = self._current_tp_id()
        if tp_id is None:
            return
        try:
            with self.db_manager.get_session() as s:
                # Снять флаг со всех вариантов этой детали
                others = (s.query(TechProcess)
                          .filter(TechProcess.product_id == self.product_id)
                          .all())
                for tp in others:
                    tp.is_default_for_product = (tp.id == tp_id)
            self._reload_variants()
            self.tp_changed.emit(tp_id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось отметить:\n{e}")

    def _on_delete_variant(self):
        tp_id = self._current_tp_id()
        if tp_id is None:
            return
        s = self.db_manager.Session()
        try:
            tp = s.get(TechProcess, tp_id)
            if not tp:
                return
            num = tp.number
        finally:
            s.close()
        reply = QMessageBox.question(
            self, "Удалить вариант",
            f"Перенести вариант «{num}» в корзину?\n"
            f"Восстановить можно через «Сервис → Корзина».",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from datetime import datetime
            with self.db_manager.get_session() as s:
                tp = s.get(TechProcess, tp_id)
                if tp:
                    tp.is_deleted = True
                    tp.deleted_at = datetime.now()
                    if (self.user or {}).get('id'):
                        tp.deleted_by = self.user['id']
            # Удалить редактор из кеша
            ed = self._editor_cache.pop(tp_id, None)
            if ed is not None:
                self.editor_stack.removeWidget(ed)
                ed.deleteLater()
            self._reload_variants()
            self.tp_changed.emit(tp_id)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось удалить:\n{e}")

    def _on_compare(self):
        ids = self._selected_tp_ids()
        if len(ids) < 2:
            QMessageBox.information(
                self, "Сравнение вариантов",
                "Выделите ровно два варианта (Ctrl+клик) "
                "и нажмите «Сравнить два».")
            return
        if len(ids) > 2:
            ids = ids[:2]
        try:
            from ui.widgets.tp_compare import TPCompareDialog
            dlg = TPCompareDialog(self.db_manager, ids[0], ids[1], self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"{e}")

    def _show_variants_context_menu(self, pos):
        item = self.variants_list.itemAt(pos)
        if not item:
            return
        m = QMenu(self)
        a_default = QAction("⭐ Сделать по умолчанию", self)
        a_default.triggered.connect(self._on_set_default)
        m.addAction(a_default)
        a_rename = QAction("✏ Переименовать вариант…", self)
        a_rename.triggered.connect(self._on_rename_variant)
        m.addAction(a_rename)
        a_copy = QAction("⎘ Создать копию…", self)
        a_copy.triggered.connect(self._on_copy_variant)
        m.addAction(a_copy)
        m.addSeparator()
        a_del = QAction("🗑 Удалить вариант…", self)
        a_del.triggered.connect(self._on_delete_variant)
        m.addAction(a_del)
        m.exec(self.variants_list.viewport().mapToGlobal(pos))

    # ───────── PUBLIC API ────────────────────────────────────
    def get_tab_title(self) -> str:
        d = self._product.get('designation', '?')
        n = self._product.get('name', '')
        return f"КТП · {d}  {n}".strip()

    def refresh(self):
        self._product = self._load_product()
        self._reload_variants()
