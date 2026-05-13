"""
Главное окно приложения АТПП
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QLabel, QPushButton, QLineEdit, QToolBar, QStatusBar, 
    QMenuBar, QMenu, QMessageBox, QDockWidget, QTextEdit,
    QSizePolicy, QFrame, QSpacerItem
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QSettings
from PyQt6.QtGui import QAction, QKeySequence, QFont, QColor, QIcon, QPixmap

from config import APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT
from database.models import (
    Product, ProductGroup, TechProcess, TPStatus, TPType
)


STATUS_BADGE = {
    TPStatus.DRAFT:    ('#f39c12', 'Черновик'),
    TPStatus.REVIEW:   ('#8e44ad', 'Согласование'),
    TPStatus.REWORK:   ('#e74c3c', 'Доработка'),
    TPStatus.APPROVED: ('#27ae60', 'Утверждён'),
    TPStatus.ARCHIVED: ('#95a5a6', 'Архив'),
}


class MainWindow(QMainWindow):
    """Главное окно системы АТПП"""

    def __init__(self, db_manager, user):
        print("[DEBUG] Loading MainWindow from:", __file__)
        super().__init__()
        self.db_manager = db_manager
        self.user = user

        self.setWindowTitle("УЗГА-Инжиниринг АТПП- Система автоматизации технологической подготовки производства")
        print("DEBUG_TITLE:", self.windowTitle())
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self._open_tp_tabs = {}  # tp_id -> tab index

        self._init_ui()
        self._create_menu()
        self._create_toolbar()
        self._create_statusbar()
        self._install_hotkeys()
        self.load_navigation_data()

    # ──────────────────────────────────────────────────────────────
    # Основной UI
    # ──────────────────────────────────────────────────────────────
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # Верхний branding header + main content
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Верхнее branding удалено

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая панель навигации
        nav_panel = self._make_nav_panel()
        splitter.addWidget(nav_panel)

        # Рабочая область (вкладки)
        self.work_area = QTabWidget()
        self.work_area.setTabsClosable(True)
        self.work_area.setMovable(True)
        self.work_area.tabCloseRequested.connect(self._close_tab)
        self.work_area.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #bdc3c7; }
            QTabBar::tab { padding: 6px 14px; min-width: 120px; }
            QTabBar::tab:selected { background: #ecf0f1; font-weight: bold; }
        """)
        splitter.addWidget(self.work_area)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([270, WINDOW_WIDTH - 270])
        splitter.setHandleWidth(2)
        # v7.7h: восстанавливаем сохранённое положение разделителя.
        self._main_splitter = splitter
        try:
            settings = QSettings('ATPP', f"main_window_{self.user.get('username','default')}")
            state = settings.value('splitter_state')
            if state is not None:
                splitter.restoreState(state)
        except Exception:
            pass
        # Сохраняем при изменении (debounced — каждое движение)
        splitter.splitterMoved.connect(self._save_splitter_state)

        main_layout.addWidget(splitter)

        # Нижняя панель сообщений
        self._messages_dock = self._make_messages_dock()
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._messages_dock)
        self._messages_dock.hide()

    # ──────────────────────────────────────────────────────────────
    # Навигационная панель
    # ──────────────────────────────────────────────────────────────
    def _make_nav_panel(self):
        panel = QWidget()
        panel.setMinimumWidth(240)
        panel.setMaximumWidth(340)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Поиск
        search_layout = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Поиск...")
        self._search_edit.textChanged.connect(self._on_search)
        search_layout.addWidget(self._search_edit)
        layout.addLayout(search_layout)

        # Вкладки навигации
        nav_tabs = QTabWidget()
        nav_tabs.setTabPosition(QTabWidget.TabPosition.South)

        # Вкладка «Изделия»
        products_panel = QWidget()
        pl = QVBoxLayout(products_panel)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(2)

        prod_btns = QHBoxLayout()
        add_prod_btn = QPushButton("+ Изделие")
        add_prod_btn.setFixedHeight(24)
        add_prod_btn.clicked.connect(self._new_product)
        add_prod_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border: none; padding: 2px 8px; border-radius: 3px; }")
        edit_prod_btn = QPushButton("Ред.")
        edit_prod_btn.setFixedHeight(24)
        edit_prod_btn.clicked.connect(self._edit_selected_product)
        edit_prod_btn.setStyleSheet("QPushButton { background-color: #2980b9; color: white; border: none; padding: 2px 6px; border-radius: 3px; }")
        del_prod_btn = QPushButton("Удал.")
        del_prod_btn.setFixedHeight(24)
        del_prod_btn.clicked.connect(self._delete_selected_product)
        del_prod_btn.setStyleSheet("QPushButton { color: #e74c3c; border: none; padding: 2px 6px; }")
        prod_btns.addWidget(add_prod_btn)
        prod_btns.addWidget(edit_prod_btn)
        prod_btns.addWidget(del_prod_btn)
        prod_btns.addStretch()
        pl.addLayout(prod_btns)

        # v7.7: новое дерево «Группа» — только группы + детали (без ТП-узлов).
        from ui.widgets.group_tree import GroupTreeWidget
        self.group_tree = GroupTreeWidget(self.db_manager)
        self.group_tree.product_double_clicked.connect(self._open_product_ktp)
        self.group_tree.product_edit_requested.connect(self._edit_product)
        self.group_tree.product_delete_requested.connect(self._delete_product)
        self.group_tree.new_product_requested.connect(
            lambda gid: self._new_product())
        self.group_tree.template_double_clicked.connect(self._open_tp_editor)
        # Псевдоним для совместимости со старым кодом (поиск/контекстные меню).
        self.products_tree = self.group_tree
        pl.addWidget(self.group_tree)
        nav_tabs.addTab(products_panel, "Группа")

        # Вкладка «ТП»
        tp_panel = QWidget()
        tpl = QVBoxLayout(tp_panel)
        tpl.setContentsMargins(0, 0, 0, 0)
        tpl.setSpacing(2)

        tp_btns = QHBoxLayout()
        add_tp_btn = QPushButton("+ ТП")
        add_tp_btn.setFixedHeight(24)
        add_tp_btn.clicked.connect(self._new_tech_process)
        add_tp_btn.setStyleSheet("QPushButton { background-color: #8e44ad; color: white; border: none; padding: 2px 8px; border-radius: 3px; }")
        refresh_btn = QPushButton("↺")
        refresh_btn.setFixedHeight(24)
        refresh_btn.setToolTip("Обновить")
        refresh_btn.clicked.connect(self.load_navigation_data)
        tp_btns.addWidget(add_tp_btn)
        tp_btns.addStretch()
        tp_btns.addWidget(refresh_btn)
        tpl.addLayout(tp_btns)

        self.tp_tree = QTreeWidget()
        self.tp_tree.setHeaderHidden(True)
        self.tp_tree.itemDoubleClicked.connect(self._on_tp_double_click)
        self.tp_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tp_tree.customContextMenuRequested.connect(self._tp_context_menu)
        tpl.addWidget(self.tp_tree)
        nav_tabs.addTab(tp_panel, "ТП")

        layout.addWidget(nav_tabs)
        self._nav_tabs = nav_tabs
        return panel

    # ──────────────────────────────────────────────────────────────
    # Загрузка данных в навигацию
    # ──────────────────────────────────────────────────────────────
    def load_navigation_data(self):
        self._load_products_tree()
        self._load_tp_tree()

    def _load_products_tree(self):
        # v7.7: дерево «Группа» строится новым виджетом GroupTreeWidget.
        if hasattr(self, 'group_tree'):
            self.group_tree.reload()
            return

        # ── Старый билдер (deprecated, оставлен для обратной совместимости) ──
        self.products_tree.clear()
        session = self.db_manager.Session()
        try:
            # Загружаем корневые группы (без родителя), сортированные
            root_groups = (session.query(ProductGroup)
                           .filter(ProductGroup.parent_id.is_(None))
                           .order_by(ProductGroup.sort_order, ProductGroup.name)
                           .all())

            group_items: dict[int, QTreeWidgetItem] = {}  # group_id → QTreeWidgetItem

            def make_group_item(group: ProductGroup) -> QTreeWidgetItem:
                if group.id in group_items:
                    return group_items[group.id]
                display = group.display_name or group.name
                # Считаем изделия в группе (рекурсивно)
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

            # Рекурсивно строим дерево групп
            def add_group_to_tree(group: ProductGroup, parent_item=None):
                g_item = make_group_item(group)
                if parent_item is None:
                    self.products_tree.addTopLevelItem(g_item)
                else:
                    parent_item.addChild(g_item)
                # Подгруппы
                for child_group in sorted(group.children,
                                          key=lambda g: (g.sort_order, g.name)):
                    add_group_to_tree(child_group, g_item)
                # Изделия в этой группе
                products = (session.query(Product)
                            .filter_by(group_id=group.id)
                            .order_by(Product.designation)
                            .all())
                # Префикс группы для отрезания у обозначений (чтобы под "1.7601"
                # не плодилась повторная папка "1")
                group_prefix = (group.name or '').strip()
                for p in products:
                    _add_product_item(p, g_item, group_prefix=group_prefix)
                # Разворачиваем группы с небольшим числом элементов
                if _count_products_in_group(session, group) <= 50:
                    g_item.setExpanded(True)

            # Кеш авто-подгрупп: (parent_item_id, prefix) → QTreeWidgetItem
            auto_subgroups: dict[tuple[int, str], QTreeWidgetItem] = {}

            def _get_or_make_subgroup(parent_item: QTreeWidgetItem, prefix: str) -> QTreeWidgetItem:
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

            def _split_designation(designation: str) -> list[str]:
                """Разбить обозначение по разделителям '.' / ' ' на сегменты."""
                import re
                parts = [s for s in re.split(r'[.\s]+', (designation or '').strip()) if s]
                return parts

            def _add_product_item(p: Product, group_item: QTreeWidgetItem,
                                  group_prefix: str = ''):
                """Добавляет изделие в группу, авто-создавая промежуточные подгруппы
                по сегментам обозначения. Последний сегмент — лист (само изделие).

                ``group_prefix`` — префикс группы (например ``"1.7601"`` или
                ``"11-74.80"``), который вырезается из начала обозначения, чтобы
                не дублировать его в авто-подгруппах.
                """
                designation = (p.designation or '').strip()
                # Срезаем префикс группы, если обозначение начинается с него
                trimmed = designation
                if group_prefix and designation.startswith(group_prefix):
                    rest = designation[len(group_prefix):]
                    if rest.startswith('.') or rest.startswith(' ') or not rest:
                        trimmed = rest.lstrip('. ')
                parts = _split_designation(trimmed)
                # Идём по всем сегментам кроме последнего, наращивая префикс
                container = group_item
                for i in range(len(parts) - 1):
                    prefix = '.'.join(parts[: i + 1])
                    container = _get_or_make_subgroup(container, prefix)

                item = QTreeWidgetItem()
                # В листе показываем полное обозначение детали — так нагляднее,
                # чем только последние 3 цифры (две детали могут совпасть по «000»).
                item.setText(0, f"{designation}  —  {p.name}")
                item.setData(0, Qt.ItemDataRole.UserRole, p.id)
                item.setToolTip(0,
                    f"Обозначение: {p.designation}\n"
                    f"Наименование: {p.name}\n"
                    f"Материал: {p.material.name if p.material else '—'}\n"
                    f"Масса: {p.mass or '—'} кг"
                )
                container.addChild(item)
                # ТП как дочерние узлы (без помещённых в корзину)
                tps = (session.query(TechProcess)
                       .filter(TechProcess.product_id == p.id,
                               (TechProcess.is_deleted == False) | (TechProcess.is_deleted.is_(None)))
                       .all())
                for tp in tps:
                    color, status_label = STATUS_BADGE.get(tp.status, ('#555', str(tp.status)))
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

            # Добавляем все корневые группы
            for root_group in root_groups:
                add_group_to_tree(root_group)

            # Изделия без группы — в конец
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
            # Группируем по статусу
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

    # ──────────────────────────────────────────────────────────────
    # Поиск в навигации
    # ──────────────────────────────────────────────────────────────
    def _on_search(self, text):
        # v7.7: новое дерево умеет фильтровать само
        if hasattr(self, 'group_tree') and self.group_tree is self.products_tree:
            self.group_tree.set_search(text)
            self._on_search_tp_tree(text)
            return
        self._on_search_legacy(text)

    def _on_search_tp_tree(self, text):
        """Фильтрация tp_tree (по статусам)."""
        text = (text or '').lower().strip()

        def _filt(item) -> bool:
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

        def _filter_item(item) -> bool:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            is_group = isinstance(data, tuple) and data[0] in ('group', 'auto_group')

            if not text:
                item.setHidden(False)
                for j in range(item.childCount()):
                    _filter_item(item.child(j))
                return True

            # Совпадение по видимому тексту, тултипу и UserRole-данным
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

    # ──────────────────────────────────────────────────────────────
    # Двойной клик по элементам навигации
    # ──────────────────────────────────────────────────────────────
    def _on_product_double_click(self, item, col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple) and data[0] == 'tp':
            self._open_tp_editor(data[1])
        elif isinstance(data, tuple) and data[0] == 'group':
            # Двойной клик по группе — свернуть/развернуть
            item.setExpanded(not item.isExpanded())
        elif isinstance(data, int):
            # Клик по изделию — открываем редактирование
            self._edit_product(data)

    def _on_tp_double_click(self, item, col):
        tp_id = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(tp_id, int):
            self._open_tp_editor(tp_id)

    # ──────────────────────────────────────────────────────────────
    # Открытие редактора ТП
    # ──────────────────────────────────────────────────────────────
    def _open_product_ktp(self, product_id: int):
        """v7.7: Открыть карточку КТП для одной детали (вкладка с вариантами ТП)."""
        if not hasattr(self, '_open_ktp_tabs'):
            self._open_ktp_tabs = {}
        if product_id in self._open_ktp_tabs:
            idx = self._open_ktp_tabs[product_id]
            if idx < self.work_area.count():
                self.work_area.setCurrentIndex(idx)
                return

        from ui.widgets.product_ktp import ProductKTPWidget
        widget = ProductKTPWidget(
            self.db_manager, product_id, self.user, self)
        widget.tp_changed.connect(self._on_tp_changed)

        title = widget.get_tab_title()
        idx = self.work_area.addTab(widget, title)
        self.work_area.setCurrentIndex(idx)
        self._open_ktp_tabs[product_id] = idx
        self._log_message(f"Открыт КТП: {title}")

    def _open_tp_editor(self, tp_id):
        # Если уже открыт — переключаемся
        if tp_id in self._open_tp_tabs:
            idx = self._open_tp_tabs[tp_id]
            if idx < self.work_area.count():
                self.work_area.setCurrentIndex(idx)
                return

        from ui.widgets.tp_editor import TPEditorWidget
        editor = TPEditorWidget(self.db_manager, tp_id, self.user, self)
        editor.tp_changed.connect(self._on_tp_changed)

        title = editor.get_tab_title()
        idx = self.work_area.addTab(editor, title)
        self.work_area.setCurrentIndex(idx)
        self._open_tp_tabs[tp_id] = idx
        self._log_message(f"Открыт ТП: {title}")

        # D18: фиксируем «недавно открытое»
        try:
            from modules import bookmarks
            with self.db_manager.get_session() as s:
                bookmarks.track_open(
                    s, user_id=self.user.get('id'),
                    target_type='tech_process',
                    target_id=int(tp_id),
                    title=title,
                )
        except Exception as e:
            print(f'[bookmarks] track_open skipped: {e}')

    def _on_tp_changed(self, tp_id):
        # Обновляем заголовок вкладки
        if tp_id in self._open_tp_tabs:
            idx = self._open_tp_tabs[tp_id]
            if idx < self.work_area.count():
                widget = self.work_area.widget(idx)
                if hasattr(widget, 'get_tab_title'):
                    self.work_area.setTabText(idx, widget.get_tab_title())
        self._load_tp_tree()
        self._load_products_tree()

    def _close_tab(self, index):
        widget = self.work_area.widget(index)
        # ТП-редакторы (старая карта)
        tp_id_to_remove = None
        for tp_id, idx in self._open_tp_tabs.items():
            if idx == index:
                tp_id_to_remove = tp_id
                break
        if tp_id_to_remove is not None:
            del self._open_tp_tabs[tp_id_to_remove]
            self._open_tp_tabs = {
                tid: (i if i < index else i - 1)
                for tid, i in self._open_tp_tabs.items()
            }
        # КТП-карточки (v7.7)
        if hasattr(self, '_open_ktp_tabs'):
            ktp_to_remove = None
            for pid, idx in self._open_ktp_tabs.items():
                if idx == index:
                    ktp_to_remove = pid
                    break
            if ktp_to_remove is not None:
                del self._open_ktp_tabs[ktp_to_remove]
                self._open_ktp_tabs = {
                    pid: (i if i < index else i - 1)
                    for pid, i in self._open_ktp_tabs.items()
                }
        self.work_area.removeTab(index)

    # ──────────────────────────────────────────────────────────────
    # Контекстные меню
    # ──────────────────────────────────────────────────────────────
    def _product_context_menu(self, pos):
        item = self.products_tree.itemAt(pos)
        menu = QMenu(self)

        new_prod = QAction("Новое изделие", self)
        new_prod.triggered.connect(self._new_product)
        menu.addAction(new_prod)

        if item:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, int):
                edit_act = QAction("Редактировать изделие", self)
                edit_act.triggered.connect(lambda: self._edit_product(data))
                menu.addAction(edit_act)

                add_tp_act = QAction("Создать ТП для этого изделия", self)
                add_tp_act.triggered.connect(lambda: self._new_tech_process(product_id=data))
                menu.addAction(add_tp_act)

                menu.addSeparator()
                del_act = QAction("Удалить изделие", self)
                del_act.triggered.connect(lambda: self._delete_product(data))
                menu.addAction(del_act)

            elif isinstance(data, tuple) and data[0] == 'tp':
                tp_id = data[1]
                open_act = QAction("Открыть ТП", self)
                open_act.triggered.connect(lambda: self._open_tp_editor(tp_id))
                menu.addAction(open_act)

                menu.addSeparator()
                variant_act = QAction("Создать вариант исполнения ТП…", self)
                variant_act.triggered.connect(lambda: self._copy_tp(tp_id))
                menu.addAction(variant_act)

                copy_act = QAction("Копировать ТП…", self)
                copy_act.triggered.connect(lambda: self._copy_tp(tp_id))
                menu.addAction(copy_act)

                snap_act = QAction("Сохранить снимок версии…", self)
                snap_act.triggered.connect(lambda: self._snapshot_tp(tp_id))
                menu.addAction(snap_act)

                hist_act = QAction("История версий…", self)
                hist_act.triggered.connect(lambda: self._show_tp_history(tp_id))
                menu.addAction(hist_act)

                arch_act = QAction("Архивировать ТП", self)
                arch_act.triggered.connect(lambda: self._archive_tp(tp_id))
                menu.addAction(arch_act)

                del_act = QAction("Удалить ТП", self)
                del_act.triggered.connect(lambda: self._delete_tp(tp_id))
                menu.addAction(del_act)

        menu.exec(self.products_tree.viewport().mapToGlobal(pos))

    def _tp_context_menu(self, pos):
        item = self.tp_tree.itemAt(pos)
        menu = QMenu(self)

        new_tp = QAction("Создать ТП", self)
        new_tp.triggered.connect(self._new_tech_process)
        menu.addAction(new_tp)

        if item:
            tp_id = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(tp_id, int):
                open_act = QAction("Открыть ТП", self)
                open_act.triggered.connect(lambda: self._open_tp_editor(tp_id))
                menu.addAction(open_act)

                menu.addSeparator()
                copy_act = QAction("Копировать ТП", self)
                copy_act.triggered.connect(lambda: self._copy_tp(tp_id))
                menu.addAction(copy_act)

                snap_act = QAction("Сохранить снимок версии…", self)
                snap_act.triggered.connect(lambda: self._snapshot_tp(tp_id))
                menu.addAction(snap_act)

                hist_act = QAction("История версий…", self)
                hist_act.triggered.connect(lambda: self._show_tp_history(tp_id))
                menu.addAction(hist_act)

                arch_act = QAction("Архивировать ТП", self)
                arch_act.triggered.connect(lambda: self._archive_tp(tp_id))
                menu.addAction(arch_act)

                del_act = QAction("Удалить ТП", self)
                del_act.triggered.connect(lambda: self._delete_tp(tp_id))
                menu.addAction(del_act)

        menu.exec(self.tp_tree.viewport().mapToGlobal(pos))

    # ──────────────────────────────────────────────────────────────
    # Управление изделиями
    # ──────────────────────────────────────────────────────────────
    def _new_product(self):
        from ui.dialogs.product_dialog import ProductDialog
        dlg = ProductDialog(self.db_manager, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            data = dlg.get_data()
            try:
                new_prod_id = None
                with self.db_manager.get_session() as session:
                    prod = Product(
                        designation=data['designation'],
                        name=data['name'],
                        material_id=data.get('material_id'),
                        mass=data.get('mass'),
                        dimensions=data.get('dimensions'),
                        blank_type=data.get('blank_type'),
                        accuracy_class=data.get('accuracy_class'),
                        roughness=data.get('roughness'),
                        quantity_in_assembly=data.get('quantity_in_assembly', 1),
                        description=data.get('description'),
                        author_id=self.user.get('id'),
                    )
                    session.add(prod)
                    session.flush()
                    new_prod_id = prod.id
                self.load_navigation_data()
                self._log_message(f"Изделие «{data['designation']}» создано")
                # Регистрация в журнале (с подтверждением и автономером)
                self._register_in_journal(
                    'product', new_prod_id, is_variant=False,
                    title='Регистрация изделия в журнале ТП/МТП',
                    prompt=(
                        f'Изделие «{data["designation"]} — {data["name"]}» создано.\n'
                        f'Зарегистрировать его в журнале ТП и МТП?'
                    ),
                )
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать изделие:\n{e}")

    def _edit_selected_product(self):
        item = self.products_tree.currentItem()
        if not item:
            QMessageBox.information(self, "Выбор", "Выберите изделие для редактирования")
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, int):
            self._edit_product(data)

    def _edit_product(self, product_id):
        session = self.db_manager.Session()
        try:
            p = session.query(Product).get(product_id)
            if not p:
                return
            prod_data = {
                'id': p.id,
                'designation': p.designation,
                'name': p.name,
                'material_id': p.material_id,
                'mass': p.mass,
                'dimensions': p.dimensions,
                'blank_type': p.blank_type,
                'accuracy_class': p.accuracy_class,
                'roughness': p.roughness,
                'quantity_in_assembly': p.quantity_in_assembly,
                'description': p.description,
            }
        finally:
            session.close()

        from ui.dialogs.product_dialog import ProductDialog
        dlg = ProductDialog(self.db_manager, product_data=prod_data, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            data = dlg.get_data()
            try:
                with self.db_manager.get_session() as session:
                    p = session.query(Product).get(product_id)
                    if p:
                        p.designation = data['designation']
                        p.name = data['name']
                        p.material_id = data.get('material_id')
                        p.mass = data.get('mass')
                        p.dimensions = data.get('dimensions')
                        p.blank_type = data.get('blank_type')
                        p.accuracy_class = data.get('accuracy_class')
                        p.roughness = data.get('roughness')
                        p.quantity_in_assembly = data.get('quantity_in_assembly', 1)
                        p.description = data.get('description')
                self.load_navigation_data()
                self._log_message(f"Изделие «{data['designation']}» обновлено")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить:\n{e}")

    def _delete_selected_product(self):
        item = self.products_tree.currentItem()
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, int):
            self._delete_product(data)

    def _delete_product(self, product_id):
        session = self.db_manager.Session()
        try:
            p = session.query(Product).get(product_id)
            if not p:
                return
            designation = p.designation
            tp_count = len(p.tech_processes)
        finally:
            session.close()

        # v8: переносим в Корзину (soft delete) вместо физического удаления.
        msg = (
            f"Перенести изделие «{designation}» в Корзину?\n"
            f"Его можно восстановить из Корзины (Ctrl+B) в течение 30 дней."
        )
        if tp_count > 0:
            msg += (
                f"\n\nВсе {tp_count} ТП этого изделия также будут "
                f"помечены удалёнными."
            )

        reply = QMessageBox.question(self, "Удаление", msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from datetime import datetime as _dt
                uid = (self.user or {}).get('id')
                with self.db_manager.get_session() as session:
                    p = session.query(Product).get(product_id)
                    if not p:
                        return
                    p.is_deleted = True
                    p.deleted_at = _dt.now()
                    p.deleted_by = uid
                    # Каскадно «помечаем» все ТП этого изделия.
                    for tp in (p.tech_processes or []):
                        if not tp.is_deleted:
                            tp.is_deleted = True
                            tp.deleted_at = _dt.now()
                            tp.deleted_by = uid
                self.load_navigation_data()
                self._log_message(
                    f"Изделие «{designation}» перенесено в Корзину"
                )
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{e}")

    # ──────────────────────────────────────────────────────────────
    # Управление ТП
    # ──────────────────────────────────────────────────────────────
    def _new_tech_process(self, product_id=None):
        from ui.dialogs.tp_dialog import TPDialog
        dlg = TPDialog(self.db_manager, product_id=product_id, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            data = dlg.get_data()
            try:
                new_tp_id = None
                is_variant = False
                with self.db_manager.get_session() as session:
                    from database.models import TPStatus
                    tp = TechProcess(
                        number=data['number'],
                        product_id=data['product_id'],
                        tp_type=data.get('tp_type'),
                        technology_type=data.get('technology_type'),
                        version=data.get('version', '1.0'),
                        execution_variant=data.get('execution_variant'),
                        description=data.get('description'),
                        status=TPStatus.DRAFT,
                        author_id=self.user.get('id'),
                    )
                    session.add(tp)
                    session.flush()
                    new_tp_id = tp.id
                    # Считается вариантом если у изделия уже есть другие ТП
                    sib_count = (session.query(TechProcess)
                                 .filter(TechProcess.product_id == data['product_id'],
                                         TechProcess.id != new_tp_id)
                                 .count())
                    is_variant = sib_count > 0

                self.load_navigation_data()
                self._log_message(f"ТП «{data['number']}» создан")
                # Регистрация в журнале (вариант → подтверждение)
                prompt = (
                    f'Создан новый технологический процесс «{data["number"]}».\n\n'
                    + ('У этого изделия уже есть зарегистрированный ТП. '
                       'Хотите зарегистрировать новый вариант отдельной строкой?'
                       if is_variant else
                       'Зарегистрировать ТП в едином журнале ТП/МТП?')
                )
                self._register_in_journal(
                    'tp', new_tp_id, is_variant=is_variant,
                    title=('Регистрация варианта ТП' if is_variant
                           else 'Регистрация ТП в журнале'),
                    prompt=prompt,
                    register_default=not is_variant,
                    suggested_tp_number=data.get('number'),
                )
                self._open_tp_editor(new_tp_id)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать ТП:\n{e}")

    def _delete_tp(self, tp_id):
        session = self.db_manager.Session()
        try:
            tp = session.query(TechProcess).get(tp_id)
            if not tp:
                return
            number = tp.number
        finally:
            session.close()

        reply = QMessageBox.question(
            self, "Удаление ТП",
            f"Перенести ТП «{number}» в корзину?\n"
            f"(Можно восстановить через «Сервис → Корзина»)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from datetime import datetime
                # Закрываем вкладку если открыта
                if tp_id in self._open_tp_tabs:
                    self._close_tab(self._open_tp_tabs[tp_id])
                with self.db_manager.get_session() as session:
                    tp = session.query(TechProcess).get(tp_id)
                    if tp:
                        tp.is_deleted = True
                        tp.deleted_at = datetime.now()
                        if self.user and self.user.get('id'):
                            tp.deleted_by = self.user['id']
                # audit log
                try:
                    from modules import audit
                    audit.log_change(self.db_manager,
                                     entity_type='TechProcess',
                                     entity_id=tp_id,
                                     user_id=(self.user or {}).get('id'),
                                     action='soft_delete',
                                     description=f'ТП «{number}» перемещён в корзину')
                except Exception:
                    pass
                self.load_navigation_data()
                self._log_message(f"ТП «{number}» перемещён в корзину")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{e}")

    def _copy_tp(self, tp_id):
        from modules.tp_designer import TPDesigner
        session = self.db_manager.Session()
        try:
            tp = session.query(TechProcess).get(tp_id)
            if not tp:
                return
            original_number = tp.number
            new_number = f"{original_number}-копия"

            from PyQt6.QtWidgets import QInputDialog
            new_number, ok = QInputDialog.getText(
                self, "Копирование ТП",
                f"Номер для копии ТП «{original_number}»:",
                text=new_number
            )
            if not ok or not new_number.strip():
                return

            # Запрашиваем вариант исполнения для копии — это и есть способ
            # создать «вариант ТП» под одну деталь.
            variant_default = getattr(tp, 'execution_variant', '') or ''
            new_variant, ok2 = QInputDialog.getText(
                self, "Вариант исполнения",
                "Вариант исполнения для копии (можно оставить пустым):",
                text=variant_default
            )
            if not ok2:
                return
            new_variant = new_variant.strip() or None

            designer = TPDesigner(session)
            new_tp = designer.copy_tech_process(
                source_tp_id=tp_id,
                new_number=new_number.strip(),
                author_id=self.user.get('id'),
                new_execution_variant=new_variant
            )
            new_tp_id = new_tp.id
        finally:
            session.close()

        self.load_navigation_data()
        self._log_message(f"ТП скопирован как «{new_number}»")
        # Регистрация в журнале (вариант → диалог подтверждения)
        self._register_in_journal(
            'tp', new_tp_id, is_variant=True,
            title='Регистрация варианта ТП',
            prompt=(
                f'Создана копия ТП «{original_number}» как «{new_number}»'
                + (f' (вариант исполнения «{new_variant}»).' if new_variant else '.')
                + '\n\nЗарегистрировать новый вариант в журнале отдельной строкой?'
            ),
            register_default=False,
            suggested_tp_number=new_number.strip(),
        )
        self._open_tp_editor(new_tp_id)

    # ──────────────────────────────────────────────────────────────
    # Меню
    # ──────────────────────────────────────────────────────────────
    def _create_menu(self):
        menubar = self.menuBar()

        # Файл
        file_menu = menubar.addMenu("Файл")

        act = QAction("Новое изделие", self)
        act.setShortcut(QKeySequence("Ctrl+Shift+N"))
        act.triggered.connect(self._new_product)
        file_menu.addAction(act)

        act = QAction("Новый ТП", self)
        act.setShortcut(QKeySequence.StandardKey.New)
        act.triggered.connect(self._new_tech_process)
        file_menu.addAction(act)

        act = QAction("Импорт из CAD-файла (STEP/CDW)...", self)
        act.triggered.connect(self._open_cad_import)
        file_menu.addAction(act)

        file_menu.addSeparator()

        # D18: «Недавно открытые» / «Избранное»
        self._recent_menu = file_menu.addMenu("🕘 Недавно открытые")
        self._recent_menu.aboutToShow.connect(self._refresh_recent_menu)
        self._favorites_menu = file_menu.addMenu("⭐ Избранное")
        self._favorites_menu.aboutToShow.connect(self._refresh_favorites_menu)

        file_menu.addSeparator()

        export_menu = file_menu.addMenu("Экспорт (активный ТП)")
        for fmt, label in [('xlsx', 'В Excel (.xlsx)'), ('docx', 'В Word (.docx)'), ('pdf', 'В PDF')]:
            a = QAction(label, self)
            a.triggered.connect(lambda checked, f=fmt: self._export_current_tp(f))
            export_menu.addAction(a)

        file_menu.addSeparator()
        exit_act = QAction("Выход", self)
        exit_act.setShortcut(QKeySequence.StandardKey.Quit)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # Справочники
        ref_menu = menubar.addMenu("Справочники")
        act = QAction("Материалы, оборудование, инструмент, профессии", self)
        act.triggered.connect(self._open_references)
        ref_menu.addAction(act)

        # Документы
        doc_menu = menubar.addMenu("Документы")
        act = QAction("Генерировать документы для активного ТП...", self)
        act.triggered.connect(self._open_doc_dialog)
        doc_menu.addAction(act)

        doc_menu.addSeparator()
        act = QAction("Библиотека шаблонов КТД (ГОСТ 3.1xxx)...", self)
        act.triggered.connect(self._open_ktd_browser)
        doc_menu.addAction(act)

        # Производство
        prod_menu = menubar.addMenu("Производство")
        act = QAction("📋 Панель «Производство»...", self)
        act.setShortcut("Ctrl+Shift+P")
        act.triggered.connect(self._open_production_panel)
        prod_menu.addAction(act)

        prod_menu.addSeparator()

        if (self.user.get('role') in ('admin', 'technologist')):
            act = QAction("Передать активный ТП в производство...", self)
            act.triggered.connect(self._release_active_tp)
            prod_menu.addAction(act)

        prod_menu.addSeparator()
        act = QAction("🏭 Справочник участков...", self)
        act.triggered.connect(self._open_workshops_dialog)
        prod_menu.addAction(act)

        act = QAction("📊 Отчёты производства...", self)
        act.triggered.connect(self._open_production_reports)
        prod_menu.addAction(act)

        prod_menu.addSeparator()

        # ── v9 Средний горизонт ──
        act = QAction("📊 Дашборд руководителя…", self)
        act.triggered.connect(self._open_manager_dashboard)
        prod_menu.addAction(act)

        act = QAction("📅 Gantt-планировщик…", self)
        act.triggered.connect(self._open_gantt)
        prod_menu.addAction(act)

        act = QAction("⚙ Загрузка оборудования…", self)
        act.triggered.connect(self._open_equipment_load)
        prod_menu.addAction(act)

        act = QAction("🔍 Терминал ОТК…", self)
        act.triggered.connect(self._open_qa_terminal)
        prod_menu.addAction(act)

        act = QAction("❌ Брак-журнал…", self)
        act.triggered.connect(self._open_scrap_journal)
        prod_menu.addAction(act)

        act = QAction("🧰 Учёт оснастки…", self)
        act.triggered.connect(self._open_tooling)
        prod_menu.addAction(act)

        act = QAction("📦 Учёт материала (партии)…", self)
        act.triggered.connect(self._open_materials)
        prod_menu.addAction(act)

        act = QAction("📐 Метрологическая поверка…", self)
        act.triggered.connect(self._open_metrology)
        prod_menu.addAction(act)

        act = QAction("✉ Извещения об изменениях (ECN)…", self)
        act.triggered.connect(self._open_ecn)
        prod_menu.addAction(act)

        prod_menu.addSeparator()
        act = QAction("📦 Редактор состава изделия (BOM)…", self)
        act.triggered.connect(self._open_bom_editor)
        prod_menu.addAction(act)

        act = QAction("📡 IoT-мониторинг станков…", self)
        act.triggered.connect(self._open_iot_dashboard)
        prod_menu.addAction(act)

        act = QAction("📐 Раскрой листового металла…", self)
        act.triggered.connect(self._open_nesting)
        prod_menu.addAction(act)

        act = QAction("🕜 Хронометраж (анализ план/факт)…", self)
        act.triggered.connect(self._open_chronometry)
        prod_menu.addAction(act)

        act = QAction("🔷 Графическое дерево БОМ…", self)
        act.triggered.connect(self._open_bom_graph)
        prod_menu.addAction(act)

        # Сервис
        srv_menu = menubar.addMenu("Сервис")
        if self.user.get('role') == 'admin':
            act = QAction("Управление пользователями...", self)
            act.triggered.connect(self._open_users_dialog)
            srv_menu.addAction(act)

        act = QAction("Обновить навигацию", self)
        act.setShortcut(QKeySequence.StandardKey.Refresh)
        act.triggered.connect(self.load_navigation_data)
        srv_menu.addAction(act)

        srv_menu.addSeparator()
        act = QAction("Дашборд полноты данных...", self)
        act.triggered.connect(self._open_completeness_dashboard)
        srv_menu.addAction(act)

        act = QAction("Журнал изменений (audit log)...", self)
        act.triggered.connect(self._open_audit_log)
        srv_menu.addAction(act)

        act = QAction("🗑 Корзина...", self)
        act.triggered.connect(self._open_recycle_bin)
        srv_menu.addAction(act)

        act = QAction("Глобальный поиск...", self)
        act.setShortcut("Ctrl+Shift+F")
        act.triggered.connect(self._open_global_search)
        srv_menu.addAction(act)

        srv_menu.addSeparator()
        act = QAction("📒 Журнал регистрации ТП/МТП...", self)
        act.triggered.connect(self._open_registration_journal)
        srv_menu.addAction(act)

        act = QAction("📊 Аналитические отчёты...", self)
        act.triggered.connect(self._open_analytics)
        srv_menu.addAction(act)

        act = QAction("📚 Библиотека типовых операций...", self)
        act.triggered.connect(self._open_op_templates)
        srv_menu.addAction(act)

        # v8: Библиотека типовых переходов
        act = QAction("📋 Шаблоны переходов...", self)
        act.triggered.connect(self._open_transition_templates)
        srv_menu.addAction(act)

        act = QAction("📥 Импорт справочников из Excel...", self)
        act.triggered.connect(self._open_excel_import)
        srv_menu.addAction(act)

        srv_menu.addSeparator()
        act = QAction("💾 Резервная копия БД сейчас", self)
        act.triggered.connect(self._make_backup_now)
        srv_menu.addAction(act)

        act = QAction("Восстановить из резервной копии...", self)
        act.triggered.connect(self._restore_backup_dialog)
        srv_menu.addAction(act)

        act = QAction("Информация о резервных копиях...", self)
        act.triggered.connect(self._show_backup_info)
        srv_menu.addAction(act)

        srv_menu.addSeparator()

        # 1C Integration submenu
        onec_menu = QMenu("Интеграция с 1С", self)
        act = QAction("Импорт из 1С (XML/JSON)...", self)
        act.triggered.connect(self._open_1c_import)
        onec_menu.addAction(act)
        act = QAction("Экспорт спецификации (xlsx)...", self)
        act.triggered.connect(self._export_specification_1c)
        onec_menu.addAction(act)
        act = QAction("Экспорт себестоимости в 1С (XML)...", self)
        act.triggered.connect(self._export_cost_1c)
        onec_menu.addAction(act)
        act = QAction("Экспорт графика в 1С (XML)...", self)
        act.triggered.connect(self._export_timeline_1c)
        onec_menu.addAction(act)
        srv_menu.addMenu(onec_menu)

        act = QAction("🧠 AI-помощник технолога...", self)
        act.triggered.connect(self._open_ai_assistant)
        srv_menu.addAction(act)

        act = QAction("🔧 Калькулятор режимов резания...", self)
        act.triggered.connect(self._open_cutting_calc)
        srv_menu.addAction(act)

        act = QAction("📐 Таблицы УНВ (укрупнённые нормы)...", self)
        act.triggered.connect(self._open_unv_tables)
        srv_menu.addAction(act)

        srv_menu.addSeparator()
        act = QAction("📋 Комплект документов (МК+ОК+ВМ)...", self)
        act.triggered.connect(self._generate_doc_pack)
        srv_menu.addAction(act)

        act = QAction("Настройки внешнего вида...", self)
        act.triggered.connect(self._open_appearance_settings)
        srv_menu.addAction(act)

        srv_menu.addSeparator()
        act = QAction("🔔 Уведомления...", self)
        act.setShortcut("Ctrl+Shift+N")
        act.triggered.connect(self._open_notifications)
        srv_menu.addAction(act)

        act = QAction("👤 Сменить пароль...", self)
        act.triggered.connect(self._open_change_password_self)
        srv_menu.addAction(act)

        srv_menu.addSeparator()
        act = QAction("Панель сообщений", self)
        act.setCheckable(True)
        act.triggered.connect(lambda c: self._messages_dock.show() if c else self._messages_dock.hide())
        srv_menu.addAction(act)

        # Справка
        help_menu = menubar.addMenu("Справка")
        act = QAction("О программе", self)
        act.triggered.connect(self._show_about)
        help_menu.addAction(act)

    # ──────────────────────────────────────────────────────────────
    # Панель инструментов
    # ──────────────────────────────────────────────────────────────
    def _create_toolbar(self):
        tb = QToolBar("Основная")
        tb.setIconSize(QSize(18, 18))
        tb.setMovable(False)
        tb.setStyleSheet("QToolBar { spacing: 4px; padding: 2px; }")
        self.addToolBar(tb)

        # Branding removed from toolbar to avoid layout issues

        def add_btn(text, slot, tooltip='', color=None):
            btn = QPushButton(text)
            btn.setFixedHeight(28)
            btn.clicked.connect(slot)
            if tooltip:
                btn.setToolTip(tooltip)
            if color:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {color}; color: white; "
                    f"border: none; padding: 2px 10px; border-radius: 3px; }}"
                    f"QPushButton:hover {{ opacity: 0.8; }}"
                )
            tb.addWidget(btn)
            return btn

        add_btn("Новое изделие", self._new_product, color='#27ae60')
        add_btn("Новый ТП", self._new_tech_process, color='#8e44ad')
        tb.addSeparator()
        add_btn("Справочники", self._open_references, color='#2980b9')
        add_btn("Документы", self._open_doc_dialog, color='#e67e22')
        add_btn("Шаблоны КТД", self._open_ktd_browser, color='#8e44ad')
        tb.addSeparator()
        add_btn("↺ Обновить", self.load_navigation_data, color='#7f8c8d')

        if self.user.get('role') == 'admin':
            tb.addSeparator()
            add_btn("Пользователи", self._open_users_dialog, color='#e74c3c')

        # v8: правый блок — быстрый поиск и переключатели вида.
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        tb.addWidget(spacer)

        search_btn = QPushButton('🔎  Ctrl+P')
        search_btn.setFixedHeight(28)
        search_btn.setToolTip('Глобальный поиск (Ctrl+P)')
        search_btn.setStyleSheet(
            "QPushButton { background-color: #34495e; color: white; "
            "border: none; padding: 2px 12px; border-radius: 3px; } "
            "QPushButton:hover { background-color: #2c3e50; }"
        )
        search_btn.clicked.connect(self._open_quick_search)
        tb.addWidget(search_btn)

        from modules import settings as _us
        cur_theme = _us.get('theme', 'light')
        self._theme_btn = QPushButton('🌙' if cur_theme == 'light' else '☀')
        self._theme_btn.setFixedSize(34, 28)
        self._theme_btn.setToolTip(
            f'Тема: {"светлая" if cur_theme == "light" else "тёмная"}. '
            f'Кликните, чтобы переключить.'
        )
        self._theme_btn.clicked.connect(self._toggle_theme)
        tb.addWidget(self._theme_btn)

        cur_font = int(_us.get('font_size', 9) or 9)
        self._font_btn = QPushButton(f'A{cur_font}')
        self._font_btn.setFixedSize(40, 28)
        self._font_btn.setToolTip(
            f'Размер шрифта: {cur_font} pt. Кликните, чтобы увеличить.'
        )
        self._font_btn.clicked.connect(self._cycle_font_size)
        tb.addWidget(self._font_btn)

    # ──────────────────────────────────────────────────────────────
    # Строка состояния
    # ──────────────────────────────────────────────────────────────
    def _install_hotkeys(self):
        """Глобальные хоткеи."""
        from PyQt6.QtGui import QShortcut, QKeySequence

        def add(seq: str, slot):
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(slot)
            return sc

        add('Ctrl+N', self._new_tech_process)
        add('Ctrl+F', self._focus_search)
        add('Ctrl+Shift+F', self._open_global_search)
        # v8: Ctrl+P — быстрая модалка поиска (как в VSCode / 1С).
        add('Ctrl+P', self._open_quick_search)
        # v7.4: F3 — «Где сейчас деталь?» (поиск активных нарядов).
        add('F3', self._open_where_is_part)
        add('Ctrl+W', self._close_current_tab)
        add('F5', self.load_navigation_data)
        add('Ctrl+B', self._open_recycle_bin)
        add('Ctrl+E', self._open_analytics)
        add('Ctrl+Shift+B', self._make_backup_now)

    def _focus_search(self):
        try:
            self._search_edit.setFocus()
            self._search_edit.selectAll()
        except Exception:
            pass

    def _open_where_is_part(self):
        """v7.4: F3 «Где сейчас деталь?»"""
        try:
            from ui.widgets.where_is_part import WhereIsPartDialog
            dlg = WhereIsPartDialog(self.db_manager, self.user, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"{e}")

    def _open_route_for_wo(self, work_order_id: int):
        """v7.2/7.3: открыть окно операционного маршрута для наряда."""
        try:
            from ui.widgets.route_window import RouteWindow
            dlg = RouteWindow(self.db_manager, work_order_id, self.user, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"{e}")

    def _open_route_by_barcode(self, code: str):
        """v7.3: открыть маршрут по сканированному штрих-коду."""
        from database.models import WorkOrder, WorkOrderItem
        s = self.db_manager.Session()
        try:
            wo = s.query(WorkOrder).filter(
                (WorkOrder.barcode == code) | (WorkOrder.number == code)
            ).first()
            if wo is None:
                # может быть штрих-код партии — найдём её WO
                it = s.query(WorkOrderItem).filter_by(barcode=code).first()
                if it:
                    wo = it.work_order
            if wo is None:
                QMessageBox.information(
                    self, "Сканер штрих-кода",
                    f"Наряд с кодом «{code}» не найден.")
                return
            wo_id = wo.id
        finally:
            s.close()
        self._open_route_for_wo(wo_id)

    def _save_splitter_state(self, *_):
        """v7.7h: сохранить положение разделителя в QSettings."""
        try:
            settings = QSettings(
                'ATPP', f"main_window_{self.user.get('username','default')}")
            settings.setValue('splitter_state', self._main_splitter.saveState())
        except Exception:
            pass

    def _close_current_tab(self):
        idx = self.work_area.currentIndex()
        if idx >= 0:
            self._close_tab(idx)

    def _create_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._status_label = QLabel("Готово")
        sb.addWidget(self._status_label)

        # Индикатор подключения к БД (postgres@host или SQLite)
        try:
            from config import DATABASE_URL as _DB_URL
            if _DB_URL.lower().startswith('sqlite'):
                db_text = 'БД: SQLite (локальная)'
                db_color = '#7f8c8d'
            elif _DB_URL.lower().startswith(('postgresql', 'postgres')):
                from urllib.parse import urlparse
                _u = _DB_URL
                if _u.startswith('postgresql+'):
                    _u = 'postgresql://' + _u.split('://', 1)[1]
                _p = urlparse(_u)
                _host = _p.hostname or '?'
                _db = (_p.path or '/').lstrip('/') or '?'
                db_text = f'БД: postgres @ {_host}/{_db}'
                db_color = '#16a085'
            else:
                db_text = 'БД: ?'
                db_color = '#c0392b'
        except Exception:
            db_text = 'БД: ?'
            db_color = '#c0392b'
        db_lbl = QLabel(f"  {db_text}  ")
        db_lbl.setStyleSheet(f"color: {db_color}; font-weight: bold;")
        sb.addPermanentWidget(db_lbl)

        sb.addPermanentWidget(QLabel(" | "))

        role_labels = {
            'admin': 'Администратор',
            'technologist': 'Технолог',
            'engineer': 'Инженер',
            'master': 'Мастер участка',
            'worker': 'Рабочий',
            'qc': 'Контролёр ОТК',
            'user': 'Пользователь',
        }
        role = role_labels.get(self.user.get('role', 'user'), self.user.get('role', ''))
        user_lbl = QLabel(
            f"  {self.user.get('full_name') or self.user.get('username')}  [{role}]  "
        )
        user_lbl.setStyleSheet("color: #2c3e50; font-weight: bold;")
        sb.addPermanentWidget(user_lbl)

        version_lbl = QLabel(f"  v{APP_VERSION}  ")
        version_lbl.setStyleSheet("color: #95a5a6;")
        sb.addPermanentWidget(version_lbl)

    # ──────────────────────────────────────────────────────────────
    # Нижняя панель сообщений
    # ──────────────────────────────────────────────────────────────
    def _make_messages_dock(self):
        dock = QDockWidget("Сообщения", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        dock.setMaximumHeight(150)

        self._messages_log = QTextEdit()
        self._messages_log.setReadOnly(True)
        self._messages_log.setStyleSheet("font-family: Consolas; font-size: 11px;")
        dock.setWidget(self._messages_log)
        return dock

    def _log_message(self, msg):
        from datetime import datetime
        ts = datetime.now().strftime('%H:%M:%S')
        self._messages_log.append(f"[{ts}]  {msg}")
        self._status_label.setText(msg)

    # ──────────────────────────────────────────────────────────────
    # Диалоги
    # ──────────────────────────────────────────────────────────────
    def _open_references(self):
        from ui.dialogs.references_dialog import ReferencesDialog
        dlg = ReferencesDialog(self.db_manager, parent=self)
        dlg.exec()

    def _open_users_dialog(self):
        from ui.dialogs.users_dialog import UsersDialog
        dlg = UsersDialog(self.db_manager, self.user, parent=self)
        dlg.exec()

    def _open_ktd_browser(self):
        from ui.dialogs.ktd_browser_dialog import KTDBrowserDialog
        dlg = KTDBrowserDialog(parent=self)
        dlg.exec()

    def _open_completeness_dashboard(self):
        # Не дублируем — переключаемся на уже открытый
        for i in range(self.work_area.count()):
            if self.work_area.tabText(i) == 'Полнота данных':
                self.work_area.setCurrentIndex(i)
                w = self.work_area.widget(i)
                if hasattr(w, 'refresh'):
                    w.refresh()
                return
        from ui.widgets.data_completeness import DataCompletenessWidget
        w = DataCompletenessWidget(self.db_manager, parent=self)
        idx = self.work_area.addTab(w, 'Полнота данных')
        self.work_area.setCurrentIndex(idx)

    def _open_audit_log(self):
        for i in range(self.work_area.count()):
            if self.work_area.tabText(i) == 'Журнал изменений':
                self.work_area.setCurrentIndex(i)
                w = self.work_area.widget(i)
                if hasattr(w, 'refresh'):
                    w.refresh()
                return
        from ui.widgets.audit_log_widget import AuditLogWidget
        w = AuditLogWidget(self.db_manager, parent=self)
        idx = self.work_area.addTab(w, 'Журнал изменений')
        self.work_area.setCurrentIndex(idx)

    def _open_appearance_settings(self):
        from ui.dialogs.appearance_dialog import AppearanceDialog
        dlg = AppearanceDialog(parent=self)
        dlg.exec()

    def _toggle_theme(self):
        """v8: быстрое переключение светлой/тёмной темы с кнопки в тулбаре."""
        from modules import settings as user_settings
        from ui.theme import apply_theme
        from PyQt6.QtWidgets import QApplication
        cur = user_settings.get('theme', 'light')
        new = 'dark' if cur == 'light' else 'light'
        user_settings.set('theme', new)
        app = QApplication.instance()
        if app is not None:
            apply_theme(
                app,
                theme=new,
                font_size=int(user_settings.get('font_size', 9) or 9),
            )
        # Обновляем подпись на кнопке.
        btn = getattr(self, '_theme_btn', None)
        if btn is not None:
            btn.setText('🌙' if new == 'light' else '☀')
            btn.setToolTip(
                f'Тема: {"светлая" if new == "light" else "тёмная"}. '
                f'Кликните, чтобы переключить.'
            )

    def _cycle_font_size(self):
        """v8: цикл размера шрифта 9 → 11 → 13 → 9 …  с кнопки в тулбаре."""
        from modules import settings as user_settings
        from ui.theme import apply_theme
        from PyQt6.QtWidgets import QApplication
        cur = int(user_settings.get('font_size', 9) or 9)
        sizes = [9, 11, 13, 15]
        try:
            idx = sizes.index(cur)
            new = sizes[(idx + 1) % len(sizes)]
        except ValueError:
            new = 11
        user_settings.set('font_size', new)
        app = QApplication.instance()
        if app is not None:
            apply_theme(
                app,
                theme=user_settings.get('theme', 'light'),
                font_size=new,
            )
        btn = getattr(self, '_font_btn', None)
        if btn is not None:
            btn.setText(f'A{new}')
            btn.setToolTip(
                f'Размер шрифта: {new} pt. Кликните, чтобы увеличить.'
            )

    # ──────────────────────────────────────────────────────────────
    # Версионирование / архивация / снимки ТП (пп. 10, 14)
    # ──────────────────────────────────────────────────────────────
    def _snapshot_tp(self, tp_id):
        from PyQt6.QtWidgets import QInputDialog
        comment, ok = QInputDialog.getText(
            self, "Снимок версии ТП",
            "Комментарий к снимку (что изменилось / зачем):",
            text=""
        )
        if not ok:
            return
        from modules.audit import snapshot_tp, log_change
        ver_id = snapshot_tp(
            self.db_manager,
            tp_id=tp_id,
            user_id=getattr(self.user, 'id', None),
            comment=(comment or '').strip(),
        )
        if ver_id is None:
            QMessageBox.warning(self, "Снимок версии",
                                "Не удалось создать снимок (см. лог в консоли).")
            return
        log_change(
            self.db_manager,
            user_id=getattr(self.user, 'id', None),
            action='snapshot',
            entity_type='TechProcess',
            entity_id=tp_id,
            description=f'Создан снимок версии #{ver_id}: {comment or ""}'.strip(),
        )
        self._log_message(f"Создан снимок версии ТП #{tp_id} (id={ver_id})")
        QMessageBox.information(self, "Снимок версии",
                                f"Снимок сохранён (версия #{ver_id}).")

    def _show_tp_history(self, tp_id):
        from modules.audit import list_versions, list_audit
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget,
                                     QTableWidget, QTableWidgetItem,
                                     QPushButton, QHBoxLayout, QPlainTextEdit,
                                     QSplitter)

        versions = list_versions(self.db_manager, tp_id=tp_id)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"История ТП #{tp_id}")
        dlg.resize(900, 600)
        lay = QVBoxLayout(dlg)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # Tab 1: snapshots
        snap_w = QWidget()
        snap_lay = QVBoxLayout(snap_w)
        splitter = QSplitter(Qt.Orientation.Vertical)
        snap_lay.addWidget(splitter)
        tbl = QTableWidget(len(versions), 4)
        tbl.setHorizontalHeaderLabels(["Версия", "Дата", "Автор", "Комментарий"])
        tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for i, v in enumerate(versions):
            tbl.setItem(i, 0, QTableWidgetItem(str(v.get('version_number') or '')))
            ts = v.get('created_at')
            tbl.setItem(i, 1, QTableWidgetItem(
                ts.strftime('%Y-%m-%d %H:%M') if ts else ''))
            tbl.setItem(i, 2, QTableWidgetItem(str(v.get('created_by') or '')))
            tbl.setItem(i, 3, QTableWidgetItem(v.get('comment') or ''))
        tbl.resizeColumnsToContents()
        splitter.addWidget(tbl)

        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setPlaceholderText("Выберите версию слева для просмотра JSON-снимка")
        splitter.addWidget(preview)
        splitter.setSizes([220, 320])

        def _on_select():
            r = tbl.currentRow()
            if 0 <= r < len(versions):
                preview.setPlainText(versions[r].get('data_snapshot') or '')
        tbl.itemSelectionChanged.connect(_on_select)

        tabs.addTab(snap_w, f"Снимки версий ({len(versions)})")

        # Tab 2: audit log for this TP
        audit_rows = [r for r in list_audit(self.db_manager, limit=2000)
                      if r.get('entity_type') == 'TechProcess' and r.get('entity_id') == tp_id]
        audit_w = QWidget()
        audit_lay = QVBoxLayout(audit_w)
        atbl = QTableWidget(len(audit_rows), 4)
        atbl.setHorizontalHeaderLabels(["Когда", "Кто", "Действие", "Описание"])
        atbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for i, r in enumerate(audit_rows):
            ts = r.get('timestamp')
            atbl.setItem(i, 0, QTableWidgetItem(ts.strftime('%Y-%m-%d %H:%M') if ts else ''))
            atbl.setItem(i, 1, QTableWidgetItem(r.get('user_name') or ''))
            atbl.setItem(i, 2, QTableWidgetItem(r.get('action') or ''))
            atbl.setItem(i, 3, QTableWidgetItem(r.get('description') or ''))
        atbl.resizeColumnsToContents()
        audit_lay.addWidget(atbl)
        tabs.addTab(audit_w, f"Журнал изменений ({len(audit_rows)})")

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        dlg.exec()

    def _archive_tp(self, tp_id):
        session = self.db_manager.Session()
        try:
            tp = session.query(TechProcess).get(tp_id)
            if not tp:
                return
            number = tp.number
            currently_archived = tp.status == TPStatus.ARCHIVED
        finally:
            session.close()

        action_name = "Восстановить из архива" if currently_archived else "Архивировать"
        reply = QMessageBox.question(
            self, action_name,
            f"{action_name} ТП «{number}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            with self.db_manager.get_session() as session:
                tp = session.query(TechProcess).get(tp_id)
                if not tp:
                    return
                tp.status = TPStatus.DRAFT if currently_archived else TPStatus.ARCHIVED
            from modules.audit import log_change
            log_change(
                self.db_manager,
                user_id=getattr(self.user, 'id', None),
                action='unarchive' if currently_archived else 'archive',
                entity_type='TechProcess',
                entity_id=tp_id,
                description=(f'ТП «{number}» восстановлен из архива'
                             if currently_archived
                             else f'ТП «{number}» отправлен в архив'),
            )
            self.load_navigation_data()
            self._log_message(
                f"ТП «{number}» {'восстановлен' if currently_archived else 'архивирован'}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось изменить статус:\n{e}")

    # ──────────────────────────────────────────────────────────────
    # Сервисные команды (корзина, бэкап, аналитика, поиск, шаблоны)
    # ──────────────────────────────────────────────────────────────
    def _open_recycle_bin(self):
        from ui.widgets.recycle_bin import RecycleBinWidget
        w = RecycleBinWidget(self.db_manager, self)
        w.changed.connect(self.load_navigation_data)
        self._add_or_focus_tab(w, 'Корзина')

    # ── v9: Средний горизонт ─────────────────────────────────────
    def _v9_user_id(self) -> int:
        return int(self.user.get('id') or 0)

    def _open_manager_dashboard(self):
        from ui.widgets.manager_dashboard_widget import ManagerDashboardWidget
        w = ManagerDashboardWidget(self.db_manager, parent=self)
        self._add_or_focus_tab(w, 'Дашборд руководителя')

    def _open_gantt(self):
        from ui.widgets.gantt_widget import GanttWidget
        w = GanttWidget(self.db_manager, parent=self)
        self._add_or_focus_tab(w, 'Gantt-планировщик')

    def _open_equipment_load(self):
        from ui.widgets.equipment_load_widget import EquipmentLoadWidget
        w = EquipmentLoadWidget(self.db_manager, parent=self)
        self._add_or_focus_tab(w, 'Загрузка оборудования')

    def _open_qa_terminal(self):
        from ui.widgets.qa_terminal_widget import QATerminalWidget
        w = QATerminalWidget(self.db_manager,
                             current_user_id=self._v9_user_id(),
                             parent=self)
        self._add_or_focus_tab(w, 'Терминал ОТК')

    def _open_scrap_journal(self):
        from ui.widgets.scrap_journal_widget import ScrapJournalWidget
        w = ScrapJournalWidget(self.db_manager,
                               current_user_id=self._v9_user_id(),
                               parent=self)
        self._add_or_focus_tab(w, 'Брак-журнал')

    def _open_tooling(self):
        from ui.widgets.tooling_widget import ToolingWidget
        w = ToolingWidget(self.db_manager,
                          current_user_id=self._v9_user_id(),
                          parent=self)
        self._add_or_focus_tab(w, 'Оснастка')

    def _open_materials(self):
        from ui.widgets.materials_widget import MaterialsWidget
        w = MaterialsWidget(self.db_manager,
                            current_user_id=self._v9_user_id(),
                            parent=self)
        self._add_or_focus_tab(w, 'Материал (партии)')

    def _open_metrology(self):
        from ui.widgets.metrology_widget import MetrologyWidget
        w = MetrologyWidget(self.db_manager,
                            current_user_id=self._v9_user_id(),
                            parent=self)
        self._add_or_focus_tab(w, 'Метрология')

    def _open_ecn(self):
        from ui.widgets.ecn_widget import ECNWidget
        w = ECNWidget(self.db_manager,
                      current_user_id=self._v9_user_id(),
                      parent=self)
        self._add_or_focus_tab(w, 'ECN')

    # ── v10: Новые фичи ───────────────────────────────────────────

    def _open_bom_editor(self):
        """Редактор многоуровневого состава изделия (BOM)."""
        from ui.widgets.bom_widget import BOMWidget
        # Ищем активное изделие в дереве навигации
        product_id = None
        from PyQt6.QtWidgets import QInputDialog
        # Простой выбор: спросить designation
        des, ok = QInputDialog.getText(
            self, 'BOM', 'Обозначение изделия (корень БОМ):')
        if not ok or not des.strip():
            return
        from database.models import Product
        with self.db_manager.get_session() as s:
            p = s.query(Product).filter(
                Product.designation == des.strip()).first()
            if p:
                product_id = p.id
            else:
                QMessageBox.warning(self, 'BOM',
                                    f'Изделие "{des}" не найдено.')
                return
        w = BOMWidget(self.db_manager, product_id, parent=self)
        self._add_or_focus_tab(w, f'BOM: {des.strip()}')

    def _open_iot_dashboard(self):
        from ui.widgets.iot_dashboard_widget import IoTDashboardWidget
        w = IoTDashboardWidget(self.db_manager,
                               current_user_id=self._v9_user_id(),
                               parent=self)
        self._add_or_focus_tab(w, 'IoT Мониторинг')

    def _open_1c_import(self):
        from ui.dialogs.onec_import_dialog import OneCImportDialog
        dlg = OneCImportDialog(self.db_manager, parent=self)
        dlg.exec()

    def _export_cost_1c(self):
        from modules.onec_exchange import export_cost_data
        from config import EXPORT_DIR
        try:
            with self.db_manager.get_session() as s:
                fp = export_cost_data(s,
                                      out_path=EXPORT_DIR / '1c_cost.xml')
            QMessageBox.information(self, 'Экспорт в 1С',
                                    f'Файл создан:\n{fp}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _export_timeline_1c(self):
        from modules.onec_exchange import export_timeline_data
        from config import EXPORT_DIR
        try:
            with self.db_manager.get_session() as s:
                fp = export_timeline_data(
                    s, out_path=EXPORT_DIR / '1c_timeline.xml')
            QMessageBox.information(self, 'Экспорт в 1С',
                                    f'Файл создан:\n{fp}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _open_ai_assistant(self):
        from ui.dialogs.ai_assistant_dialog import AIAssistantDialog
        dlg = AIAssistantDialog(self.db_manager, parent=self)
        dlg.exec()

    def _open_cad_import(self):
        from ui.dialogs.cad_import_dialog import CadImportDialog
        dlg = CadImportDialog(self.db_manager, parent=self)
        dlg.exec()

    def _open_cutting_calc(self):
        from ui.dialogs.cutting_calc_dialog import CuttingCalcDialog
        dlg = CuttingCalcDialog(parent=self)
        dlg.exec()

    def _open_unv_tables(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget
        from PyQt6.QtWidgets import QTableWidgetItem, QComboBox, QLabel
        from PyQt6.QtWidgets import QHBoxLayout, QDoubleSpinBox
        from modules.unv_tables import lookup_unv, list_categories

        dlg = QDialog(self)
        dlg.setWindowTitle('Таблицы УНВ')
        dlg.setMinimumSize(600, 400)
        lay = QVBoxLayout(dlg)

        sel = QHBoxLayout()
        sel.addWidget(QLabel('Категория:'))
        cat_cb = QComboBox()
        cats = list_categories()
        for cat_name, types in cats.items():
            cat_cb.addItem(cat_name, (cat_name, types))
        sel.addWidget(cat_cb)
        sel.addWidget(QLabel('Тип:'))
        type_cb = QComboBox()
        sel.addWidget(type_cb)

        def _on_cat():
            type_cb.clear()
            data = cat_cb.currentData()
            if data:
                for t in data[1]:
                    type_cb.addItem(t)
        cat_cb.currentIndexChanged.connect(_on_cat)
        _on_cat()
        sel.addWidget(QLabel('Масса:'))
        mass_sb = QDoubleSpinBox()
        mass_sb.setRange(0.01, 1000)
        mass_sb.setValue(5)
        mass_sb.setSuffix(' кг')
        sel.addWidget(mass_sb)
        sel.addWidget(QLabel('Габарит:'))
        dim_sb = QDoubleSpinBox()
        dim_sb.setRange(1, 5000)
        dim_sb.setValue(300)
        dim_sb.setSuffix(' мм')
        sel.addWidget(dim_sb)
        lay.addLayout(sel)

        tbl = QTableWidget(0, 4)
        tbl.setHorizontalHeaderLabels(['Тпз', 'Тшт', 'Интерпол.', 'Источник'])
        lay.addWidget(tbl)

        def _lookup():
            cat_key = list(CATEGORY_MAP.keys())[cat_cb.currentIndex()]\
                if cat_cb.currentIndex() >= 0 else 'turning'
            from modules.unv_tables import CATEGORY_MAP
            cat_key = list(CATEGORY_MAP.keys())[cat_cb.currentIndex()]\
                if 0 <= cat_cb.currentIndex() < len(CATEGORY_MAP)\
                else 'turning'
            r = lookup_unv(category=cat_key,
                           part_type=type_cb.currentText(),
                           mass_kg=mass_sb.value(),
                           dimension_mm=dim_sb.value())
            tbl.setRowCount(1)
            if r:
                tbl.setItem(0, 0, QTableWidgetItem(str(r.t_setup)))
                tbl.setItem(0, 1, QTableWidgetItem(str(r.t_piece)))
                tbl.setItem(0, 2, QTableWidgetItem(
                    'да' if r.interpolated else 'нет'))
                tbl.setItem(0, 3, QTableWidgetItem(
                    f'{r.part_type} ~{r.source_mass:.0f}кг'))

        mass_sb.valueChanged.connect(_lookup)
        dim_sb.valueChanged.connect(_lookup)
        type_cb.currentIndexChanged.connect(_lookup)
        _lookup()
        dlg.exec()

    def _generate_doc_pack(self):
        from PyQt6.QtWidgets import QInputDialog
        tp_num, ok = QInputDialog.getText(
            self, 'Комплект документов', 'Номер ТП:')
        if not ok or not tp_num.strip():
            return
        from database.models import TechProcess
        from modules.doc_generator import DocumentGenerator
        try:
            with self.db_manager.get_session() as s:
                tp = s.query(TechProcess).filter(
                    TechProcess.number == tp_num.strip()).first()
                if not tp:
                    QMessageBox.warning(self, 'Ошибка', 'ТП не найден.')
                    return
                gen = DocumentGenerator(s)
                files = gen.generate_document_pack(tp.id)
            QMessageBox.information(
                self, 'Готово',
                f'Создано файлов: {len(files)}\n' +
                '\n'.join(f'• {f.name}' for f in files))
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _open_nesting(self):
        from ui.widgets.nesting_widget import NestingWidget
        w = NestingWidget(self.db_manager, parent=self)
        self._add_or_focus_tab(w, 'Раскрой листа')

    def _open_chronometry(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget
        from PyQt6.QtWidgets import QTableWidgetItem, QLabel
        from modules.chronometry import chrono_summary

        dlg = QDialog(self)
        dlg.setWindowTitle('Хронометраж')
        dlg.setMinimumSize(700, 400)
        lay = QVBoxLayout(dlg)

        with self.db_manager.get_session() as s:
            summary = chrono_summary(s)

        lay.addWidget(QLabel(
            f'Замеров: {summary.total_measurements} | '
            f'Среднее отклонение: {summary.avg_deviation_pct:+.1f}% | '
            f'Быстрее: {summary.over_perform_count} | '
            f'Медленнее: {summary.under_perform_count}'))
        if summary.recommendations:
            lay.addWidget(QLabel(
                'Рекомендации:\n' + '\n'.join(
                    f'• {r}' for r in summary.recommendations)))

        tbl = QTableWidget(len(summary.most_deviated_ops), 5)
        tbl.setHorizontalHeaderLabels(
            ['Операция', 'План', 'Факт', 'Откл.', 'Наряд'])
        for i, r in enumerate(summary.most_deviated_ops):
            tbl.setItem(i, 0, QTableWidgetItem(r.operation_name))
            tbl.setItem(i, 1, QTableWidgetItem(
                f'{r.planned_t_piece:.1f}'))
            tbl.setItem(i, 2, QTableWidgetItem(
                f'{r.actual_minutes:.1f}' if r.actual_minutes else '—'))
            tbl.setItem(i, 3, QTableWidgetItem(
                f'{r.deviation_pct:+.0f}%' if r.deviation_pct is not None
                else '—'))
            tbl.setItem(i, 4, QTableWidgetItem(r.work_order_number))
        lay.addWidget(tbl)
        dlg.exec()

    def _open_bom_graph(self):
        from PyQt6.QtWidgets import QInputDialog
        des, ok = QInputDialog.getText(
            self, 'Графическое дерево БОМ', 'Обозначение изделия:')
        if not ok or not des.strip():
            return
        from database.models import Product
        with self.db_manager.get_session() as s:
            p = s.query(Product).filter(
                Product.designation == des.strip()).first()
            if not p:
                QMessageBox.warning(self, 'Ошибка', 'Изделие не найдено.')
                return
            pid = p.id
        from ui.widgets.bom_graph_widget import BOMGraphWidget
        w = BOMGraphWidget(self.db_manager, product_id=pid, parent=self)
        self._add_or_focus_tab(w, f'BOM-граф: {des.strip()}')

    def _open_global_search(self):
        from ui.widgets.global_search import GlobalSearchWidget
        w = GlobalSearchWidget(self.db_manager, self)
        try:
            w.tp_open.connect(self._open_tp_editor)
        except Exception:
            pass
        self._add_or_focus_tab(w, 'Поиск')

    def _open_quick_search(self):
        """v8: Ctrl+P — быстрый модальный поиск (поверх всего)."""
        from ui.dialogs.global_search_dialog import GlobalSearchDialog
        dlg = GlobalSearchDialog(self.db_manager, parent=self)
        try:
            dlg.tp_open.connect(self._open_tp_editor)
        except Exception:
            pass
        dlg.exec()

    def _open_analytics(self):
        from ui.widgets.analytics import AnalyticsWidget
        w = AnalyticsWidget(self.db_manager, self)
        self._add_or_focus_tab(w, 'Аналитика')

    def _open_registration_journal(self):
        from ui.widgets.journal_widget import JournalWidget
        w = JournalWidget(self.db_manager, self.user, self)
        try:
            w.open_tp.connect(self._open_tp_editor)
        except Exception:
            pass
        self._add_or_focus_tab(w, 'Журнал регистрации')

    def _register_in_journal(self, kind: str, entity_id: int,
                             *, is_variant: bool, title: str, prompt: str,
                             register_default: bool = True,
                             suggested_tp_number=None):
        """Открыть диалог регистрации и применить к выбранной сущности.

        kind ∈ {'product', 'tp'}
        """
        from ui.dialogs.journal_register_dialog import JournalRegisterDialog
        from modules import journal as journal_mod
        from database.models import Product, TechProcess

        defaults = {}
        if suggested_tp_number:
            defaults['tp_number'] = suggested_tp_number
            defaults['mtp_number'] = suggested_tp_number
        # Подставим имя пользователя
        defaults['executor'] = (self.user.get('full_name') or
                                self.user.get('username') or '')

        dlg = JournalRegisterDialog(
            self.db_manager, title, prompt,
            defaults=defaults, is_variant=is_variant,
            register_default=register_default, parent=self,
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            self._log_message('Регистрация в журнале пропущена.')
            return
        data = dlg.get_data()
        if data is None:
            return

        try:
            with self.db_manager.get_session() as s:
                if kind == 'product':
                    obj = s.query(Product).get(entity_id)
                    if obj is None:
                        return
                    entry = journal_mod.register_product(
                        s, obj, user_id=self.user.get('id'),
                        executor=data['executor'] or None,
                        product_type=data['product_type'] or None,
                        project=data['project'] or None,
                        notes=data['notes'] or None,
                        in_tp=data['in_tp'],
                        in_mtp=data['in_mtp'],
                        tp_number=data['tp_number'] or None,
                        mtp_number=data['mtp_number'] or None,
                        auto_number=False,
                    )
                else:
                    tp = s.query(TechProcess).get(entity_id)
                    if tp is None:
                        return
                    entry = journal_mod.register_tp(
                        s, tp, user_id=self.user.get('id'),
                        executor=data['executor'] or None,
                        product_type=data['product_type'] or None,
                        project=data['project'] or None,
                        notes=data['notes'] or None,
                        in_tp=data['in_tp'],
                        in_mtp=data['in_mtp'],
                        tp_number=data['tp_number'] or None,
                        mtp_number=data['mtp_number'] or None,
                        auto_number=False,
                    )
                if data['excluded']:
                    journal_mod.exclude_entry(
                        s, entry.id, self.user.get('id'),
                        'Помечено как исключённое при регистрации')
                # audit
                try:
                    from modules import audit
                    audit.log_change(
                        self.db_manager,
                        entity_type='RegistrationJournal',
                        entity_id=entry.id,
                        user_id=self.user.get('id'),
                        action='register',
                        description=(f'Регистрация {kind} #{entity_id}: '
                                     f'ТП={data["tp_number"]}, '
                                     f'МТП={data["mtp_number"]}'),
                    )
                except Exception:
                    pass
            self._log_message(
                f'Зарегистрировано в журнале: ТП {data["tp_number"]}, '
                f'МТП {data["mtp_number"]}'
            )
        except Exception as ex:
            QMessageBox.warning(
                self, 'Журнал',
                f'Не удалось зарегистрировать в журнале:\n{ex}\n\n'
                'Изделие/ТП всё равно создано. Можно добавить запись '
                'позже через Сервис → Журнал регистрации ТП/МТП.'
            )

    def _open_op_templates(self):
        from ui.dialogs.op_templates_dialog import OpTemplatesDialog
        dlg = OpTemplatesDialog(self.db_manager, parent=self)
        dlg.exec()

    def _open_transition_templates(self):
        """v8: Библиотека шаблонов переходов (Сервис → меню)."""
        from ui.dialogs.transition_templates_dialog import (
            TransitionTemplatesDialog,
        )
        dlg = TransitionTemplatesDialog(self.db_manager, parent=self)
        dlg.exec()

    def _open_excel_import(self):
        from ui.dialogs.excel_import_dialog import ExcelImportDialog
        dlg = ExcelImportDialog(self.db_manager, parent=self)
        dlg.exec()

    def _export_specification_1c(self):
        """Экспорт спецификации в формате xlsx для импорта в 1С."""
        from modules.pdm_integration import export_specification_xls
        try:
            with self.db_manager.get_session() as s:
                path = export_specification_xls(s)
        except Exception as e:
            QMessageBox.critical(self, 'Спецификация', f'Ошибка:\n{e}')
            return
        QMessageBox.information(
            self, 'Спецификация',
            f'Файл сохранён:\n{path}\n\n'
            f'Откройте его в 1С через "Загрузка из табличного документа".'
        )

    def _make_backup_now(self):
        from modules import backup as _backup
        path = _backup.make_backup(force=True)
        if path is None:
            QMessageBox.warning(
                self, 'Резервная копия',
                'Не удалось создать резервную копию.\n\n'
                'Для PostgreSQL убедитесь, что установлен pg_dump и доступ к серверу есть.\n'
                'Для SQLite — что файл БД существует.'
            )
            return
        mirror_dir = _backup._mirror_target()
        mirror_msg = f'\nЗеркало: {mirror_dir}' if mirror_dir else ''
        QMessageBox.information(
            self, 'Резервная копия',
            f'Резервная копия создана:\n{path}\n\n'
            f'Размер: {path.stat().st_size // 1024} КБ{mirror_msg}'
        )
        self._log_message(f'Backup: {path.name}')

    def _show_backup_info(self):
        from modules import backup as _backup
        backups, mirror = _backup.backup_summary()
        lines = []
        if backups:
            lines.append('Локальные резервные копии (data/backups):')
            # последние 10
            for p in backups[-10:]:
                size_kb = p.stat().st_size // 1024 if p.exists() else 0
                lines.append(f'  {p.name}  ({size_kb} КБ)')
            if len(backups) > 10:
                lines.insert(1, f'  …и ещё {len(backups) - 10} файл(ов) ранее')
        else:
            lines.append('Локальные резервные копии: пока нет.')
        lines.append('')
        if mirror:
            lines.append(f'Сетевое зеркало: {mirror}')
            try:
                if mirror.exists():
                    lines.append('  доступно (есть доступ на чтение).')
                else:
                    lines.append('  путь сейчас недоступен — копии будут '
                                 'отправлены при ближайшем удачном бэкапе.')
            except Exception:
                lines.append('  (статус доступности не определён)')
        else:
            lines.append('Сетевое зеркало не настроено '
                         '(переменная ATPP_BACKUP_MIRROR или data/backup.cfg).')
        QMessageBox.information(self, 'Резервные копии', '\n'.join(lines))

    def _restore_backup_dialog(self):
        from PyQt6.QtWidgets import QFileDialog
        from modules import backup as _backup
        if (self.user or {}).get('role') != 'admin':
            QMessageBox.warning(
                self, 'Восстановление',
                'Восстановление БД доступно только администратору.'
            )
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self, 'Выберите файл резервной копии',
            str(_backup.BACKUP_DIR),
            'Резервные копии (*.db.gz *.dump);;SQLite gzip (*.db.gz);;'
            'PostgreSQL custom (*.dump);;Все файлы (*)',
        )
        if not path_str:
            return
        if QMessageBox.question(
            self, 'Восстановить из резервной копии',
            'ВНИМАНИЕ! Восстановление заменит текущую БД на содержимое резервной копии.\n\n'
            'Текущая БД будет сохранена с суффиксом .bak_<timestamp>.\n'
            'После восстановления приложение нужно перезапустить.\n\n'
            'Продолжить?'
        ) != QMessageBox.StandardButton.Yes:
            return
        from pathlib import Path
        ok = _backup.restore_backup(Path(path_str))
        if ok:
            QMessageBox.information(
                self, 'Восстановление',
                'БД восстановлена. Закройте и снова откройте программу.'
            )
        else:
            QMessageBox.critical(self, 'Восстановление',
                                 'Не удалось восстановить БД.')

    def _add_or_focus_tab(self, widget, title: str):
        # Если уже открыта вкладка с таким заголовком — переключаемся
        for i in range(self.work_area.count()):
            if self.work_area.tabText(i) == title:
                self.work_area.setCurrentIndex(i)
                return
        idx = self.work_area.addTab(widget, title)
        self.work_area.setCurrentIndex(idx)

    def _open_doc_dialog(self):
        widget = self.work_area.currentWidget()
        if not hasattr(widget, 'tp_id'):
            QMessageBox.information(self, "Документы",
                                    "Откройте технологический процесс для генерации документов.\n"
                                    "Дважды кликните по ТП в дереве навигации.")
            return
        from ui.dialogs.doc_dialog import DocGenerateDialog
        tp_num = widget._tp.get('number', str(widget.tp_id))
        dlg = DocGenerateDialog(self.db_manager, widget.tp_id, tp_num, parent=self)
        dlg.exec()

    def _export_current_tp(self, fmt):
        widget = self.work_area.currentWidget()
        if not hasattr(widget, 'tp_id'):
            QMessageBox.information(self, "Экспорт", "Откройте ТП для экспорта")
            return
        from modules.doc_generator import DocumentGenerator
        session = self.db_manager.Session()
        try:
            gen = DocumentGenerator(session)
            path = gen.generate_route_card(widget.tp_id, fmt)
            QMessageBox.information(self, "Экспорт", f"Файл сохранён:\n{path}")
            self._log_message(f"Экспорт МК: {path.name}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта:\n{e}")
        finally:
            session.close()

    # ──────────────────────────────────────────────────────────────
    # Производство
    # ──────────────────────────────────────────────────────────────

    def _open_production_panel(self):
        from ui.widgets.production_widget import ProductionWidget
        w = ProductionWidget(self.db_manager, self.user, self)
        self._add_or_focus_tab(w, 'Производство')

    def _release_active_tp(self):
        """Передать активный (открытый в текущей вкладке) ТП в производство."""
        from ui.dialogs.production_dialogs import ReleaseDialog
        widget = self.work_area.currentWidget()
        tp_id = getattr(widget, 'tp_id', None)
        dlg = ReleaseDialog(self.db_manager, self.user, parent=self,
                            default_tp_id=tp_id)
        if dlg.exec():
            # Открываем панель производства
            self._open_production_panel()

    def _open_workshops_dialog(self):
        """Справочник производственных участков (CRUD + назначение мастера)."""
        from ui.dialogs.workshops_dialog import WorkshopsDialog
        dlg = WorkshopsDialog(self.db_manager, self.user, parent=self)
        dlg.exec()

    def _open_production_reports(self):
        """Отчёты производства: выработка, throughput, журнал смен, проблемы."""
        from ui.dialogs.production_reports_dialog import ProductionReportsDialog
        dlg = ProductionReportsDialog(self.db_manager, self.user, parent=self)
        dlg.exec()

    def _open_notifications(self):
        """Список уведомлений текущего пользователя (A6)."""
        from ui.dialogs.notifications_dialog import NotificationsDialog
        dlg = NotificationsDialog(self.db_manager, self.user, parent=self)
        dlg.exec()
        # Обновляем счётчик в строке состояния, если он есть.
        if hasattr(self, '_refresh_notifications_badge'):
            self._refresh_notifications_badge()

    def _open_change_password_self(self):
        """Смена своего пароля (D15/D16)."""
        from ui.dialogs.change_password_dialog import ChangePasswordDialog
        dlg = ChangePasswordDialog(self.db_manager, self.user, parent=self)
        dlg.exec()

    # ──────────────────────────────────────────────────────────────
    # D18: «Недавно открытые» / «Избранное»
    # ──────────────────────────────────────────────────────────────
    def _refresh_recent_menu(self):
        self._populate_bookmark_menu(self._recent_menu, favorites=False)

    def _refresh_favorites_menu(self):
        self._populate_bookmark_menu(self._favorites_menu, favorites=True)

    def _populate_bookmark_menu(self, menu, *, favorites: bool):
        from modules import bookmarks
        menu.clear()
        uid = self.user.get('id')
        if not uid:
            menu.addAction('— нет данных —').setEnabled(False)
            return
        try:
            with self.db_manager.get_session() as s:
                if favorites:
                    rows = bookmarks.list_favorites(s, user_id=uid, limit=50)
                else:
                    rows = bookmarks.list_recent(
                        s, user_id=uid, target_type='tech_process', limit=15)
                # (target_type, target_id, title)
                items = [(b.target_type, b.target_id, b.title or f'#{b.target_id}',
                          b.is_favorite) for b in rows]
        except Exception as e:
            menu.addAction(f'Ошибка: {e}').setEnabled(False)
            return
        if not items:
            menu.addAction('— пусто —').setEnabled(False)
            return
        for ttype, tid, title, is_fav in items:
            label = ('★ ' if is_fav else '') + title
            act = QAction(label, self)
            act.triggered.connect(
                lambda checked=False, t=ttype, i=tid: self._open_bookmark(t, i))
            menu.addAction(act)
        if not favorites:
            menu.addSeparator()
            act = QAction('★ Добавить активный ТП в избранное', self)
            act.triggered.connect(self._toggle_active_tp_favorite)
            menu.addAction(act)

    def _open_bookmark(self, target_type: str, target_id: int):
        if target_type == 'tech_process':
            self._open_tp_editor(int(target_id))
        # Другие типы — точки расширения.

    def _toggle_active_tp_favorite(self):
        """Переключает «избранное» для активного ТП."""
        idx = self.work_area.currentIndex()
        if idx < 0:
            return
        active_tp_id = None
        for tp_id, i in self._open_tp_tabs.items():
            if i == idx:
                active_tp_id = tp_id
                break
        if not active_tp_id:
            return
        from modules import bookmarks
        try:
            with self.db_manager.get_session() as s:
                new_state = bookmarks.toggle_favorite(
                    s, user_id=self.user.get('id'),
                    target_type='tech_process',
                    target_id=int(active_tp_id))
            self._log_message(
                f'★ ТП #{active_tp_id} '
                + ('добавлен в избранное' if new_state
                   else 'убран из избранного'))
        except Exception as e:
            print(f'[bookmarks] toggle failed: {e}')

    def _show_about(self):
        QMessageBox.about(
            self, "О программе",
            f"<h3>{APP_NAME}</h3>"
            f"<p><b>Версия:</b> {APP_VERSION}</p>"
            f"<p>Система автоматизации технологической подготовки производства</p>"
            f"<p>Аналог САПР ТП «ТехноПро» — внутренняя разработка</p>"
            f"<p><b>Компания:</b> УЗГА</p>"
            f"<p style='color:#95a5a6;'>© 2026 УЗГА. Все права защищены.</p>"
        )

    # ──────────────────────────────────────────────────────────────
    # Закрытие окна
    # ──────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, "Выход из АТПП",
            "Вы уверены, что хотите выйти из системы?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()
