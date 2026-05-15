"""
GroupTreeWidget — дерево «Группа» для нового UI v7.7.

Отличия от старого `products_tree`:
- НЕТ узлов ТП внутри детали (ТП открываются на вкладке КТП).
- НЕТ агрегатов / КЗ / переходов в дереве — только обозначение + наименование.
- Двойной клик по детали испускает сигнал `product_double_clicked(product_id)`.
- Виртуальные группы по статусу сверху (улучшение #f):
    🆕 Без ТП
    🟡 На согласовании
    🔁 На доработке
- Виртуальная группа «📋 Шаблоны» (улучшение #e).
- Поддержка drag-and-drop (детали между группами).

Содержит метод `set_search(text)` для фильтрации по обозначению/наименованию.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QAction, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QInputDialog,
    QAbstractItemView,
)

from database.models import (
    Product, ProductGroup, TechProcess, TPStatus,
)


# Маркеры типа узла в UserRole
ROLE_KIND = Qt.ItemDataRole.UserRole          # 'group' | 'product' | 'virtual'
ROLE_ID = Qt.ItemDataRole.UserRole + 1        # int / str


class GroupTreeWidget(QTreeWidget):
    """Дерево «Группа» (продукты по группам, без ТП-узлов)."""

    product_double_clicked = pyqtSignal(int)        # product_id
    product_edit_requested = pyqtSignal(int)        # product_id
    product_delete_requested = pyqtSignal(int)      # product_id
    new_product_requested = pyqtSignal(int)         # group_id (or 0)
    group_changed = pyqtSignal()                    # дерево изменилось
    template_double_clicked = pyqtSignal(int)       # tp_id (для шаблонов)

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._search_text = ''

        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(False)
        self.setAlternatingRowColors(False)

        # Drag-and-drop (улучшение #e/частично)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)

        self.itemDoubleClicked.connect(self._on_dbl)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    # ───────── PUBLIC ────────────────────────────────────────
    def reload(self):
        """Полная перезагрузка дерева."""
        self.clear()
        s = self.db_manager.Session()
        try:
            # Виртуальные секции по статусу/без ТП — добавляем сверху, если они не пусты
            self._add_virtual_status_groups(s)

            # Виртуальная группа «Шаблоны»
            self._add_templates_group(s)

            # Обычная иерархия групп → детали
            self._add_real_groups(s)

            # Детали без группы
            self._add_orphan_products(s)
        finally:
            s.close()

        if self._search_text:
            self.set_search(self._search_text)

    def set_search(self, text: str):
        """Фильтрация по тексту (обозначение/наименование детали)."""
        self._search_text = (text or '').lower().strip()
        self._filter_recursive(None)

    # ───────── BUILD ─────────────────────────────────────────
    def _add_virtual_status_groups(self, s):
        # Подсчёт изделий по виртуальным критериям
        # 1. Без ТП (только живые изделия)
        all_prod_ids = {
            p.id for p in s.query(Product).filter(
                (Product.is_deleted == False)
                | (Product.is_deleted.is_(None))
            ).all()
        }
        prod_with_tp = {tp.product_id for tp in
                        s.query(TechProcess).filter(
                            TechProcess.is_deleted == False).all()}
        no_tp = sorted(all_prod_ids - prod_with_tp)

        # 2. Детали с ТП на согласовании
        review_pids = {tp.product_id for tp in
                       s.query(TechProcess).filter(
                           TechProcess.status == TPStatus.REVIEW,
                           TechProcess.is_deleted == False).all()}

        # 3. Детали с ТП на доработке
        rework_pids = {tp.product_id for tp in
                       s.query(TechProcess).filter(
                           TechProcess.status == TPStatus.REWORK,
                           TechProcess.is_deleted == False).all()}

        if not (no_tp or review_pids or rework_pids):
            return

        if no_tp:
            self._make_virtual_group(
                f"🆕 Без ТП  ({len(no_tp)})", no_tp,
                color='#16a085', expanded=False)
        if review_pids:
            self._make_virtual_group(
                f"🟡 На согласовании  ({len(review_pids)})",
                sorted(review_pids), color='#f1c40f', expanded=False)
        if rework_pids:
            self._make_virtual_group(
                f"🔁 На доработке  ({len(rework_pids)})",
                sorted(rework_pids), color='#e67e22', expanded=False)

    def _make_virtual_group(self, title: str, product_ids: list[int],
                            color: str, expanded: bool = False):
        s = self.db_manager.Session()
        try:
            top = QTreeWidgetItem([title])
            f = top.font(0)
            f.setBold(True)
            top.setFont(0, f)
            top.setForeground(0, QColor(color))
            top.setData(0, ROLE_KIND, 'virtual')
            top.setData(0, ROLE_ID, '')
            self.addTopLevelItem(top)

            prods = (s.query(Product)
                     .filter(Product.id.in_(product_ids))
                     .order_by(Product.designation).all())
            for p in prods:
                self._add_product_item(top, p)
            top.setExpanded(expanded)
        finally:
            s.close()

    def _add_templates_group(self, s):
        """Добавляет виртуальную секцию «📋 Шаблоны» (TP с is_template=True)."""
        try:
            templates = (s.query(TechProcess)
                         .filter(TechProcess.is_template == True,
                                 TechProcess.is_deleted == False)
                         .order_by(TechProcess.number).all())
        except Exception:
            return
        if not templates:
            return

        top = QTreeWidgetItem([f"📋 Шаблоны  ({len(templates)})"])
        f = top.font(0)
        f.setBold(True)
        top.setFont(0, f)
        top.setForeground(0, QColor('#3498db'))
        top.setData(0, ROLE_KIND, 'virtual')
        top.setData(0, ROLE_ID, 'templates')
        self.addTopLevelItem(top)

        for tp in templates:
            it = QTreeWidgetItem([
                f"{tp.number}  —  "
                f"{tp.execution_variant or 'Шаблон'}"])
            it.setData(0, ROLE_KIND, 'template')
            it.setData(0, ROLE_ID, tp.id)
            it.setForeground(0, QColor('#3498db'))
            top.addChild(it)
        top.setExpanded(False)

    def _add_real_groups(self, s):
        roots = (s.query(ProductGroup)
                 .filter(ProductGroup.parent_id.is_(None))
                 .order_by(ProductGroup.sort_order, ProductGroup.name).all())
        for g in roots:
            self._add_group(s, g, parent_item=None)

    def _add_group(self, s, group: ProductGroup, parent_item):
        cnt = self._count_products(s, group)
        # v7.7: пользователь просил «без агрегатов, только числовые и буквенные
        # значения» — убираем устаревший префикс «Агрегаты» из легаси-имён групп.
        raw_name = group.display_name or group.name or ''
        clean_name = raw_name
        for prefix in ('Агрегаты ', 'агрегаты ', 'АГРЕГАТЫ '):
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix):]
                break
        title = f"📁 {clean_name}  ({cnt})"
        item = QTreeWidgetItem([title])
        item.setData(0, ROLE_KIND, 'group')
        item.setData(0, ROLE_ID, group.id)
        # Принимает дропы детали
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDropEnabled)
        f = item.font(0)
        f.setBold(True)
        item.setFont(0, f)
        item.setForeground(0, QColor('#2c3e50'))

        if parent_item is None:
            self.addTopLevelItem(item)
        else:
            parent_item.addChild(item)

        # Подгруппы
        for child in sorted(group.children,
                            key=lambda g: (g.sort_order, g.name)):
            self._add_group(s, child, item)

        # Детали в этой группе (только живые)
        prods = (s.query(Product)
                 .filter(Product.group_id == group.id,
                         (Product.is_deleted == False)
                         | (Product.is_deleted.is_(None)))
                 .order_by(Product.designation).all())
        for p in prods:
            self._add_product_item(item, p)

        # Авто-разворот для небольших групп
        if cnt <= 50:
            item.setExpanded(True)

    def _add_orphan_products(self, s):
        orphans = (s.query(Product)
                   .filter(Product.group_id.is_(None),
                           (Product.is_deleted == False)
                           | (Product.is_deleted.is_(None)))
                   .order_by(Product.designation).all())
        if not orphans:
            return
        title = f"📁 Без группы  ({len(orphans)})"
        top = QTreeWidgetItem([title])
        f = top.font(0)
        f.setBold(True)
        top.setFont(0, f)
        top.setData(0, ROLE_KIND, 'group')
        top.setData(0, ROLE_ID, None)  # special "no group"
        top.setFlags(top.flags() | Qt.ItemFlag.ItemIsDropEnabled)
        self.addTopLevelItem(top)
        for p in orphans:
            self._add_product_item(top, p)

    def _add_product_item(self, parent: QTreeWidgetItem, p: Product):
        text = f"{p.designation}  —  {p.name}"
        it = QTreeWidgetItem([text])
        it.setData(0, ROLE_KIND, 'product')
        it.setData(0, ROLE_ID, p.id)
        it.setFlags((it.flags() | Qt.ItemFlag.ItemIsDragEnabled)
                    & ~Qt.ItemFlag.ItemIsDropEnabled)
        # Подсчитаем количество ТП — отображаем (k вар.)
        # v8: считаем минимальную готовность среди живых ТП и показываем
        # её индикатором у узла детали.
        try:
            from modules.completeness import (
                score_tp, score_label, score_tooltip,
            )
        except Exception:
            score_tp = None
        live_tps = []
        try:
            live_tps = [tp for tp in p.tech_processes
                        if not getattr(tp, 'is_deleted', False)]
        except Exception:
            live_tps = []
        n_tp = len(live_tps)

        worst_label = ''
        worst_tooltip = ''
        if n_tp and score_tp is not None:
            try:
                worst = min(
                    (score_tp(tp) for tp in live_tps),
                    key=lambda r: r[0],
                )
                worst_label = score_label(worst[0])
                worst_tooltip = score_tooltip(*worst)
            except Exception:
                worst_label = ''
                worst_tooltip = ''

        suffix = ''
        if worst_label:
            suffix += f'   {worst_label}'
        if n_tp:
            suffix += f'    ({n_tp} вар.)'
        it.setText(0, f"{p.designation}  —  {p.name}{suffix}")

        tooltip_lines = [
            f"Обозначение: {p.designation}",
            f"Наименование: {p.name}",
            f"Материал: {p.material.name if p.material else '—'}",
            f"Масса: {p.mass or '—'} кг",
        ]
        if worst_tooltip:
            tooltip_lines.append('')
            tooltip_lines.append(worst_tooltip)
        it.setToolTip(0, '\n'.join(tooltip_lines))
        parent.addChild(it)

    def _count_products(self, s, g: ProductGroup) -> int:
        c = (s.query(Product)
             .filter(Product.group_id == g.id,
                     (Product.is_deleted == False)
                     | (Product.is_deleted.is_(None)))
             .count())
        for ch in g.children:
            c += self._count_products(s, ch)
        return c

    # ───────── INTERACTION ───────────────────────────────────
    def _on_dbl(self, item: QTreeWidgetItem, col: int):
        kind = item.data(0, ROLE_KIND)
        ident = item.data(0, ROLE_ID)
        if kind == 'product' and isinstance(ident, int):
            self.product_double_clicked.emit(ident)
        elif kind == 'template' and isinstance(ident, int):
            self.template_double_clicked.emit(ident)
        else:
            item.setExpanded(not item.isExpanded())

    def _on_context_menu(self, pos):
        item = self.itemAt(pos)
        m = QMenu(self)

        # Всегда: «новая группа»
        a_new_group = QAction("➕  Новая группа верхнего уровня", self)
        a_new_group.triggered.connect(lambda: self._create_group(parent_id=None))
        m.addAction(a_new_group)

        if item is not None:
            kind = item.data(0, ROLE_KIND)
            ident = item.data(0, ROLE_ID)

            if kind == 'group' and isinstance(ident, int):
                m.addSeparator()
                a_subgroup = QAction("➕  Создать подгруппу…", self)
                a_subgroup.triggered.connect(
                    lambda: self._create_group(parent_id=ident))
                m.addAction(a_subgroup)

                a_rename = QAction("✏  Переименовать группу…", self)
                a_rename.triggered.connect(
                    lambda: self._rename_group(ident))
                m.addAction(a_rename)

                a_del = QAction("🗑  Удалить пустую группу", self)
                a_del.triggered.connect(
                    lambda: self._delete_empty_group(ident))
                m.addAction(a_del)

                m.addSeparator()
                a_new_prod = QAction("➕  Новая деталь в этой группе…", self)
                a_new_prod.triggered.connect(
                    lambda: self.new_product_requested.emit(ident))
                m.addAction(a_new_prod)

            elif kind == 'product' and isinstance(ident, int):
                m.addSeparator()
                a_open = QAction("📂  Открыть КТП", self)
                a_open.triggered.connect(
                    lambda: self.product_double_clicked.emit(ident))
                m.addAction(a_open)
                a_edit = QAction("✏  Редактировать деталь…", self)
                a_edit.triggered.connect(
                    lambda: self.product_edit_requested.emit(ident))
                m.addAction(a_edit)
                m.addSeparator()
                a_del = QAction("🗑  Удалить деталь", self)
                a_del.triggered.connect(
                    lambda: self.product_delete_requested.emit(ident))
                m.addAction(a_del)

        m.exec(self.viewport().mapToGlobal(pos))

    def _create_group(self, parent_id: int | None):
        name, ok = QInputDialog.getText(
            self, "Новая группа",
            "Имя группы (например, «11-74.80»):")
        if not ok or not name.strip():
            return
        try:
            with self.db_manager.get_session() as s:
                g = ProductGroup(name=name.strip(), parent_id=parent_id)
                s.add(g)
            self.reload()
            self.group_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Операция не выполнена.\n\n{e}")

    def _rename_group(self, group_id: int):
        s = self.db_manager.Session()
        try:
            g = s.get(ProductGroup, group_id)
            if not g:
                return
            cur = g.display_name or g.name or ''
        finally:
            s.close()
        new_name, ok = QInputDialog.getText(
            self, "Переименовать группу", "Новое имя:", text=cur)
        if not ok or not new_name.strip():
            return
        try:
            with self.db_manager.get_session() as s:
                g = s.get(ProductGroup, group_id)
                g.display_name = new_name.strip()
            self.reload()
            self.group_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Операция не выполнена.\n\n{e}")

    def _delete_empty_group(self, group_id: int):
        try:
            with self.db_manager.get_session() as s:
                g = s.get(ProductGroup, group_id)
                if not g:
                    return
                # Только если пустая
                if g.children or g.products:
                    QMessageBox.information(
                        self, "Удаление группы",
                        "Группа не пуста — сначала перенесите детали "
                        "в другую группу или удалите подгруппы.")
                    return
                s.delete(g)
            self.reload()
            self.group_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Операция не выполнена.\n\n{e}")

    # ───────── DRAG-AND-DROP ────────────────────────────────
    def dropEvent(self, e: QDropEvent):
        # Сохраняем выделение перед стандартной обработкой
        src = self.currentItem()
        if src is None:
            return super().dropEvent(e)
        kind = src.data(0, ROLE_KIND)
        if kind != 'product':
            return super().dropEvent(e)
        product_id = src.data(0, ROLE_ID)

        target = self.itemAt(e.position().toPoint())
        if target is None:
            return e.ignore()
        tk = target.data(0, ROLE_KIND)
        if tk != 'group':
            return e.ignore()
        new_group_id = target.data(0, ROLE_ID)

        try:
            with self.db_manager.get_session() as s:
                p = s.get(Product, product_id)
                if not p:
                    return
                p.group_id = new_group_id  # None если "Без группы"
        except Exception as ex:
            QMessageBox.critical(self, "Ошибка перемещения", f"{ex}")
            return e.ignore()
        e.accept()
        self.reload()
        self.group_changed.emit()

    # ───────── FILTER ───────────────────────────────────────
    def _filter_recursive(self, item):
        """Скрыть/показать узлы по тексту поиска."""
        if item is None:
            for i in range(self.topLevelItemCount()):
                self._filter_recursive(self.topLevelItem(i))
            return True

        text = self._search_text
        if not text:
            item.setHidden(False)
            for i in range(item.childCount()):
                self._filter_recursive(item.child(i))
            return True

        # Сравнение текста
        kind = item.data(0, ROLE_KIND)
        haystack = item.text(0).lower()
        tip = item.toolTip(0)
        if tip:
            haystack += '\n' + tip.lower()

        any_child = False
        for i in range(item.childCount()):
            if self._filter_recursive(item.child(i)):
                any_child = True

        # Группы видны только если хоть один ребёнок виден
        if kind in ('group', 'virtual'):
            visible = any_child
        else:
            visible = (text in haystack) or any_child

        item.setHidden(not visible)
        if visible and any_child:
            item.setExpanded(True)
        return visible
