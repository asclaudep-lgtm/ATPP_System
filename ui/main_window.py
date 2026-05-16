"""
Главное окно приложения АТПП — координатор виджетов.

Связывает MainMenu, MainToolBar, MainStatusBar, NavigationPanel и
DialogLaunchersMixin через Qt signals/slots.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QTabWidget,
    QTreeWidgetItem, QLabel, QPushButton, QTextEdit, QDockWidget,
    QMenu, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QAction, QKeySequence, QColor

from utils.logger import get_logger
_log = get_logger(__name__)

from config import APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT
from database.models import Product, TechProcess, TPStatus

from ui.widgets.main_menu import MainMenu
from ui.widgets.main_toolbar import MainToolBar
from ui.widgets.main_statusbar import MainStatusBar
from ui.widgets.navigation_panel import NavigationPanel
from ui.widgets.dialog_launchers import DialogLaunchersMixin


class MainWindow(DialogLaunchersMixin, QMainWindow):
    """Главное окно системы АТПП — композиция виджетов + сигналы."""

    def __init__(self, db_manager, user):
        _log.debug("Loading MainWindow from: %s", __file__)
        super().__init__()
        self.db_manager = db_manager
        self.user = user
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setWindowTitle(
            "УЗГА-Инжиниринг АТПП- Система автоматизации "
            "технологической подготовки производства")
        _log.debug("Window title: %s", self.windowTitle())
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self._open_tp_tabs = {}
        self._open_ktp_tabs = {}

        self._init_ui()
        self._connect_signals()
        self._install_hotkeys()
        self.nav_panel.load_data()

    # ═══════════════════════════════════════════════════════════════
    # UI Construction
    # ═══════════════════════════════════════════════════════════════

    def _init_ui(self):
        central = QWidget()
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Navigation panel (left)
        self.nav_panel = NavigationPanel(self.db_manager, user=self.user)
        splitter.addWidget(self.nav_panel)

        # Work area (center) — tabbed
        self.work_area = QTabWidget()
        self.work_area.setTabsClosable(True)
        self.work_area.setMovable(True)
        self.work_area.tabCloseRequested.connect(self._close_tab)
        splitter.addWidget(self.work_area)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([230, WINDOW_WIDTH - 230])
        splitter.setHandleWidth(2)
        self._main_splitter = splitter
        try:
            settings = QSettings(
                'ATPP', f"main_window_{self.user.get('username', 'default')}")
            state = settings.value('splitter_state')
            if state is not None:
                splitter.restoreState(state)
        except Exception:
            pass
        splitter.splitterMoved.connect(self._save_splitter_state)

        main_layout.addWidget(splitter)

        # Messages dock (bottom)
        self._messages_dock = self._make_messages_dock()
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self._messages_dock)
        self._messages_dock.hide()

    def _connect_signals(self):
        """Wire all widget signals to MainWindow slots."""
        nav = self.nav_panel

        # Navigation → MainWindow
        nav.product_double_clicked.connect(self._open_product_editor)
        nav.tp_double_clicked.connect(self._open_tp_editor)
        nav.product_edit_requested.connect(self._open_product_editor)
        nav.product_delete_requested.connect(self._delete_product)
        nav.new_product_requested.connect(self._new_product)
        nav.new_tp_requested.connect(
            lambda pid: self._new_tech_process(pid if pid else None))

        # Sidebar module buttons → menu actions
        nav.production_clicked.connect(self._open_production_panel)
        nav.qa_clicked.connect(self._open_qa_terminal)
        nav.tooling_clicked.connect(self._open_tooling)
        nav.orders_clicked.connect(lambda: self._open_production_panel())
        nav.pdo_clicked.connect(self._open_pdo_dispatcher)
        nav.dashboard_clicked.connect(self._open_manager_dashboard)
        nav.references_clicked.connect(self._open_references)
        nav.documents_clicked.connect(self._open_doc_dialog)
        nav.users_clicked.connect(self._open_users_dialog)
        nav.audit_clicked.connect(lambda: self._open_audit_log())
        nav.batch_clicked.connect(lambda: QMessageBox.information(
            self, "Batch-операции",
            "Используйте веб-интерфейс для batch-операций.\n"
            "Откройте http://localhost:8000 и перейдите на вкладку «⚡ Batch-операции»."))

        # Menu
        menu = MainMenu(self.user, self)
        self.setMenuBar(menu)
        self._menu = menu

        menu.act_new_product.triggered.connect(self._new_product)
        menu.act_new_tp.triggered.connect(self._new_tech_process)
        menu.act_cad_import.triggered.connect(self._open_cad_import)
        menu.act_export_xlsx.triggered.connect(lambda: self._export_current_tp('xlsx'))
        menu.act_export_docx.triggered.connect(lambda: self._export_current_tp('docx'))
        menu.act_export_pdf.triggered.connect(lambda: self._export_current_tp('pdf'))
        menu.act_exit.triggered.connect(self.close)
        menu.recent_menu_about_to_show.connect(self._refresh_recent_menu)
        menu.favorites_menu_about_to_show.connect(self._refresh_favorites_menu)

        menu.act_open_references.triggered.connect(self._open_references)
        if hasattr(menu, 'act_open_reference_editors'):
            menu.act_open_reference_editors.triggered.connect(
                self._open_reference_editors)
        menu.act_generate_docs.triggered.connect(self._open_doc_dialog)
        menu.act_ktd_browser.triggered.connect(self._open_ktd_browser)

        menu.act_production_panel.triggered.connect(self._open_production_panel)
        if hasattr(menu, 'act_release_tp'):
            menu.act_release_tp.triggered.connect(self._release_active_tp)
        menu.act_workshops.triggered.connect(self._open_workshops_dialog)
        menu.act_production_reports.triggered.connect(self._open_production_reports)

        menu.act_manager_dashboard.triggered.connect(self._open_manager_dashboard)
        menu.act_gantt.triggered.connect(self._open_gantt)
        menu.act_equipment_load.triggered.connect(self._open_equipment_load)
        menu.act_qa_terminal.triggered.connect(self._open_qa_terminal)
        menu.act_scrap_journal.triggered.connect(self._open_scrap_journal)
        menu.act_tooling.triggered.connect(self._open_tooling)
        menu.act_materials.triggered.connect(self._open_materials)
        menu.act_metrology.triggered.connect(self._open_metrology)
        menu.act_ecn.triggered.connect(self._open_ecn)
        menu.act_bom_editor.triggered.connect(self._open_bom_editor)
        menu.act_iot_dashboard.triggered.connect(self._open_iot_dashboard)
        menu.act_nesting.triggered.connect(self._open_nesting)
        menu.act_chronometry.triggered.connect(self._open_chronometry)
        menu.act_bom_graph.triggered.connect(self._open_bom_graph)

        if hasattr(menu, 'act_users'):
            menu.act_users.triggered.connect(self._open_users_dialog)
        menu.act_refresh.triggered.connect(self.nav_panel.load_data)
        menu.act_completeness.triggered.connect(self._open_completeness_dashboard)
        menu.act_audit_log.triggered.connect(self._open_audit_log)
        menu.act_recycle_bin.triggered.connect(self._open_recycle_bin)
        menu.act_global_search.triggered.connect(self._open_global_search)
        menu.act_journal.triggered.connect(self._open_registration_journal)
        menu.act_analytics.triggered.connect(self._open_analytics)
        if hasattr(menu, 'act_report_builder'):
            menu.act_report_builder.triggered.connect(self._open_report_builder)
        if hasattr(menu, 'act_formula_editor'):
            menu.act_formula_editor.triggered.connect(self._open_formula_editor)
        if hasattr(menu, 'act_shift_dashboard'):
            menu.act_shift_dashboard.triggered.connect(self._open_shift_dashboard)
        if hasattr(menu, 'act_pdo_dispatcher'):
            menu.act_pdo_dispatcher.triggered.connect(self._open_pdo_dispatcher)
        if hasattr(menu, 'act_pdo_analytics'):
            menu.act_pdo_analytics.triggered.connect(self._open_pdo_analytics)
        menu.act_op_templates.triggered.connect(self._open_op_templates)
        menu.act_transition_templates.triggered.connect(self._open_transition_templates)
        menu.act_excel_import.triggered.connect(self._open_excel_import)
        menu.act_backup_now.triggered.connect(self._make_backup_now)
        menu.act_restore_backup.triggered.connect(self._restore_backup_dialog)
        menu.act_backup_info.triggered.connect(self._show_backup_info)
        menu.act_1c_import.triggered.connect(self._open_1c_import)
        menu.act_export_spec_1c.triggered.connect(self._export_specification_1c)
        menu.act_export_cost_1c.triggered.connect(self._export_cost_1c)
        menu.act_export_timeline_1c.triggered.connect(self._export_timeline_1c)
        menu.act_ai_assistant.triggered.connect(self._open_ai_assistant)
        menu.act_cutting_calc.triggered.connect(self._open_cutting_calc)
        menu.act_unv_tables.triggered.connect(self._open_unv_tables)
        menu.act_doc_pack.triggered.connect(self._generate_doc_pack)
        if hasattr(menu, 'act_batch_print'):
            menu.act_batch_print.triggered.connect(self._open_batch_print)
        menu.act_appearance.triggered.connect(self._open_appearance_settings)
        menu.act_notifications.triggered.connect(self._open_notifications)
        menu.act_change_password.triggered.connect(self._open_change_password_self)
        menu.act_toggle_messages.triggered.connect(
            lambda checked: (self._messages_dock.show()
                             if checked else self._messages_dock.hide()))
        if hasattr(menu, 'act_hotkeys'):
            menu.act_hotkeys.triggered.connect(self._show_hotkeys)
        menu.act_about.triggered.connect(self._show_about)

        # Toolbar
        from modules import settings as _us
        cur_theme = _us.get('theme', 'light')
        self._toolbar = MainToolBar(self.user, cur_theme)
        self.addToolBar(self._toolbar)

        tb = self._toolbar
        tb.new_product.connect(self._new_product)
        tb.new_tp.connect(self._new_tech_process)
        tb.open_references.connect(self._open_references)
        tb.open_documents.connect(self._open_doc_dialog)
        tb.open_ktd_browser.connect(self._open_ktd_browser)
        tb.refresh.connect(self.nav_panel.load_data)
        if self.user.get('role') == 'admin':
            tb.open_users.connect(self._open_users_dialog)
        tb.open_global_search.connect(self._open_quick_search)
        if hasattr(tb, 'open_pdo_dispatcher'):
            tb.open_pdo_dispatcher.connect(self._open_pdo_dispatcher)
        tb.toggle_theme.connect(self._toggle_theme)

        # StatusBar
        self._statusbar = MainStatusBar(self.user)
        self.setStatusBar(self._statusbar)

        # Context menu for products tree
        self.nav_panel.products_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.nav_panel.products_tree.customContextMenuRequested.connect(
            self._product_context_menu)

    # ═══════════════════════════════════════════════════════════════
    # Messages dock
    # ═══════════════════════════════════════════════════════════════

    def _make_messages_dock(self):
        dock = QDockWidget("Сообщения", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        dock.setMaximumHeight(150)
        self._messages_log = QTextEdit()
        self._messages_log.setReadOnly(True)
        self._messages_log.setStyleSheet(
            "font-family: Consolas; font-size: 11px;")
        dock.setWidget(self._messages_log)
        return dock

    def _log_message(self, msg):
        from datetime import datetime
        ts = datetime.now().strftime('%H:%M:%S')
        self._messages_log.append(f"[{ts}]  {msg}")
        self._statusbar.set_message(msg)

    # ═══════════════════════════════════════════════════════════════
    # Tab management
    # ═══════════════════════════════════════════════════════════════

    def _open_product_ktp(self, product_id: int):
        """Legacy KTP widget — kept for backward compatibility."""
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

    def _open_product_editor(self, product_id: int):
        """v11: Open the new ProductEditorWidget for a product."""
        for i in range(self.work_area.count()):
            w = self.work_area.widget(i)
            if (hasattr(w, 'product_id') and w.product_id == product_id
                    and type(w).__name__ == 'ProductEditorWidget'):
                self.work_area.setCurrentIndex(i)
                return

        from ui.editors.product_editor import ProductEditorWidget
        editor = ProductEditorWidget(
            self.db_manager, product_id, self.user, self)
        editor.product_saved.connect(lambda pid: self.load_navigation_data())
        editor.tp_open_requested.connect(self._open_tp_editor)

        title = editor.get_tab_title()
        idx = self.work_area.addTab(editor, title)
        self.work_area.setCurrentIndex(idx)
        self._log_message(f"Открыт редактор: {title}")

    def _open_reference_editors(self):
        """v11: Open tabbed reference editors (materials, equipment, etc.)."""
        from ui.editors.reference_editor import ReferenceEditorWidget

        tabs = QTabWidget()
        for ref_type, cfg in [
            ('material', 'Материалы'),
            ('equipment', 'Оборудование'),
            ('tool', 'Инструмент'),
            ('profession', 'Профессии'),
        ]:
            editor = ReferenceEditorWidget(self.db_manager, ref_type)
            tabs.addTab(editor, cfg[1])
        self._add_or_focus_tab(tabs, 'Справочники')

    def _open_tp_editor(self, tp_id):
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
            _log.debug('track_open skipped: %s', e)

    def _on_tp_changed(self, tp_id):
        if tp_id in self._open_tp_tabs:
            idx = self._open_tp_tabs[tp_id]
            if idx < self.work_area.count():
                widget = self.work_area.widget(idx)
                if hasattr(widget, 'get_tab_title'):
                    self.work_area.setTabText(idx, widget.get_tab_title())
        self.nav_panel.load_data()

    def _close_tab(self, index):
        # Clean up TP tab tracking
        for tp_id, idx in list(self._open_tp_tabs.items()):
            if idx == index:
                del self._open_tp_tabs[tp_id]
                self._open_tp_tabs = {
                    tid: (i if i < index else i - 1)
                    for tid, i in self._open_tp_tabs.items()
                }
                break
        # Clean up KTP tab tracking
        for pid, idx in list(self._open_ktp_tabs.items()):
            if idx == index:
                del self._open_ktp_tabs[pid]
                self._open_ktp_tabs = {
                    p: (i if i < index else i - 1)
                    for p, i in self._open_ktp_tabs.items()
                }
                break
        self.work_area.removeTab(index)

    def _add_or_focus_tab(self, widget, title: str):
        for i in range(self.work_area.count()):
            if self.work_area.tabText(i) == title:
                self.work_area.setCurrentIndex(i)
                return
        idx = self.work_area.addTab(widget, title)
        self.work_area.setCurrentIndex(idx)

    # ═══════════════════════════════════════════════════════════════
    # Context menu (products tree)
    # ═══════════════════════════════════════════════════════════════

    def _product_context_menu(self, pos):
        item = self.nav_panel.products_tree.itemAt(pos)
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
                add_tp_act.triggered.connect(
                    lambda: self._new_tech_process(product_id=data))
                menu.addAction(add_tp_act)

                menu.addSeparator()
                del_act = QAction("Удалить изделие", self)
                del_act.triggered.connect(lambda: self._delete_product(data))
                menu.addAction(del_act)

            elif isinstance(data, tuple) and data[0] == 'tp':
                tp_id = data[1]
                open_act = QAction("Открыть ТП", self)
                open_act.triggered.connect(
                    lambda: self._open_tp_editor(tp_id))
                menu.addAction(open_act)

                menu.addSeparator()
                variant_act = QAction("Создать вариант исполнения ТП…", self)
                variant_act.triggered.connect(
                    lambda: self._copy_tp(tp_id))
                menu.addAction(variant_act)

                copy_act = QAction("Копировать ТП…", self)
                copy_act.triggered.connect(
                    lambda: self._copy_tp(tp_id))
                menu.addAction(copy_act)

                snap_act = QAction("Сохранить снимок версии…", self)
                snap_act.triggered.connect(
                    lambda: self._snapshot_tp(tp_id))
                menu.addAction(snap_act)

                hist_act = QAction("История версий…", self)
                hist_act.triggered.connect(
                    lambda: self._show_tp_history(tp_id))
                menu.addAction(hist_act)

                arch_act = QAction("Архивировать ТП", self)
                arch_act.triggered.connect(
                    lambda: self._archive_tp(tp_id))
                menu.addAction(arch_act)

                del_act = QAction("Удалить ТП", self)
                del_act.triggered.connect(lambda: self._delete_tp(tp_id))
                menu.addAction(del_act)

        menu.exec(self.nav_panel.products_tree.viewport().mapToGlobal(pos))

    # ═══════════════════════════════════════════════════════════════
    # Hotkeys
    # ═══════════════════════════════════════════════════════════════

    def _install_hotkeys(self):
        from PyQt6.QtGui import QShortcut, QKeySequence

        def add(seq, slot):
            QShortcut(QKeySequence(seq), self).activated.connect(slot)

        add('Ctrl+N', self._new_tech_process)
        add('Ctrl+F', self._focus_search)
        add('Ctrl+Shift+F', self._open_global_search)
        add('Ctrl+P', self._open_quick_search)
        add('F3', self._open_where_is_part)
        add('Ctrl+W', self._close_current_tab)
        add('F5', self.nav_panel.load_data)
        add('Ctrl+B', self._open_recycle_bin)
        add('Ctrl+E', self._open_analytics)
        add('Ctrl+Shift+B', self._make_backup_now)

    def _focus_search(self):
        try:
            self.nav_panel.focus_search()
        except Exception:
            pass

    def _close_current_tab(self):
        idx = self.work_area.currentIndex()
        if idx >= 0:
            self._close_tab(idx)

    def _open_where_is_part(self):
        try:
            from ui.widgets.where_is_part import WhereIsPartDialog
            dlg = WhereIsPartDialog(self.db_manager, self.user, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                f"Не удалось открыть окно поиска детали.\n\n{e}")

    def _open_route_for_wo(self, work_order_id: int):
        try:
            from ui.widgets.route_window import RouteWindow
            dlg = RouteWindow(self.db_manager, work_order_id, self.user, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                f"Не удалось открыть маршрутный лист.\n\n{e}")

    def _open_route_by_barcode(self, code: str):
        from database.models import WorkOrder, WorkOrderItem
        s = self.db_manager.Session()
        try:
            wo = s.query(WorkOrder).filter(
                (WorkOrder.barcode == code) | (WorkOrder.number == code)
            ).first()
            if wo is None:
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
        try:
            settings = QSettings(
                'ATPP', f"main_window_{self.user.get('username', 'default')}")
            settings.setValue('splitter_state', self._main_splitter.saveState())
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # Theme / Font
    # ═══════════════════════════════════════════════════════════════

    def _toggle_theme(self):
        from modules import settings as user_settings
        from ui.theme import apply_theme
        from PyQt6.QtWidgets import QApplication
        cur = user_settings.get('theme', 'light')
        new = 'dark' if cur == 'light' else 'light'
        user_settings.set('theme', new)
        app = QApplication.instance()
        if app is not None:
            apply_theme(
                app, theme=new,
                font_size=int(user_settings.get('font_size', 9) or 9),
            )
        if hasattr(self, '_toolbar'):
            self._toolbar.setStyleSheet("")
            self._toolbar.update_theme(new)

    # ═══════════════════════════════════════════════════════════════
    # Navigation data (delegates)
    # ═══════════════════════════════════════════════════════════════

    def load_navigation_data(self):
        self.nav_panel.load_data()

    # ═══════════════════════════════════════════════════════════════
    # About / Close
    # ═══════════════════════════════════════════════════════════════

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
