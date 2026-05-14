"""Main menu bar — all top-level menus and actions.

Creates QActions and exposes them as attributes so MainWindow can
connect them to its handler methods via triggered.connect().
"""

from PyQt6.QtWidgets import QMenuBar, QMenu
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction


class MainMenu(QMenuBar):
    """Menu bar with all ATPP menus.

    Actions are stored as instance attributes (e.g. self.act_new_product).
    MainWindow connects them: menu.act_new_product.triggered.connect(handler).
    """

    recent_menu_about_to_show = pyqtSignal()
    favorites_menu_about_to_show = pyqtSignal()

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self._user = user

        self._build_file_menu()
        self._build_references_menu()
        self._build_documents_menu()
        self._build_production_menu()
        self._build_service_menu()
        self._build_help_menu()

    # ── File menu ─────────────────────────────────────────────────

    def _build_file_menu(self):
        m = self.addMenu("Файл")

        self.act_new_product = QAction("Новое изделие", self)
        self.act_new_product.setShortcut("Ctrl+Shift+N")
        m.addAction(self.act_new_product)

        self.act_new_tp = QAction("Новый ТП", self)
        self.act_new_tp.setShortcut("Ctrl+N")
        m.addAction(self.act_new_tp)

        self.act_cad_import = QAction("Импорт из CAD-файла (STEP/CDW)...", self)
        m.addAction(self.act_cad_import)

        m.addSeparator()

        self.recent_menu = m.addMenu("🕘 Недавно открытые")
        self.recent_menu.aboutToShow.connect(self.recent_menu_about_to_show)
        self.favorites_menu = m.addMenu("⭐ Избранное")
        self.favorites_menu.aboutToShow.connect(self.favorites_menu_about_to_show)

        m.addSeparator()

        export_menu = m.addMenu("Экспорт (активный ТП)")
        self.act_export_xlsx = QAction("В Excel (.xlsx)", self)
        export_menu.addAction(self.act_export_xlsx)
        self.act_export_docx = QAction("В Word (.docx)", self)
        export_menu.addAction(self.act_export_docx)
        self.act_export_pdf = QAction("В PDF", self)
        export_menu.addAction(self.act_export_pdf)

        m.addSeparator()
        self.act_exit = QAction("Выход", self)
        self.act_exit.setShortcut("Ctrl+Q")
        m.addAction(self.act_exit)

    # ── References menu ───────────────────────────────────────────

    def _build_references_menu(self):
        m = self.addMenu("Справочники")
        self.act_open_references = QAction(
            "Материалы, оборудование, инструмент, профессии", self)
        m.addAction(self.act_open_references)
        self.act_open_reference_editors = QAction(
            "Редакторы справочников (табличный вид)...", self)
        m.addAction(self.act_open_reference_editors)

    # ── Documents menu ────────────────────────────────────────────

    def _build_documents_menu(self):
        m = self.addMenu("Документы")
        self.act_generate_docs = QAction(
            "Генерировать документы для активного ТП...", self)
        m.addAction(self.act_generate_docs)
        m.addSeparator()
        self.act_ktd_browser = QAction(
            "Библиотека шаблонов КТД (ГОСТ 3.1xxx)...", self)
        m.addAction(self.act_ktd_browser)

    # ── Production menu ───────────────────────────────────────────

    def _build_production_menu(self):
        m = self.addMenu("Производство")

        self.act_production_panel = QAction("📋 Панель «Производство»...", self)
        self.act_production_panel.setShortcut("Ctrl+Shift+P")
        m.addAction(self.act_production_panel)

        m.addSeparator()

        if self._user.get('role') in ('admin', 'technologist'):
            self.act_release_tp = QAction(
                "Передать активный ТП в производство...", self)
            m.addAction(self.act_release_tp)

        m.addSeparator()
        self.act_workshops = QAction("🏭 Справочник участков...", self)
        m.addAction(self.act_workshops)
        self.act_production_reports = QAction("📊 Отчёты производства...", self)
        m.addAction(self.act_production_reports)

        m.addSeparator()

        # v9 Middle Horizon
        self.act_manager_dashboard = QAction("📊 Дашборд руководителя…", self)
        m.addAction(self.act_manager_dashboard)
        self.act_gantt = QAction("📅 Gantt-планировщик…", self)
        m.addAction(self.act_gantt)
        self.act_equipment_load = QAction("⚙ Загрузка оборудования…", self)
        m.addAction(self.act_equipment_load)
        self.act_qa_terminal = QAction("🔍 Терминал ОТК…", self)
        m.addAction(self.act_qa_terminal)
        self.act_scrap_journal = QAction("❌ Брак-журнал…", self)
        m.addAction(self.act_scrap_journal)
        self.act_tooling = QAction("🧰 Учёт оснастки…", self)
        m.addAction(self.act_tooling)
        self.act_materials = QAction("📦 Учёт материала (партии)…", self)
        m.addAction(self.act_materials)
        self.act_metrology = QAction("📐 Метрологическая поверка…", self)
        m.addAction(self.act_metrology)
        self.act_ecn = QAction("✉ Извещения об изменениях (ECN)…", self)
        m.addAction(self.act_ecn)

        m.addSeparator()
        self.act_bom_editor = QAction("📦 Редактор состава изделия (BOM)…", self)
        m.addAction(self.act_bom_editor)
        self.act_iot_dashboard = QAction("📡 IoT-мониторинг станков…", self)
        m.addAction(self.act_iot_dashboard)
        self.act_nesting = QAction("📐 Раскрой листового металла…", self)
        m.addAction(self.act_nesting)
        self.act_chronometry = QAction("🕜 Хронометраж (анализ план/факт)…", self)
        m.addAction(self.act_chronometry)
        self.act_bom_graph = QAction("🔷 Графическое дерево БОМ…", self)
        m.addAction(self.act_bom_graph)

    # ── Service menu ──────────────────────────────────────────────

    def _build_service_menu(self):
        m = self.addMenu("Сервис")

        if self._user.get('role') == 'admin':
            self.act_users = QAction("Управление пользователями...", self)
            m.addAction(self.act_users)

        self.act_refresh = QAction("Обновить навигацию", self)
        self.act_refresh.setShortcut("F5")
        m.addAction(self.act_refresh)

        m.addSeparator()
        self.act_completeness = QAction("Дашборд полноты данных...", self)
        m.addAction(self.act_completeness)
        self.act_audit_log = QAction("Журнал изменений (audit log)...", self)
        m.addAction(self.act_audit_log)
        self.act_recycle_bin = QAction("🗑 Корзина...", self)
        m.addAction(self.act_recycle_bin)
        self.act_global_search = QAction("Глобальный поиск...", self)
        self.act_global_search.setShortcut("Ctrl+Shift+F")
        m.addAction(self.act_global_search)

        m.addSeparator()
        self.act_journal = QAction("📒 Журнал регистрации ТП/МТП...", self)
        m.addAction(self.act_journal)
        self.act_analytics = QAction("📊 Аналитические отчёты...", self)
        m.addAction(self.act_analytics)
        self.act_op_templates = QAction("📚 Библиотека типовых операций...", self)
        m.addAction(self.act_op_templates)
        self.act_transition_templates = QAction("📋 Шаблоны переходов...", self)
        m.addAction(self.act_transition_templates)
        self.act_excel_import = QAction("📥 Импорт справочников из Excel...", self)
        m.addAction(self.act_excel_import)

        m.addSeparator()
        self.act_backup_now = QAction("💾 Резервная копия БД сейчас", self)
        m.addAction(self.act_backup_now)
        self.act_restore_backup = QAction(
            "Восстановить из резервной копии...", self)
        m.addAction(self.act_restore_backup)
        self.act_backup_info = QAction(
            "Информация о резервных копиях...", self)
        m.addAction(self.act_backup_info)

        m.addSeparator()

        # 1C Integration submenu
        onec_menu = QMenu("Интеграция с 1С", self)
        self.act_1c_import = QAction("Импорт из 1С (XML/JSON)...", self)
        onec_menu.addAction(self.act_1c_import)
        self.act_export_spec_1c = QAction(
            "Экспорт спецификации (xlsx)...", self)
        onec_menu.addAction(self.act_export_spec_1c)
        self.act_export_cost_1c = QAction(
            "Экспорт себестоимости в 1С (XML)...", self)
        onec_menu.addAction(self.act_export_cost_1c)
        self.act_export_timeline_1c = QAction(
            "Экспорт графика в 1С (XML)...", self)
        onec_menu.addAction(self.act_export_timeline_1c)
        m.addMenu(onec_menu)

        self.act_ai_assistant = QAction("🧠 AI-помощник технолога...", self)
        m.addAction(self.act_ai_assistant)
        self.act_cutting_calc = QAction("🔧 Калькулятор режимов резания...", self)
        m.addAction(self.act_cutting_calc)
        self.act_unv_tables = QAction(
            "📐 Таблицы УНВ (укрупнённые нормы)...", self)
        m.addAction(self.act_unv_tables)

        m.addSeparator()
        self.act_doc_pack = QAction(
            "📋 Комплект документов (МК+ОК+ВМ)...", self)
        m.addAction(self.act_doc_pack)
        self.act_appearance = QAction("Настройки внешнего вида...", self)
        m.addAction(self.act_appearance)

        m.addSeparator()
        self.act_notifications = QAction("🔔 Уведомления...", self)
        self.act_notifications.setShortcut("Ctrl+Shift+N")
        m.addAction(self.act_notifications)
        self.act_change_password = QAction("👤 Сменить пароль...", self)
        m.addAction(self.act_change_password)

        m.addSeparator()
        self.act_toggle_messages = QAction("Панель сообщений", self)
        self.act_toggle_messages.setCheckable(True)
        m.addAction(self.act_toggle_messages)

    # ── Help menu ─────────────────────────────────────────────────

    def _build_help_menu(self):
        m = self.addMenu("Справка")
        self.act_about = QAction("О программе", self)
        m.addAction(self.act_about)
