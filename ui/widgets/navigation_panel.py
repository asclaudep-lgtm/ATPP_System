"""
Sidebar navigation panel — Fluent Design, dark sidebar.

All styling lives in ui/theme.py (via #nav_panel QSS selectors).
This file contains NO inline setStyleSheet calls.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QPushButton, QLineEdit, QMenu, QMessageBox,
    QLabel, QFrame, QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QFont

from database.models import (
    Product, ProductGroup, TechProcess, TPStatus,
)
from ui.fluent_compat import LineEdit, PushButton, QFLUENT_AVAILABLE

STATUS_BADGE = {
    TPStatus.DRAFT:    ("#f97316", "Черновик"),
    TPStatus.REVIEW:   ("#8b5cf6", "Согласование"),
    TPStatus.REWORK:   ("#ef4444", "Доработка"),
    TPStatus.APPROVED: ("#22c55e", "Утверждён"),
    TPStatus.ARCHIVED: ("#94a3b8", "Архив"),
}


class ModuleButton(QPushButton):
    """Clickable module button — styled by theme QSS."""

    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.setText(f"  {icon}  {label}")
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setProperty("module_btn", True)


class NavigationPanel(QWidget):
    product_double_clicked = pyqtSignal(int)
    tp_double_clicked = pyqtSignal(int)
    product_edit_requested = pyqtSignal(int)
    product_delete_requested = pyqtSignal(int)
    new_product_requested = pyqtSignal()
    new_tp_requested = pyqtSignal(object)

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
        self.setMinimumWidth(260)
        self.setMaximumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ──
        header = QFrame()
        header.setObjectName("nav_header")
        header.setFixedHeight(52)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 8, 16, 8)

        icon_lbl = QLabel("A")
        icon_lbl.setObjectName("nav_logo")
        icon_lbl.setFixedSize(28, 28)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_layout.addWidget(icon_lbl)

        title_lbl = QLabel("ATPP System")
        title_lbl.setObjectName("nav_title")
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        layout.addWidget(header)

        # ── Quick actions ──
        actions_frame = QFrame()
        actions_frame.setObjectName("nav_actions")
        al = QHBoxLayout(actions_frame)
        al.setContentsMargins(12, 8, 12, 8)
        al.setSpacing(8)

        new_prod_btn = QPushButton("＋ Изделие")
        new_prod_btn.setObjectName("nav_action_btn")
        new_prod_btn.setProperty("accent", "orange")
        new_prod_btn.setFixedHeight(32)
        new_prod_btn.clicked.connect(self.new_product_requested)
        al.addWidget(new_prod_btn)

        new_tp_btn = QPushButton("＋ ТП")
        new_tp_btn.setObjectName("nav_action_btn")
        new_tp_btn.setProperty("accent", "purple")
        new_tp_btn.setFixedHeight(32)
        new_tp_btn.clicked.connect(lambda: self.new_tp_requested.emit(None))
        al.addWidget(new_tp_btn)
        al.addStretch()
        layout.addWidget(actions_frame)

        # ── Module buttons ──
        modules_scroll = QScrollArea()
        modules_scroll.setObjectName("nav_modules_scroll")
        modules_scroll.setWidgetResizable(True)
        modules_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        modules_widget = QWidget()
        modules_widget.setObjectName("nav_modules_widget")
        mod_layout = QVBoxLayout(modules_widget)
        mod_layout.setContentsMargins(0, 8, 0, 8)
        mod_layout.setSpacing(1)

        # Section: Production
        self._add_section_label(mod_layout, "ПРОИЗВОДСТВО")
        self._mod_dashboard = ModuleButton("📊", "Дашборд")
        self._mod_dashboard.clicked.connect(self.dashboard_clicked)
        mod_layout.addWidget(self._mod_dashboard)

        self._mod_orders = ModuleButton("📋", "Производственные заказы")
        self._mod_orders.clicked.connect(self.orders_clicked)
        mod_layout.addWidget(self._mod_orders)

        self._mod_pdo = ModuleButton("📦", "Диспетчер ПДО")
        self._mod_pdo.clicked.connect(self.pdo_clicked)
        mod_layout.addWidget(self._mod_pdo)

        self._mod_qa = ModuleButton("✓", "QA-терминал")
        self._mod_qa.clicked.connect(self.qa_clicked)
        mod_layout.addWidget(self._mod_qa)

        self._mod_tooling = ModuleButton("🔧", "Оснастка и инструмент")
        self._mod_tooling.clicked.connect(self.tooling_clicked)
        mod_layout.addWidget(self._mod_tooling)

        # Section: Data
        self._add_section_label(mod_layout, "ДАННЫЕ")
        self._mod_refs = ModuleButton("📚", "Справочники")
        self._mod_refs.clicked.connect(self.references_clicked)
        mod_layout.addWidget(self._mod_refs)

        self._mod_docs = ModuleButton("📄", "Документы")
        self._mod_docs.clicked.connect(self.documents_clicked)
        mod_layout.addWidget(self._mod_docs)

        # Section: System (admin only)
        if self.user.get("role") == "admin":
            self._add_section_label(mod_layout, "СИСТЕМА")
            self._mod_users = ModuleButton("👤", "Пользователи")
            self._mod_users.clicked.connect(self.users_clicked)
            mod_layout.addWidget(self._mod_users)

        self._mod_audit = ModuleButton("📋", "Аудит изменений")
        self._mod_audit.clicked.connect(self.audit_clicked)
        mod_layout.addWidget(self._mod_audit)

        self._mod_batch = ModuleButton("⚡", "Batch-операции")
        self._mod_batch.clicked.connect(self.batch_clicked)
        mod_layout.addWidget(self._mod_batch)

        mod_layout.addStretch()
        modules_scroll.setWidget(modules_widget)
        layout.addWidget(modules_scroll)

        # ── Tree view ──
        self._tab_widget = QTabWidget()
        self._tab_widget.setObjectName("nav_tabs")

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

        self._tab_widget.addTab(self._product_tree, "📦 Изделия")
        self._tab_widget.addTab(self._tp_tree, "📋 ТП")
        layout.addWidget(self._tab_widget, 1)

        # ── User footer ──
        footer = QFrame()
        footer.setObjectName("nav_footer")
        footer.setFixedHeight(52)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(16, 8, 16, 8)

        initial = (self.user.get("full_name") or self.user.get("username") or "?")[0].upper()
        avatar = QLabel(initial)
        avatar.setObjectName("nav_avatar")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f_layout.addWidget(avatar)

        user_name = self.user.get("full_name") or self.user.get("username")
        user_role = self.user.get("role") or ""
        user_info = QLabel(f"{user_name}\n{user_role}")
        user_info.setObjectName("nav_user_info")
        f_layout.addWidget(user_info)
        f_layout.addStretch()
        layout.addWidget(footer)

        # ── Search ──
        self._search_edit = LineEdit()
        self._search_edit.setObjectName("nav_search")
        self._search_edit.setPlaceholderText("🔎 Поиск...")
        self._search_edit.textChanged.connect(self._on_search)
        layout.addWidget(self._search_edit)

        # Legacy public names
        self.products_tree = self._product_tree

    def focus_search(self):
        self._search_edit.setFocus()
        self._search_edit.selectAll()

    def _add_section_label(self, layout, text):
        lbl = QLabel(text)
        lbl.setObjectName("nav_section_label")
        layout.addWidget(lbl)

    def _on_search(self, text):
        self._populate_products(text)

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
        if entity_id is None:
            return
        menu = QMenu(self)
        if item_type == "product":
            menu.addAction("✎ Редактировать", lambda: self.product_edit_requested.emit(entity_id))
            menu.addAction("＋ Новый ТП", lambda: self.new_tp_requested.emit(entity_id))
            menu.addAction("🗑 Удалить", lambda: self.product_delete_requested.emit(entity_id))
        elif item_type == "tp":
            menu.addAction("Открыть ТП", lambda: self.tp_double_clicked.emit(entity_id))
        menu.exec(self._product_tree.viewport().mapToGlobal(pos))

    def _on_tp_context_menu(self, pos):
        item = self._tp_tree.itemAt(pos)
        if item is None:
            return
        entity_id = item.data(0, Qt.ItemDataRole.UserRole)
        if entity_id is None:
            return
        menu = QMenu(self)
        menu.addAction("Открыть ТП", lambda: self.tp_double_clicked.emit(entity_id))
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
                    grp_item = QTreeWidgetItem([f"▸ {g.name}"])
                    grp_item.setFlags(grp_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                    grp_item.setData(0, Qt.ItemDataRole.UserRole, None)
                    self._product_tree.addTopLevelItem(grp_item)

                    q = s.query(Product).filter(
                        Product.is_deleted == False,
                        Product.group_id == g.id,
                    )
                    if search:
                        q = q.filter(Product.designation.ilike(f"%{search}%"))
                    for p in q.order_by(Product.designation).all():
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
                q = s.query(TechProcess).filter(TechProcess.is_deleted == False)
                if search:
                    q = q.filter(TechProcess.number.ilike(f"%{search}%"))
                for tp in q.order_by(TechProcess.number).all():
                    item = QTreeWidgetItem([f"{tp.number}"])
                    item.setData(0, Qt.ItemDataRole.UserRole, tp.id)
                    item.setData(0, Qt.ItemDataRole.UserRole + 1, "tp")
                    color, status_text = STATUS_BADGE.get(tp.status, ("#94a3b8", str(tp.status)))
                    item.setToolTip(0, f"{tp.number} — {tp.product.designation if tp.product else '—'} [{status_text}]")
                    self._tp_tree.addTopLevelItem(item)
        except Exception:
            pass
