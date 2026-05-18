"""Sidebar navigation panel — VSCode-style, theme-aware.

Module buttons moved to ActivityBar. Search moved to TitleBar.
All styling via QSS selectors (setObjectName / setProperty).
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QPushButton, QLineEdit, QMenu, QMessageBox,
    QLabel, QFrame, QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal

from database.models import (
    Product, ProductGroup, TechProcess, TPStatus,
)

STATUS_BADGE = {
    TPStatus.DRAFT:    ("#f97316", "Черновик"),
    TPStatus.REVIEW:   ("#8b5cf6", "Согласование"),
    TPStatus.REWORK:   ("#ef4444", "Доработка"),
    TPStatus.APPROVED: ("#22c55e", "Утверждён"),
    TPStatus.ARCHIVED: ("#94a3b8", "Архив"),
}


class NavigationPanel(QWidget):
    # ── API signals (preserved for MainWindow compatibility) ──
    product_double_clicked = pyqtSignal(int)
    tp_double_clicked = pyqtSignal(int)
    product_edit_requested = pyqtSignal(int)
    product_delete_requested = pyqtSignal(int)
    new_product_requested = pyqtSignal(object)   # group_id or None
    new_tp_requested = pyqtSignal(object)
    new_subgroup_requested = pyqtSignal(int)       # parent_group_id
    move_product_requested = pyqtSignal(int, int)  # product_id, target_group_id

    # ── Legacy module signals (no-op shims for test compatibility) ──
    production_clicked = pyqtSignal()
    qa_clicked = pyqtSignal()
    tooling_clicked = pyqtSignal()
    orders_clicked = pyqtSignal()
    pdo_clicked = pyqtSignal()
    dashboard_clicked = pyqtSignal()
    references_clicked = pyqtSignal()
    documents_clicked = pyqtSignal()
    users_clicked = pyqtSignal()
    audit_clicked = pyqtSignal()
    batch_clicked = pyqtSignal()

    def __init__(self, db_manager, user: dict = None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.user = user or {}
        self.setObjectName("nav_panel")
        self.setFixedWidth(290)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Section header: "ИЗДЕЛИЯ И ТП" + refresh + add ──
        section_hdr = QFrame()
        section_hdr.setObjectName("nav_section_header")
        sh_layout = QHBoxLayout(section_hdr)
        sh_layout.setContentsMargins(16, 0, 12, 0)

        title_lbl = QLabel("ИЗДЕЛИЯ И ТП")
        title_lbl.setObjectName("nav_section_title")
        sh_layout.addWidget(title_lbl)
        sh_layout.addStretch()

        refresh_btn = QPushButton("⟳")
        refresh_btn.setToolTip("Обновить")
        refresh_btn.clicked.connect(self.load_data)
        sh_layout.addWidget(refresh_btn)

        add_btn = QPushButton("+")
        add_btn.setToolTip("Новое изделие")
        add_btn.clicked.connect(lambda: self.new_product_requested.emit(None))
        sh_layout.addWidget(add_btn)
        layout.addWidget(section_hdr)

        # ── Inner tabs: Изделия / ТП ──
        self._inner_tabs = QTabWidget()
        self._inner_tabs.setObjectName("nav_inner_tabs")

        self._product_tree = QTreeWidget()
        self._product_tree.setObjectName("nav_tree")
        self._product_tree.setHeaderHidden(True)
        self._product_tree.setIndentation(16)
        self._product_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._product_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._product_tree.customContextMenuRequested.connect(self._on_context_menu)

        self._tp_tree = QTreeWidget()
        self._tp_tree.setObjectName("nav_tree")
        self._tp_tree.setHeaderHidden(True)
        self._tp_tree.setIndentation(16)
        self._tp_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tp_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tp_tree.customContextMenuRequested.connect(self._on_tp_context_menu)

        self._inner_tabs.addTab(self._product_tree, "Изделия")
        self._inner_tabs.addTab(self._tp_tree, "ТП")
        layout.addWidget(self._inner_tabs, 1)

        # ── Filter input ──
        self._search_edit = QLineEdit()
        self._search_edit.setObjectName("nav_filter")
        self._search_edit.setPlaceholderText("⚲  Фильтр изделий…")
        self._search_edit.textChanged.connect(self._on_search)
        layout.addWidget(self._search_edit)

        # ── Quick actions ──
        quick_frame = QFrame()
        quick_frame.setObjectName("nav_quick")
        ql = QHBoxLayout(quick_frame)
        ql.setContentsMargins(0, 0, 0, 0)
        ql.setSpacing(8)

        new_prod_btn = QPushButton("+ Изделие")
        new_prod_btn.clicked.connect(lambda: self.new_product_requested.emit(None))
        ql.addWidget(new_prod_btn)

        new_tp_btn = QPushButton("+ ТП")
        new_tp_btn.clicked.connect(lambda: self.new_tp_requested.emit(None))
        ql.addWidget(new_tp_btn)
        layout.addWidget(quick_frame)

        # ── User card ──
        user_frame = QFrame()
        user_frame.setObjectName("nav_user")
        uf_layout = QHBoxLayout(user_frame)
        uf_layout.setContentsMargins(0, 0, 0, 0)
        uf_layout.setSpacing(10)

        initial = (self.user.get("full_name") or self.user.get("username") or "?")[0].upper()
        avatar = QLabel(initial)
        avatar.setObjectName("nav_user_avatar")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        uf_layout.addWidget(avatar)

        info_col = QVBoxLayout()
        info_col.setSpacing(1)
        user_name = self.user.get("full_name") or self.user.get("username") or "?"
        name_lbl = QLabel(user_name)
        name_lbl.setObjectName("nav_user_name")
        info_col.addWidget(name_lbl)

        role_lbl = QLabel(f"{self.user.get('role', '')} · v1.0.0")
        role_lbl.setObjectName("nav_user_role")
        info_col.addWidget(role_lbl)
        uf_layout.addLayout(info_col)
        uf_layout.addStretch()
        layout.addWidget(user_frame)

        # ── Legacy aliases ──
        self.products_tree = self._product_tree

        # Fake search_input for test compatibility (real search moved to TitleBar)
        self.search_input = QLineEdit()
        self.search_input.hide()

    def focus_search(self):
        self._search_edit.setFocus()
        self._search_edit.selectAll()

    def _on_search(self, text):
        self._populate_products(text)
        self._populate_tps(text)

    def _on_item_double_clicked(self, item, column):
        entity_id = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if entity_id is None:
            return
        if item_type == "product":
            self.product_double_clicked.emit(entity_id)
        elif item_type == "tp":
            self.tp_double_clicked.emit(entity_id)

    def _on_context_menu(self, pos):
        item = self._product_tree.itemAt(pos)
        if item is None:
            return
        entity_id = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = item.data(0, Qt.ItemDataRole.UserRole + 1)

        menu = QMenu(self)

        if item_type == "group":
            if entity_id is not None and entity_id >= 0:
                a = menu.addAction("＋ Новое изделие")
                a.triggered.connect(
                    lambda checked=False, gid=entity_id:
                        self.new_product_requested.emit(gid))
            a = menu.addAction("＋ Новая подгруппа")
            a.triggered.connect(
                lambda checked=False, gid=entity_id:
                    self.new_subgroup_requested.emit(gid))
            menu.addSeparator()
            if entity_id is not None and entity_id >= 0:
                a = menu.addAction("✎ Редактировать группу")
                a.triggered.connect(
                    lambda checked=False, gid=entity_id: self._edit_group(gid))
                a = menu.addAction("🗑 Удалить группу")
                a.triggered.connect(
                    lambda checked=False, gid=entity_id: self._delete_group(gid))
            menu.addSeparator()
            a = menu.addAction("♻ Обновить")
            a.triggered.connect(
                lambda: self._populate_products(self._search_edit.text()))

        elif item_type == "product":
            a = menu.addAction("✎ Редактировать")
            a.triggered.connect(
                lambda: self.product_edit_requested.emit(entity_id))
            a = menu.addAction("＋ Новый ТП")
            a.triggered.connect(
                lambda: self.new_tp_requested.emit(entity_id))
            # Подменю: переместить в группу
            move_menu = menu.addMenu("Переместить в группу")
            self._build_move_menu(move_menu, entity_id)
            menu.addSeparator()
            a = menu.addAction("🗑 Удалить")
            a.triggered.connect(
                lambda: self.product_delete_requested.emit(entity_id))

        menu.exec(self._product_tree.viewport().mapToGlobal(pos))

    def _build_move_menu(self, menu, product_id):
        """Построить подменю выбора группы для перемещения изделия."""
        try:
            with self.db_manager.get_session() as s:
                groups = s.query(ProductGroup).order_by(ProductGroup.name).all()
                for g in groups:
                    a = menu.addAction(g.name)
                    a.triggered.connect(
                        lambda checked=False, gid=g.id, pid=product_id:
                            self._move_product(pid, gid))
                menu.addSeparator()
                a = menu.addAction("Без группы")
                a.triggered.connect(
                    lambda checked=False, pid=product_id:
                        self._move_product(pid, None))
        except Exception:
            pass

    def _move_product(self, product_id, group_id):
        """Переместить изделие в другую группу."""
        try:
            with self.db_manager.get_session() as s:
                p = s.get(Product, product_id)
                if p:
                    p.group_id = group_id
                    s.commit()
            self._populate_products(self._search_edit.text())
            self._product_tree.update()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось переместить: {e}")

    def _edit_group(self, group_id):
        """Редактировать название группы."""
        try:
            with self.db_manager.get_session() as s:
                g = s.get(ProductGroup, group_id)
                if g is None:
                    return
                from PyQt6.QtWidgets import QInputDialog
                new_name, ok = QInputDialog.getText(
                    self, "Редактировать группу",
                    "Название группы:", text=g.name)
                if ok and new_name.strip():
                    g.name = new_name.strip()
                    s.commit()
            self._populate_products(self._search_edit.text())
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось: {e}")

    def _delete_group(self, group_id):
        """Удалить группу (изделия переходят в «Без группы»)."""
        try:
            with self.db_manager.get_session() as s:
                g = s.get(ProductGroup, group_id)
                if g is None:
                    return
                ans = QMessageBox.question(
                    self, "Удалить группу",
                    f"Удалить группу «{g.name}»?\n"
                    "Изделия из этой группы останутся и перейдут в «Без группы».",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if ans != QMessageBox.StandardButton.Yes:
                    return
                # Unlink products
                s.query(Product).filter(
                    Product.group_id == group_id).update(
                    {Product.group_id: None})
                s.delete(g)
                s.commit()
            self._populate_products(self._search_edit.text())
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось удалить группу: {e}")

    def _on_tp_context_menu(self, pos):
        item = self._tp_tree.itemAt(pos)
        if item is None:
            return
        entity_id = item.data(0, Qt.ItemDataRole.UserRole)
        if entity_id is None:
            return
        menu = QMenu(self)
        menu.addAction("Открыть ТП",
                      lambda: self.tp_double_clicked.emit(entity_id))
        menu.exec(self._tp_tree.viewport().mapToGlobal(pos))

    def load_data(self, search: str = ""):
        self._populate_products(search)
        self._populate_tps(search)

    def _populate_products(self, search: str = ""):
        self._product_tree.clear()
        try:
            with self.db_manager.get_session() as s:
                groups = s.query(ProductGroup).order_by(ProductGroup.name).all()
                for g in groups:
                    grp_item = QTreeWidgetItem([f"{g.name}"])
                    grp_item.setData(0, Qt.ItemDataRole.UserRole, g.id)
                    grp_item.setData(0, Qt.ItemDataRole.UserRole + 1, "group")
                    grp_item.setToolTip(0, f"Группа: {g.name}")
                    self._product_tree.addTopLevelItem(grp_item)

                    q = s.query(Product).filter(
                        Product.is_deleted == False,
                        Product.group_id == g.id,
                    )
                    if search:
                        q = q.filter(
                            Product.designation.ilike(f"%{search}%"))
                    for p in q.order_by(Product.designation).all():
                        item = QTreeWidgetItem([p.designation])
                        item.setData(0, Qt.ItemDataRole.UserRole, p.id)
                        item.setData(0, Qt.ItemDataRole.UserRole + 1, "product")
                        item.setToolTip(0, f"{p.designation} — {p.name}")
                        grp_item.addChild(item)

                # Изделия без группы
                q = s.query(Product).filter(
                    Product.is_deleted == False,
                    Product.group_id.is_(None),
                )
                if search:
                    q = q.filter(
                        Product.designation.ilike(f"%{search}%"))
                ungrouped = q.order_by(Product.designation).all()
                if ungrouped:
                    grp_item = QTreeWidgetItem(["Без группы"])
                    grp_item.setData(0, Qt.ItemDataRole.UserRole, -1)
                    grp_item.setData(0, Qt.ItemDataRole.UserRole + 1, "group")
                    grp_item.setToolTip(0, "Изделия без группы")
                    self._product_tree.addTopLevelItem(grp_item)
                    for p in ungrouped:
                        item = QTreeWidgetItem([p.designation])
                        item.setData(0, Qt.ItemDataRole.UserRole, p.id)
                        item.setData(0, Qt.ItemDataRole.UserRole + 1, "product")
                        item.setToolTip(0, f"{p.designation} — {p.name}")
                        grp_item.addChild(item)
        except Exception:
            pass

    def _populate_tps(self, search: str = ""):
        self._tp_tree.clear()
        try:
            with self.db_manager.get_session() as s:
                q = s.query(TechProcess).filter(
                    TechProcess.is_deleted == False)
                if search:
                    q = q.filter(TechProcess.number.ilike(f"%{search}%"))
                for tp in q.order_by(TechProcess.number).all():
                    item = QTreeWidgetItem([f"{tp.number}"])
                    item.setData(0, Qt.ItemDataRole.UserRole, tp.id)
                    item.setData(0, Qt.ItemDataRole.UserRole + 1, "tp")
                    item.setToolTip(0,
                        f"{tp.number} — "
                        f"{tp.product.designation if tp.product else '—'}")
                    self._tp_tree.addTopLevelItem(item)
        except Exception:
            pass
