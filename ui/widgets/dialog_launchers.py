"""Dialog launcher methods — mixin for MainWindow.

Each method opens a dialog or adds a widget tab.  Extracted from
main_window.py to keep the coordinator class under 800 lines.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QLabel, QHBoxLayout, QDoubleSpinBox, QInputDialog,
    QMessageBox, QFileDialog, QPlainTextEdit, QSplitter,
    QPushButton, QWidget, QTabWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from database.models import Product, TechProcess, TPStatus


class DialogLaunchersMixin:
    """Mixin providing _open_* and _export_* methods.

    Requires: self.db_manager, self.user, self.work_area,
              self._add_or_focus_tab(), self._log_message(),
              self._open_tp_editor(), self.load_navigation_data().
    """

    # ── References ────────────────────────────────────────────────

    def _open_references(self):
        from ui.dialogs.references_dialog import ReferencesDialog
        dlg = ReferencesDialog(self.db_manager, parent=self)
        dlg.exec()

    def _open_users_dialog(self):
        from ui.dialogs.users_dialog import UsersDialog
        dlg = UsersDialog(self.db_manager, self.user, parent=self)
        dlg.exec()

    # ── Documents ─────────────────────────────────────────────────

    def _open_ktd_browser(self):
        from ui.dialogs.ktd_browser_dialog import KTDBrowserDialog
        dlg = KTDBrowserDialog(parent=self)
        dlg.exec()

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

    # ── Dashboard / Audit / Completeness ──────────────────────────

    def _open_completeness_dashboard(self):
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

    # ── Production ────────────────────────────────────────────────

    def _open_production_panel(self):
        from ui.widgets.production_widget import ProductionWidget
        w = ProductionWidget(self.db_manager, self.user, self)
        self._add_or_focus_tab(w, 'Производство')

    def _release_active_tp(self):
        from ui.dialogs.production_dialogs import ReleaseDialog
        widget = self.work_area.currentWidget()
        tp_id = getattr(widget, 'tp_id', None)
        dlg = ReleaseDialog(self.db_manager, self.user, parent=self,
                            default_tp_id=tp_id)
        if dlg.exec():
            self._open_production_panel()

    def _open_workshops_dialog(self):
        from ui.dialogs.workshops_dialog import WorkshopsDialog
        dlg = WorkshopsDialog(self.db_manager, self.user, parent=self)
        dlg.exec()

    def _open_production_reports(self):
        from ui.dialogs.production_reports_dialog import ProductionReportsDialog
        dlg = ProductionReportsDialog(self.db_manager, self.user, parent=self)
        dlg.exec()

    # ── v9 Middle Horizon ─────────────────────────────────────────

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

    # ── v10 Features ──────────────────────────────────────────────

    def _open_bom_editor(self):
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
        from ui.widgets.bom_widget import BOMWidget
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
                fp = export_cost_data(s, out_path=EXPORT_DIR / '1c_cost.xml')
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
        from modules.unv_tables import lookup_unv, list_categories, CATEGORY_MAP

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
            cat_key = list(CATEGORY_MAP.keys())[cat_cb.currentIndex()] \
                if 0 <= cat_cb.currentIndex() < len(CATEGORY_MAP) \
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
            tbl.setItem(i, 1, QTableWidgetItem(f'{r.planned_t_piece:.1f}'))
            tbl.setItem(i, 2, QTableWidgetItem(
                f'{r.actual_minutes:.1f}' if r.actual_minutes else '—'))
            tbl.setItem(i, 3, QTableWidgetItem(
                f'{r.deviation_pct:+.0f}%' if r.deviation_pct is not None
                else '—'))
            tbl.setItem(i, 4, QTableWidgetItem(r.work_order_number))
        lay.addWidget(tbl)
        dlg.exec()

    def _open_bom_graph(self):
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

    # ── Service ───────────────────────────────────────────────────

    def _open_global_search(self):
        from ui.widgets.global_search import GlobalSearchWidget
        w = GlobalSearchWidget(self.db_manager, self)
        try:
            w.tp_open.connect(self._open_tp_editor)
        except Exception:
            pass
        self._add_or_focus_tab(w, 'Поиск')

    def _open_quick_search(self):
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

    def _open_report_builder(self):
        from ui.widgets.report_builder import ReportBuilderWidget
        w = ReportBuilderWidget(self.db_manager, self)
        self._add_or_focus_tab(w, 'Конструктор отчётов')

    def _open_formula_editor(self):
        from ui.widgets.formula_editor import FormulaEditorWidget
        w = FormulaEditorWidget(self.db_manager, self)
        self._add_or_focus_tab(w, 'Редактор формул')

    def _open_shift_dashboard(self):
        from ui.widgets.shift_dashboard import ShiftDashboard
        w = ShiftDashboard(self.db_manager, self)
        self._add_or_focus_tab(w, 'Дашборд смены')

    def _open_pdo_dispatcher(self):
        from ui.widgets.pdo_dispatcher import PDODispatcherWidget
        w = PDODispatcherWidget(self.db_manager, self.user, self)
        self._add_or_focus_tab(w, 'Диспетчер ПДО')

    def _show_hotkeys(self):
        from ui.dialogs.hotkey_help import show_hotkey_help
        show_hotkey_help(parent=self)

    def _open_pdo_analytics(self):
        from ui.widgets.pdo_analytics_widget import PDOAnalyticsWidget
        w = PDOAnalyticsWidget(self.db_manager, self)
        self._add_or_focus_tab(w, 'Аналитика ПДО')

    def _open_registration_journal(self):
        from ui.widgets.journal_widget import JournalWidget
        w = JournalWidget(self.db_manager, self.user, self)
        try:
            w.open_tp.connect(self._open_tp_editor)
        except Exception:
            pass
        self._add_or_focus_tab(w, 'Журнал регистрации')

    def _open_op_templates(self):
        from ui.dialogs.op_templates_dialog import OpTemplatesDialog
        dlg = OpTemplatesDialog(self.db_manager, parent=self)
        dlg.exec()

    def _open_transition_templates(self):
        from ui.dialogs.transition_templates_dialog import (
            TransitionTemplatesDialog,
        )
        dlg = TransitionTemplatesDialog(self.db_manager, parent=self)
        dlg.exec()

    def _open_excel_import(self):
        from ui.dialogs.excel_import_dialog import ExcelImportDialog
        dlg = ExcelImportDialog(self.db_manager, parent=self)
        dlg.exec()

    def _open_recycle_bin(self):
        from ui.widgets.recycle_bin import RecycleBinWidget
        w = RecycleBinWidget(self.db_manager, self)
        w.changed.connect(self.load_navigation_data)
        self._add_or_focus_tab(w, 'Корзина')

    def _export_specification_1c(self):
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

    def _open_batch_print(self):
        from ui.dialogs.batch_print_dialog import BatchPrintDialog
        dlg = BatchPrintDialog(self.db_manager, parent=self)
        dlg.exec()

    def _open_notifications(self):
        from ui.dialogs.notifications_dialog import NotificationsDialog
        dlg = NotificationsDialog(self.db_manager, self.user, parent=self)
        dlg.exec()
        if hasattr(self, '_refresh_notifications_badge'):
            self._refresh_notifications_badge()

    def _open_change_password_self(self):
        from ui.dialogs.change_password_dialog import ChangePasswordDialog
        dlg = ChangePasswordDialog(self.db_manager, self.user, parent=self)
        dlg.exec()

    # ── Backup ────────────────────────────────────────────────────

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

    # ═══════════════════════════════════════════════════════════════
    # Product CRUD
    # ═══════════════════════════════════════════════════════════════

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
        item = self.nav_panel.products_tree.currentItem()
        if not item:
            QMessageBox.information(self, "Выбор", "Выберите изделие для редактирования")
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, int):
            self._edit_product(data)

    def _edit_product(self, product_id):
        session = self.db_manager.Session()
        try:
            p = session.get(Product, product_id)
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
                    p = session.get(Product, product_id)
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
        item = self.nav_panel.products_tree.currentItem()
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, int):
            self._delete_product(data)

    def _delete_product(self, product_id):
        session = self.db_manager.Session()
        try:
            p = session.get(Product, product_id)
            if not p:
                return
            designation = p.designation
            tp_count = len(p.tech_processes)
        finally:
            session.close()

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
                    p = session.get(Product, product_id)
                    if not p:
                        return
                    p.is_deleted = True
                    p.deleted_at = _dt.now()
                    p.deleted_by = uid
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

    # ═══════════════════════════════════════════════════════════════
    # TP CRUD
    # ═══════════════════════════════════════════════════════════════

    def _new_tech_process(self, product_id=None):
        from ui.dialogs.tp_dialog import TPDialog
        dlg = TPDialog(self.db_manager, product_id=product_id, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            data = dlg.get_data()
            try:
                new_tp_id = None
                is_variant = False
                with self.db_manager.get_session() as session:
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
                    sib_count = (session.query(TechProcess)
                                 .filter(TechProcess.product_id == data['product_id'],
                                         TechProcess.id != new_tp_id)
                                 .count())
                    is_variant = sib_count > 0

                self.load_navigation_data()
                self._log_message(f"ТП «{data['number']}» создан")
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
            tp = session.get(TechProcess, tp_id)
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
                if tp_id in self._open_tp_tabs:
                    self._close_tab(self._open_tp_tabs[tp_id])
                with self.db_manager.get_session() as session:
                    tp = session.get(TechProcess, tp_id)
                    if tp:
                        tp.is_deleted = True
                        tp.deleted_at = datetime.now()
                        if self.user and self.user.get('id'):
                            tp.deleted_by = self.user['id']
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

        with self.db_manager.get_session() as s:
            tp = s.get(TechProcess, tp_id)
            if not tp:
                return
            original_number = tp.number
            variant_default = getattr(tp, 'execution_variant', '') or ''

        new_number, ok = QInputDialog.getText(
            self, "Копирование ТП",
            f"Номер для копии ТП «{original_number}»:",
            text=f"{original_number}-копия"
        )
        if not ok or not new_number.strip():
            return

        new_variant, ok2 = QInputDialog.getText(
            self, "Вариант исполнения",
            "Вариант исполнения для копии (можно оставить пустым):",
            text=variant_default
        )
        if not ok2:
            return
        new_variant = new_variant.strip() or None

        with self.db_manager.get_session() as s:
            designer = TPDesigner(s)
            new_tp = designer.copy_tech_process(
                source_tp_id=tp_id,
                new_number=new_number.strip(),
                author_id=self.user.get('id'),
                new_execution_variant=new_variant
            )
            new_tp_id = new_tp.id

        self.load_navigation_data()
        self._log_message(f"ТП скопирован как «{new_number}»")
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

    # ═══════════════════════════════════════════════════════════════
    # Versioning / History / Archive
    # ═══════════════════════════════════════════════════════════════

    def _snapshot_tp(self, tp_id):
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

        # Tab 2: audit log
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
            tp = session.get(TechProcess, tp_id)
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
                tp = session.get(TechProcess, tp_id)
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

    # ═══════════════════════════════════════════════════════════════
    # Bookmarks
    # ═══════════════════════════════════════════════════════════════

    def _refresh_recent_menu(self):
        if hasattr(self, '_menu'):
            self._populate_bookmark_menu(self._menu.recent_menu, favorites=False)

    def _refresh_favorites_menu(self):
        if hasattr(self, '_menu'):
            self._populate_bookmark_menu(self._menu.favorites_menu, favorites=True)

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

    def _toggle_active_tp_favorite(self):
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
            from utils.logger import get_logger
            get_logger(__name__).debug('bookmarks toggle failed: %s', e)

    # ═══════════════════════════════════════════════════════════════
    # Journal registration
    # ═══════════════════════════════════════════════════════════════

    def _register_in_journal(self, kind: str, entity_id: int,
                             *, is_variant: bool, title: str, prompt: str,
                             register_default: bool = True,
                             suggested_tp_number=None):
        from ui.dialogs.journal_register_dialog import JournalRegisterDialog
        from modules import journal as journal_mod

        defaults = {}
        if suggested_tp_number:
            defaults['tp_number'] = suggested_tp_number
            defaults['mtp_number'] = suggested_tp_number
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
                    obj = s.get(Product, entity_id)
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
                    tp = s.get(TechProcess, entity_id)
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
