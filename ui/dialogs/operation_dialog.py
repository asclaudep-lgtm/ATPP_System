"""
Диалог создания и редактирования операции
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from database.models import Equipment, Profession


class OperationDialog(QDialog):
    """Диалог создания и редактирования операции"""

    def __init__(self, db_manager, op_data=None, next_number=None,
                 product_designation: str = '', parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.op_data = op_data
        self.is_edit = op_data is not None
        self.next_number = next_number or '005'
        self.product_designation = product_designation
        self.result_data = None

        self.setWindowTitle("Редактирование операции" if self.is_edit else "Новая операция")
        self.setMinimumWidth(580)
        self.setMinimumHeight(560)
        self.setModal(True)

        self._load_references()
        self._init_ui()

        if self.is_edit:
            self._fill_form()

    def _load_references(self):
        session = self.db_manager.Session()
        try:
            equip = session.query(Equipment).order_by(Equipment.name).all()
            self._equipment = [(e.id, e.name, e.model or '') for e in equip]

            profs = session.query(Profession).order_by(Profession.name).all()
            self._professions = [(p.id, p.name, p.typical_grade or 3) for p in profs]
        finally:
            session.close()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Заголовок + кнопка «Из шаблона…»
        header_row = QHBoxLayout()
        title = QLabel("Редактирование операции" if self.is_edit else "Новая операция")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        header_row.addWidget(title)
        header_row.addStretch()
        if not self.is_edit:
            tmpl_btn = QPushButton("📥 Из шаблона…")
            tmpl_btn.setToolTip(
                "Подставить значения из библиотеки типовых операций.\n"
                "Часто используемые: Контрольная, Слесарная, Заготовительная и т.п."
            )
            tmpl_btn.clicked.connect(self._import_from_template)
            header_row.addWidget(tmpl_btn)
        layout.addLayout(header_row)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #bdc3c7;")
        layout.addWidget(line)

        tabs = QTabWidget()

        # Вкладка «Основное»
        main_tab = QWidget()
        main_form = QFormLayout(main_tab)
        main_form.setSpacing(9)
        main_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Номер операции
        self.number_edit = QLineEdit()
        self.number_edit.setText(self.next_number)
        self.number_edit.setFixedWidth(100)
        self.number_edit.setPlaceholderText("005, 010...")
        main_form.addRow("№ операции *:", self.number_edit)

        # Наименование
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Токарная, Фрезерная, Сборочная...")
        main_form.addRow("Наименование *:", self.name_edit)

        # Код операции
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("4110, 4210...")
        self.code_edit.setFixedWidth(120)
        main_form.addRow("Код операции:", self.code_edit)

        # Цех/участок
        self.shop_edit = QLineEdit()
        self.shop_edit.setPlaceholderText("Цех 10, Участок 3...")
        main_form.addRow("Цех / участок:", self.shop_edit)

        # Оборудование
        self.equipment_combo = QComboBox()
        self.equipment_combo.setMinimumWidth(280)
        self.equipment_combo.addItem("— не выбрано —", None)
        for eq_id, eq_name, eq_model in self._equipment:
            label = f"{eq_name}" + (f"  [{eq_model}]" if eq_model else "")
            self.equipment_combo.addItem(label, eq_id)
        self.equipment_combo.currentIndexChanged.connect(self._on_equipment_changed)
        main_form.addRow("Оборудование:", self.equipment_combo)

        # Профессия
        self.profession_combo = QComboBox()
        self.profession_combo.addItem("— не выбрана —", None)
        for pr_id, pr_name, pr_grade in self._professions:
            self.profession_combo.addItem(pr_name, pr_id)
        self.profession_combo.currentIndexChanged.connect(self._on_profession_changed)
        main_form.addRow("Профессия:", self.profession_combo)

        # Разряд
        self.grade_spin = QSpinBox()
        self.grade_spin.setRange(1, 6)
        self.grade_spin.setValue(3)
        self.grade_spin.setFixedWidth(80)
        main_form.addRow("Разряд:", self.grade_spin)

        # Число станков
        self.machine_count_spin = QSpinBox()
        self.machine_count_spin.setRange(1, 99)
        self.machine_count_spin.setValue(1)
        self.machine_count_spin.setFixedWidth(80)
        main_form.addRow("Кол-во станков:", self.machine_count_spin)

        # Включать в МТП
        self.include_in_mtp_check = QCheckBox(
            "Включать в маршрутно-технологический паспорт (МК / МСК)"
        )
        self.include_in_mtp_check.setChecked(True)
        self.include_in_mtp_check.setToolTip(
            "Если флажок снят — операция остаётся в составе ТП и в расчётах\n"
            "(норма времени, себестоимость), но не выводится в маршрутную (МК)\n"
            "и маршрутно-сопроводительную (МСК) карты."
        )
        main_form.addRow("Выдача в МТП:", self.include_in_mtp_check)

        tabs.addTab(main_tab, "Основное")

        # Вкладка «Нормы времени»
        time_tab = QWidget()
        time_layout = QVBoxLayout(time_tab)

        time_group = QGroupBox("Нормы времени, мин")
        time_form = QFormLayout(time_group)
        time_form.setSpacing(9)
        time_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def make_time_spin():
            s = QDoubleSpinBox()
            s.setRange(0, 9999)
            s.setDecimals(2)
            s.setSuffix(" мин")
            s.setFixedWidth(130)
            return s

        self.t_main_spin = make_time_spin()
        time_form.addRow("То  (основное):", self.t_main_spin)

        self.t_auxiliary_spin = make_time_spin()
        time_form.addRow("Тв  (вспомогательное):", self.t_auxiliary_spin)

        self.t_piece_spin = make_time_spin()
        time_form.addRow("Тшт  (штучное):", self.t_piece_spin)

        self.t_setup_spin = make_time_spin()
        time_form.addRow("Тпз  (подг.-закл.):", self.t_setup_spin)

        # Авторасчёт Тшт
        calc_btn = QPushButton("Рассчитать Тшт автоматически")
        calc_btn.clicked.connect(self._auto_calc_piece_time)
        calc_btn.setStyleSheet("QPushButton { padding: 5px 12px; }")
        time_form.addRow("", calc_btn)

        time_layout.addWidget(time_group)
        time_layout.addStretch()
        tabs.addTab(time_tab, "Нормы времени")

        # Вкладка «Примечание»
        note_tab = QWidget()
        note_layout = QVBoxLayout(note_tab)
        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Дополнительные указания к операции...")
        note_layout.addWidget(self.note_edit)
        tabs.addTab(note_tab, "Примечание")

        # Вкладка «Эскизы»
        from ui.widgets.sketches_panel import SketchesPanel
        op_id = (self.op_data or {}).get('id') if self.is_edit else None
        self.sketches_panel = SketchesPanel(
            self.db_manager,
            parent_kind='operation',
            parent_id=op_id,
            product_designation=self.product_designation,
        )
        tabs.addTab(self.sketches_panel, "Эскизы")

        layout.addWidget(tabs)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("  Сохранить  ")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white;
                border: none; padding: 8px 20px;
                border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #229954; }
        """)

        cancel_btn = QPushButton("  Отмена  ")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; color: white;
                border: none; padding: 8px 20px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_profession_changed(self, index):
        pr_id = self.profession_combo.itemData(index)
        for pid, pname, pgrade in self._professions:
            if pid == pr_id:
                self.grade_spin.setValue(pgrade)
                break

    def _on_equipment_changed(self, index):
        """Автоподстановка профессии по выбранному оборудованию.

        Логика:
        1. Если у Equipment есть default_profession_id — берём его.
        2. Иначе — самая частая профессия для этого оборудования
           по статистике существующих операций.
        Только если профессия пока не выбрана пользователем.
        """
        eq_id = self.equipment_combo.itemData(index)
        if not eq_id:
            return
        # уважаем выбор пользователя
        if self.profession_combo.currentData():
            return
        try:
            from modules.autofill import suggest_profession_for_equipment
            pr_id = suggest_profession_for_equipment(self.db_manager, eq_id)
        except Exception:
            pr_id = None
        if pr_id:
            for i in range(self.profession_combo.count()):
                if self.profession_combo.itemData(i) == pr_id:
                    self.profession_combo.setCurrentIndex(i)
                    break

    def _import_from_template(self):
        from ui.dialogs.op_templates_dialog import OpTemplatesDialog
        dlg = OpTemplatesDialog(self.db_manager, pick_mode=True, parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        tmpl = dlg.selected_template
        if not tmpl:
            return
        # Заполняем поля
        if tmpl.get('name'):
            self.name_edit.setText(tmpl['name'])
        if tmpl.get('code'):
            self.code_edit.setText(tmpl['code'])
        if tmpl.get('shop'):
            self.shop_edit.setText(tmpl['shop'])
        if tmpl.get('typical_equipment_id'):
            for i in range(self.equipment_combo.count()):
                if self.equipment_combo.itemData(i) == tmpl['typical_equipment_id']:
                    self.equipment_combo.setCurrentIndex(i)
                    break
        if tmpl.get('typical_profession_id'):
            for i in range(self.profession_combo.count()):
                if self.profession_combo.itemData(i) == tmpl['typical_profession_id']:
                    self.profession_combo.setCurrentIndex(i)
                    break
        if tmpl.get('grade'):
            self.grade_spin.setValue(int(tmpl['grade']))
        if tmpl.get('t_setup'):
            self.t_setup_spin.setValue(float(tmpl['t_setup']))
        if tmpl.get('t_piece'):
            self.t_piece_spin.setValue(float(tmpl['t_piece']))
        if tmpl.get('description'):
            self.note_edit.setPlainText(tmpl['description'])

    def _auto_calc_piece_time(self):
        t_main = self.t_main_spin.value()
        t_aux = self.t_auxiliary_spin.value()
        if t_main == 0 and t_aux == 0:
            QMessageBox.information(self, "Авторасчёт",
                                    "Введите То и Тв для расчёта Тшт.\n"
                                    "Тшт = (То + Тв) × 1.09  (9% на обслуживание и отдых)")
            return
        t_piece = (t_main + t_aux) * 1.09
        self.t_piece_spin.setValue(round(t_piece, 2))

    def _fill_form(self):
        d = self.op_data
        self.number_edit.setText(str(d.get('number', '') or ''))
        self.name_edit.setText(d.get('name', '') or '')
        self.code_edit.setText(d.get('code', '') or '')
        self.shop_edit.setText(d.get('shop', '') or '')
        self.note_edit.setPlainText(d.get('note', '') or '')
        self.machine_count_spin.setValue(int(d.get('machine_count', 1) or 1))
        self.include_in_mtp_check.setChecked(bool(d.get('include_in_mtp', True)))
        self.t_main_spin.setValue(float(d.get('t_main', 0) or 0))
        self.t_auxiliary_spin.setValue(float(d.get('t_auxiliary', 0) or 0))
        self.t_piece_spin.setValue(float(d.get('t_piece', 0) or 0))
        self.t_setup_spin.setValue(float(d.get('t_setup', 0) or 0))

        eq_id = d.get('equipment_id')
        if eq_id:
            for i in range(self.equipment_combo.count()):
                if self.equipment_combo.itemData(i) == eq_id:
                    self.equipment_combo.setCurrentIndex(i)
                    break

        pr_id = d.get('profession_id')
        if pr_id:
            for i in range(self.profession_combo.count()):
                if self.profession_combo.itemData(i) == pr_id:
                    self.profession_combo.setCurrentIndex(i)
                    break

        grade = d.get('grade')
        if grade:
            self.grade_spin.setValue(int(grade))

    def _on_save(self):
        number = self.number_edit.text().strip()
        name = self.name_edit.text().strip()

        if not number:
            QMessageBox.warning(self, "Ошибка", "Номер операции обязателен")
            self.number_edit.setFocus()
            return
        if not name:
            QMessageBox.warning(self, "Ошибка", "Наименование операции обязательно")
            self.name_edit.setFocus()
            return

        self.result_data = {
            'number': number.zfill(3),
            'name': name,
            'code': self.code_edit.text().strip() or None,
            'shop': self.shop_edit.text().strip() or None,
            'equipment_id': self.equipment_combo.currentData(),
            'profession_id': self.profession_combo.currentData(),
            'grade': self.grade_spin.value(),
            'machine_count': self.machine_count_spin.value(),
            'include_in_mtp': self.include_in_mtp_check.isChecked(),
            't_main': self.t_main_spin.value(),
            't_auxiliary': self.t_auxiliary_spin.value(),
            't_piece': self.t_piece_spin.value(),
            't_setup': self.t_setup_spin.value(),
            'note': self.note_edit.toPlainText().strip() or None,
        }
        self.accept()

    def get_data(self):
        return self.result_data
