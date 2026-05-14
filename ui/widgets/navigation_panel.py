"""Navigation panel — product group tree, TP tree, search, context menus."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QPushButton, QLineEdit, QMenu, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QColor

from database.models import (
    Product, ProductGroup, TechProcess, TPStatus,
)

STATUS_BADGE = {
    TPStatus.DRAFT:    ('#f39c12', 'Черновик'),
    TPStatus.REVIEW:   ('#8e44ad', 'Согласование'),
    TPStatus.REWORK:   ('#e74c3c', 'Доработка'),
    TPStatus.APPROVED: ('#27ae60', 'Утверждён'),
    TPStatus.ARCHIVED: ('#95a5a6', 'Архив'),
}


class NavigationPanel(QWidget):
    product_double_clicked = pyqtSignal(int)
    tp_double_clicked = pyqtSignal(int)
    product_edit_requested = pyqtSignal(int)
    product_delete_requested = pyqtSignal(int)
    new_product_requested = pyqtSignal()
    new_tp_requested = pyqtSignal(object)  # product_id or None

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setMinimumWidth(240)
        self.setMaximumWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Search
        search_layout = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Поиск...")
        self._search_edit.textChanged.connect(self._on_search)
        search_layout.addWidget(self._search_edit)
        layout.addLayout(search_layout)

        # Navigation tabs
        nav_tabs = QTabWidget()
        nav_tabs.setTabPosition(QTabWidget.TabPosition.South)

        # Products tab
        products_panel = self._build_products_tab()
        nav_tabs.addTab(products_panel, "Группа")

        # TP tab
        tp_panel = self._build_tp_tab()
        nav_tabs.addTab(tp_panel, "ТП")

        layout.addWidget(nav_tabs)
        self._nav_tabs = nav_tabs

    # ── Products tab ──────────────────────────────────────────────

    def _build_products_tab(self):
        panel = QWidget()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(2)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Изделие")
        add_btn.setFixedHeight(24)
        add_btn.clicked.connect(self.new_product_requested)
        add_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; "
            "border: none; padding: 2px 8px; border-radius: 3px; }")
        edit_btn = QPushButton("Ред.")
        edit_btn.setFixedHeight(24)
        edit_btn.clicked.connect(self._on_edit_product_btn)
        edit_btn.setStyleSheet(
            "QPushButton { background-color: #2980b9; color: white; "
            "border: none; padding: 2px 6px; border-radius: 3px; }")
        del_btn = QPushButton("Удал.")
        del_btn.setFixedHeight(24)
        del_btn.clicked.connect(self._on_delete_product_btn)
        del_btn.setStyleSheet(
            "QPushButton { color: #e74c3c; border: none; padding: 2px 6px; }")
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        pl.addLayout(btn_row)

        from ui.widgets.group_tree import GroupTreeWidget
        self.group_tree = GroupTreeWidget(self.db_manager)
        self.group_tree.product_double_clicked.connect(
            self.product_double_clicked)
        self.group_tree.product_edit_requested.connect(
            self.product_edit_requested)
        self.group_tree.product_delete_requested.connect(
            self.product_delete_requested)
        self.group_tree.new_product_requested.connect(
            lambda gid: self.new_product_requested.emit())
        self.group_tree.template_double_clicked.connect(
            self.tp_double_clicked)
        self.products_tree = self.group_tree
        pl.addWidget(self.group_tree)

        return panel

    def _on_edit_product_btn(self):
        item = self.products_tree.currentItem()
        if item:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, int):
                self.product_edit_requested.emit(data)

    def _on_delete_product_btn(self):
        item = self.products_tree.currentItem()
        if item:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, int):
                self.product_delete_requested.emit(data)

    # ── TP tab ────────────────────────────────────────────────────

    def _build_tp_tab(self):
        panel = QWidget()
        tpl = QVBoxLayout(panel)
        tpl.setContentsMargins(0, 0, 0, 0)
        tpl.setSpacing(2)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ ТП")
        add_btn.setFixedHeight(24)
        add_btn.clicked.connect(lambda: self.new_tp_requested.emit(None))
        add_btn.setStyleSheet(
            "QPushButton { background-color: #8e44ad; color: white; "
            "border: none; padding: 2px 8px; border-radius: 3px; }")
        refresh_btn = QPushButton("↺")
        refresh_btn.setFixedHeight(24)
        refresh_btn.setToolTip("Обновить")
        refresh_btn.clicked.connect(self.load_data)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        btn_row.addWidget(refresh_btn)
        tpl.addLayout(btn_row)

        self.tp_tree = QTreeWidget()
        self.tp_tree.setHeaderHidden(True)
        self.tp_tree.itemDoubleClicked.connect(self._on_tp_dbl_click)
        self.tp_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tp_tree.customContextMenuRequested.connect(self._tp_context_menu)
        tpl.addWidget(self.tp_tree)

        return panel

    def _on_tp_dbl_click(self, item, col):
        tp_id = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(tp_id, int):
            self.tp_double_clicked.emit(tp_id)

    # ── Data loading ──────────────────────────────────────────────

    def load_data(self):
        self._load_products_tree()
        self._load_tp_tree()

    def reload(self):
        self.load_data()

    def _load_products_tree(self):
        if hasattr(self, 'group_tree'):
            self.group_tree.reload()
            return

        # Legacy fallback (deprecated)
        self.products_tree.clear()
        session = self.db_manager.Session()
        try:
            root_groups = (session.query(ProductGroup)
                           .filter(ProductGroup.parent_id.is_(None))
                           .order_by(ProductGroup.sort_order, ProductGroup.name)
                           .all())

            group_items = {}

            def make_group_item(group):
                if group.id in group_items:
                    return group_items[group.id]
                display = group.display_name or group.name
                count = _count_products_in_group(session, group)
                g_item = QTreeWidgetItem()
                g_item.setText(0, f"📁 {display}  ({count})")
                g_item.setData(0, Qt.ItemDataRole.UserRole, ('group', group.id))
                font = g_item.font(0)
                font.setBold(True)
                g_item.setFont(0, font)
                g_item.setForeground(0, QColor('#2c3e50'))
                group_items[group.id] = g_item
                return g_item

            def _count_products_in_group(sess, group):
                cnt = sess.query(Product).filter_by(group_id=group.id).count()
                for child in group.children:
                    cnt += _count_products_in_group(sess, child)
                return cnt

            auto_subgroups = {}

            def _get_or_make_subgroup(parent_item, prefix):
                key = (id(parent_item), prefix)
                cached = auto_subgroups.get(key)
                if cached is not None:
                    return cached
                sg = QTreeWidgetItem()
                sg.setText(0, f"📂 {prefix}")
                sg.setData(0, Qt.ItemDataRole.UserRole, ('auto_group', prefix))
                f = sg.font(0)
                f.setBold(True)
                sg.setFont(0, f)
                sg.setForeground(0, QColor('#34495e'))
                parent_item.addChild(sg)
                auto_subgroups[key] = sg
                return sg

            def _split_designation(designation):
                import re
                parts = [s for s in re.split(r'[.\s]+', (designation or '').strip()) if s]
                return parts

            def _add_product_item(p, group_item, group_prefix=''):
                designation = (p.designation or '').strip()
                trimmed = designation
                if group_prefix and designation.startswith(group_prefix):
                    rest = designation[len(group_prefix):]
                    if rest.startswith('.') or rest.startswith(' ') or not rest:
                        trimmed = rest.lstrip('. ')
                parts = _split_designation(trimmed)
                container = group_item
                for i in range(len(parts) - 1):
                    prefix = '.'.join(parts[: i + 1])
                    container = _get_or_make_subgroup(container, prefix)

                item = QTreeWidgetItem()
                item.setText(0, f"{designation}  —  {p.name}")
                item.setData(0, Qt.ItemDataRole.UserRole, p.id)
                item.setToolTip(0,
                    f"Обозначение: {p.designation}\n"
                    f"Наименование: {p.name}\n"
                    f"Материал: {p.material.name if p.material else '—'}\n"
                    f"Масса: {p.mass or '—'} кг"
                )
                container.addChild(item)
                tps = (session.query(TechProcess)
                       .filter(TechProcess.product_id == p.id,
                               (TechProcess.is_deleted == False) | (TechProcess.is_deleted.is_(None)))
                       .all())
                for tp in tps:
                    color, status_label = STATUS_BADGE.get(
                        tp.status, ('#555', str(tp.status)))
                    variant = getattr(tp, 'execution_variant', None)
                    variant_part = f"  /  Исп.: {variant}" if variant else ""
                    tp_item = QTreeWidgetItem()
                    tp_item.setText(0, f"  ТП: {tp.number}{variant_part}  [{status_label}]")
                    tp_item.setData(0, Qt.ItemDataRole.UserRole, ('tp', tp.id))
                    tp_item.setForeground(0, QColor(color))
                    tp_item.setToolTip(0,
                        f"ТП: {tp.number}\n"
                        f"Версия: {tp.version or '1.0'}\n"
                        f"Вариант исполнения: {variant or '—'}\n"
                        f"Статус: {status_label}"
                    )
                    item.addChild(tp_item)

            def add_group_to_tree(group, parent_item=None):
                g_item = make_group_item(group)
                if parent_item is None:
                    self.products_tree.addTopLevelItem(g_item)
                else:
                    parent_item.addChild(g_item)
                for child_group in sorted(group.children,
                                          key=lambda g: (g.sort_order, g.name)):
                    add_group_to_tree(child_group, g_item)
                products = (session.query(Product)
                            .filter_by(group_id=group.id)
                            .order_by(Product.designation)
                            .all())
                group_prefix = (group.name or '').strip()
                for p in products:
                    _add_product_item(p, g_item, group_prefix=group_prefix)
                if _count_products_in_group(session, group) <= 50:
                    g_item.setExpanded(True)

            for root_group in root_groups:
                add_group_to_tree(root_group)

            ungrouped = (session.query(Product)
                         .filter(Product.group_id.is_(None))
                         .order_by(Product.designation)
                         .all())
            if ungrouped:
                other_item = QTreeWidgetItem()
                other_item.setText(0, f"📁 Без группы  ({len(ungrouped)})")
                other_item.setData(0, Qt.ItemDataRole.UserRole, ('group', None))
                font = other_item.font(0)
                font.setBold(True)
                other_item.setFont(0, font)
                self.products_tree.addTopLevelItem(other_item)
                for p in ungrouped:
                    _add_product_item(p, other_item)

        finally:
            session.close()

    def _load_tp_tree(self):
        self.tp_tree.clear()
        session = self.db_manager.Session()
        try:
            status_groups = {
                TPStatus.DRAFT:    QTreeWidgetItem(['Черновики']),
                TPStatus.REVIEW:   QTreeWidgetItem(['На согласовании']),
                TPStatus.REWORK:   QTreeWidgetItem(['На доработке']),
                TPStatus.APPROVED: QTreeWidgetItem(['Утверждённые']),
                TPStatus.ARCHIVED: QTreeWidgetItem(['Архив']),
            }

            tps = (session.query(TechProcess)
                   .join(Product)
                   .filter((TechProcess.is_deleted == False) | (TechProcess.is_deleted.is_(None)))
                   .order_by(TechProcess.number)
                   .all())

            counts = {s: 0 for s in status_groups}

            for tp in tps:
                color, status_label = STATUS_BADGE.get(tp.status, ('#555', str(tp.status)))
                item = QTreeWidgetItem()
                prod_name = tp.product.name if tp.product else ''
                item.setText(0, f"{tp.number}  —  {prod_name}")
                item.setData(0, Qt.ItemDataRole.UserRole, tp.id)
                item.setToolTip(0, f"ТП: {tp.number}\nИзделие: {prod_name}\nСтатус: {status_label}")
                item.setForeground(0, QColor(color))

                if tp.status in status_groups:
                    status_groups[tp.status].addChild(item)
                    counts[tp.status] = counts.get(tp.status, 0) + 1

            for status, group_item in status_groups.items():
                count = counts.get(status, 0)
                if count > 0:
                    color, lbl = STATUS_BADGE.get(status, ('#555', ''))
                    group_item.setText(0, f"{lbl}  ({count})")
                    group_item.setForeground(0, QColor(color))
                    group_font = QFont()
                    group_font.setBold(True)
                    group_item.setFont(0, group_font)
                    self.tp_tree.addTopLevelItem(group_item)
                    group_item.setExpanded(True)

        finally:
            session.close()

    # ── Search ────────────────────────────────────────────────────

    def _on_search(self, text):
        if hasattr(self, 'group_tree') and self.group_tree is self.products_tree:
            self.group_tree.set_search(text)
            self._on_search_tp_tree(text)
            return
        self._on_search_legacy(text)

    def _on_search_tp_tree(self, text):
        text = (text or '').lower().strip()

        def _filt(item):
            haystack = item.text(0).lower()
            tip = item.toolTip(0)
            if tip:
                haystack += '\n' + tip.lower()
            any_child = False
            for j in range(item.childCount()):
                if _filt(item.child(j)):
                    any_child = True
            visible = (not text) or (text in haystack) or any_child
            item.setHidden(not visible)
            if visible and any_child:
                item.setExpanded(True)
            return visible

        if hasattr(self, 'tp_tree') and self.tp_tree:
            for i in range(self.tp_tree.topLevelItemCount()):
                _filt(self.tp_tree.topLevelItem(i))

    def _on_search_legacy(self, text):
        text = (text or '').lower().strip()

        def _filter_item(item):
            data = item.data(0, Qt.ItemDataRole.UserRole)
            is_group = isinstance(data, tuple) and data[0] in ('group', 'auto_group')
            if not text:
                item.setHidden(False)
                for j in range(item.childCount()):
                    _filter_item(item.child(j))
                return True
            haystacks = [item.text(0).lower()]
            tip = item.toolTip(0)
            if tip:
                haystacks.append(tip.lower())
            if isinstance(data, tuple) and len(data) > 1:
                haystacks.append(str(data[1]).lower())
            self_match = any(text in h for h in haystacks)
            any_child_visible = False
            for j in range(item.childCount()):
                if _filter_item(item.child(j)):
                    any_child_visible = True
            visible = (self_match or any_child_visible) if not is_group else any_child_visible
            item.setHidden(not visible)
            if visible and (any_child_visible or self_match):
                item.setExpanded(True)
            return visible

        for tree in (getattr(self, 'products_tree', None),
                     getattr(self, 'tp_tree', None)):
            if tree is None:
                continue
            for i in range(tree.topLevelItemCount()):
                _filter_item(tree.topLevelItem(i))

    def focus_search(self):
        self._search_edit.setFocus()
        self._search_edit.selectAll()

    # ── Context menus ─────────────────────────────────────────────

    def _tp_context_menu(self, pos):
        item = self.tp_tree.itemAt(pos)
        menu = QMenu(self)

        new_tp = QAction("Создать ТП", self)
        new_tp.triggered.connect(lambda: self.new_tp_requested.emit(None))
        menu.addAction(new_tp)

        if item:
            tp_id = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(tp_id, int):
                open_act = QAction("Открыть ТП", self)
                open_act.triggered.connect(
                    lambda checked, tid=tp_id: self.tp_double_clicked.emit(tid))
                menu.addAction(open_act)

        menu.exec(self.tp_tree.viewport().mapToGlobal(pos))
