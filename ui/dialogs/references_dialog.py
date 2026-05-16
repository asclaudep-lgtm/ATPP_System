"""
Диалог управления справочниками (материалы, оборудование, инструмент, профессии)
"""
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QLineEdit, QDoubleSpinBox, QSpinBox, QFormLayout,
    QMessageBox, QHeaderView, QAbstractItemView, QFrame,
    QComboBox, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.fluent_compat import PrimaryPushButton, PushButton
from database.models import Material, Equipment, Tool, Profession


class ReferencesDialog(QDialog):
    """Справочники — вкладки: Материалы, Оборудование, Инструмент, Профессии"""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Справочники")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Справочники")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._make_materials_tab(), "Материалы")
        self.tabs.addTab(self._make_equipment_tab(), "Оборудование")
        self.tabs.addTab(self._make_tools_tab(), "Инструмент")
        self.tabs.addTab(self._make_professions_tab(), "Профессии")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        hl = QHBoxLayout()
        hl.addStretch()
        hl.addWidget(close_btn)
        layout.addLayout(hl)

        self._load_materials()

    # ============================================================
    # Вкладка Материалы
    # ============================================================
    def _make_materials_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # Таблица
        self.mat_table = QTableWidget()
        self.mat_table.setColumnCount(6)
        self.mat_table.setHorizontalHeaderLabels(["ID", "Наименование", "Марка", "ГОСТ", "Плотность, кг/м³", "Цена, руб/кг"])
        self.mat_table.setColumnHidden(0, True)
        self.mat_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.mat_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.mat_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mat_table.setAlternatingRowColors(True)
        layout.addWidget(self.mat_table)

        # Форма
        form_frame = QFrame()
        form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        form_layout = QFormLayout(form_frame)
        form_layout.setSpacing(7)

        self.mat_name = QLineEdit()
        self.mat_grade = QLineEdit()
        self.mat_gost = QLineEdit()
        self.mat_density = QDoubleSpinBox()
        self.mat_density.setRange(0, 99999)
        self.mat_density.setDecimals(1)
        self.mat_density.setSuffix(" кг/м³")
        self.mat_price = QDoubleSpinBox()
        self.mat_price.setRange(0, 9999999)
        self.mat_price.setDecimals(2)
        self.mat_price.setSuffix(" руб/кг")

        form_layout.addRow("Наименование *:", self.mat_name)
        form_layout.addRow("Марка:", self.mat_grade)
        form_layout.addRow("ГОСТ:", self.mat_gost)
        form_layout.addRow("Плотность:", self.mat_density)
        form_layout.addRow("Цена:", self.mat_price)

        layout.addWidget(form_frame)

        btn_layout = QHBoxLayout()
        self.mat_add_btn = PrimaryPushButton("Добавить")
        self.mat_add_btn.clicked.connect(self._add_material)
        self.mat_edit_btn = QPushButton("Изменить")
        self.mat_edit_btn.clicked.connect(self._edit_material)
        self.mat_del_btn = QPushButton("Удалить")
        self.mat_del_btn.clicked.connect(self._delete_material)
        self.mat_clear_btn = QPushButton("Очистить")
        self.mat_clear_btn.clicked.connect(self._clear_material_form)

        for btn in [self.mat_add_btn, self.mat_edit_btn, self.mat_del_btn, self.mat_clear_btn]:
            btn.setFixedHeight(28)
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.mat_table.selectionModel().selectionChanged.connect(self._on_material_selected)
        return w

    def _load_materials(self):
        session = self.db_manager.Session()
        try:
            mats = session.query(Material).order_by(Material.name).all()
            self.mat_table.setRowCount(0)
            for m in mats:
                row = self.mat_table.rowCount()
                self.mat_table.insertRow(row)
                self.mat_table.setItem(row, 0, QTableWidgetItem(str(m.id)))
                self.mat_table.setItem(row, 1, QTableWidgetItem(m.name or ''))
                self.mat_table.setItem(row, 2, QTableWidgetItem(m.grade or ''))
                self.mat_table.setItem(row, 3, QTableWidgetItem(m.gost or ''))
                self.mat_table.setItem(row, 4, QTableWidgetItem(str(m.density or '')))
                self.mat_table.setItem(row, 5, QTableWidgetItem(str(m.price_per_kg or '')))
        finally:
            session.close()

    def _on_material_selected(self):
        row = self.mat_table.currentRow()
        if row < 0:
            return
        self.mat_name.setText(self.mat_table.item(row, 1).text())
        self.mat_grade.setText(self.mat_table.item(row, 2).text())
        self.mat_gost.setText(self.mat_table.item(row, 3).text())
        try:
            self.mat_density.setValue(float(self.mat_table.item(row, 4).text()))
        except (ValueError, TypeError, AttributeError):
            self.mat_density.setValue(0)
        try:
            self.mat_price.setValue(float(self.mat_table.item(row, 5).text()))
        except (ValueError, TypeError, AttributeError):
            self.mat_price.setValue(0)

    def _add_material(self):
        name = self.mat_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите наименование материала")
            return
        with self.db_manager.get_session() as session:
            mat = Material(
                name=name,
                grade=self.mat_grade.text().strip() or None,
                gost=self.mat_gost.text().strip() or None,
                density=self.mat_density.value() or None,
                price_per_kg=self.mat_price.value() or None,
            )
            session.add(mat)
        self._load_materials()
        self._clear_material_form()

    def _edit_material(self):
        row = self.mat_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Выбор", "Выберите материал для изменения")
            return
        mat_id = int(self.mat_table.item(row, 0).text())
        name = self.mat_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите наименование")
            return
        with self.db_manager.get_session() as session:
            mat = session.get(Material, mat_id)
            if mat:
                mat.name = name
                mat.grade = self.mat_grade.text().strip() or None
                mat.gost = self.mat_gost.text().strip() or None
                mat.density = self.mat_density.value() or None
                mat.price_per_kg = self.mat_price.value() or None
        self._load_materials()

    def _delete_material(self):
        row = self.mat_table.currentRow()
        if row < 0:
            return
        mat_id = int(self.mat_table.item(row, 0).text())
        name = self.mat_table.item(row, 1).text()
        reply = QMessageBox.question(self, "Удаление",
                                     f"Удалить материал «{name}»?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with self.db_manager.get_session() as session:
                    mat = session.get(Material, mat_id)
                    if mat:
                        session.delete(mat)
                self._load_materials()
                self._clear_material_form()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось удалить: {e}")

    def _clear_material_form(self):
        self.mat_name.clear()
        self.mat_grade.clear()
        self.mat_gost.clear()
        self.mat_density.setValue(0)
        self.mat_price.setValue(0)
        self.mat_table.clearSelection()

    # ============================================================
    # Вкладка Оборудование
    # ============================================================
    def _make_equipment_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        self.eq_table = QTableWidget()
        self.eq_table.setColumnCount(6)
        self.eq_table.setHorizontalHeaderLabels(["ID", "Наименование", "Модель", "Тип", "Мощность, кВт", "Стоимость ч/р, руб"])
        self.eq_table.setColumnHidden(0, True)
        self.eq_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.eq_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.eq_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.eq_table.setAlternatingRowColors(True)
        layout.addWidget(self.eq_table)

        form_frame = QFrame()
        form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        fl = QFormLayout(form_frame)
        fl.setSpacing(7)

        self.eq_name = QLineEdit()
        self.eq_model = QLineEdit()
        self.eq_type = QLineEdit()
        self.eq_power = QDoubleSpinBox()
        self.eq_power.setRange(0, 9999)
        self.eq_power.setDecimals(1)
        self.eq_power.setSuffix(" кВт")
        self.eq_cost = QDoubleSpinBox()
        self.eq_cost.setRange(0, 9999999)
        self.eq_cost.setDecimals(2)
        self.eq_cost.setSuffix(" руб/ч")

        fl.addRow("Наименование *:", self.eq_name)
        fl.addRow("Модель:", self.eq_model)
        fl.addRow("Тип:", self.eq_type)
        fl.addRow("Мощность:", self.eq_power)
        fl.addRow("Стоимость ч/р:", self.eq_cost)
        layout.addWidget(form_frame)

        btn_layout = QHBoxLayout()
        self.eq_add_btn = PrimaryPushButton("Добавить")
        self.eq_add_btn.clicked.connect(self._add_equipment)
        self.eq_edit_btn = QPushButton("Изменить")
        self.eq_edit_btn.clicked.connect(self._edit_equipment)
        self.eq_del_btn = QPushButton("Удалить")
        self.eq_del_btn.clicked.connect(self._delete_equipment)
        self.eq_clear_btn = QPushButton("Очистить")
        self.eq_clear_btn.clicked.connect(self._clear_equipment_form)
        for btn in [self.eq_add_btn, self.eq_edit_btn, self.eq_del_btn, self.eq_clear_btn]:
            btn.setFixedHeight(28)
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.eq_table.selectionModel().selectionChanged.connect(self._on_equipment_selected)
        return w

    def _load_equipment(self):
        session = self.db_manager.Session()
        try:
            equip = session.query(Equipment).order_by(Equipment.name).all()
            self.eq_table.setRowCount(0)
            for e in equip:
                row = self.eq_table.rowCount()
                self.eq_table.insertRow(row)
                self.eq_table.setItem(row, 0, QTableWidgetItem(str(e.id)))
                self.eq_table.setItem(row, 1, QTableWidgetItem(e.name or ''))
                self.eq_table.setItem(row, 2, QTableWidgetItem(e.model or ''))
                self.eq_table.setItem(row, 3, QTableWidgetItem(e.type or ''))
                self.eq_table.setItem(row, 4, QTableWidgetItem(str(e.power or '')))
                self.eq_table.setItem(row, 5, QTableWidgetItem(str(e.cost_per_hour or '')))
        finally:
            session.close()

    def _on_equipment_selected(self):
        row = self.eq_table.currentRow()
        if row < 0:
            return
        self.eq_name.setText(self.eq_table.item(row, 1).text())
        self.eq_model.setText(self.eq_table.item(row, 2).text())
        self.eq_type.setText(self.eq_table.item(row, 3).text())
        try:
            self.eq_power.setValue(float(self.eq_table.item(row, 4).text()))
        except (ValueError, TypeError, AttributeError):
            self.eq_power.setValue(0)
        try:
            self.eq_cost.setValue(float(self.eq_table.item(row, 5).text()))
        except (ValueError, TypeError, AttributeError):
            self.eq_cost.setValue(0)

    def _add_equipment(self):
        name = self.eq_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите наименование оборудования")
            return
        with self.db_manager.get_session() as session:
            eq = Equipment(
                name=name,
                model=self.eq_model.text().strip() or None,
                type=self.eq_type.text().strip() or None,
                power=self.eq_power.value() or None,
                cost_per_hour=self.eq_cost.value() or None,
            )
            session.add(eq)
        self._load_equipment()
        self._clear_equipment_form()

    def _edit_equipment(self):
        row = self.eq_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Выбор", "Выберите оборудование")
            return
        eq_id = int(self.eq_table.item(row, 0).text())
        name = self.eq_name.text().strip()
        if not name:
            return
        with self.db_manager.get_session() as session:
            eq = session.get(Equipment, eq_id)
            if eq:
                eq.name = name
                eq.model = self.eq_model.text().strip() or None
                eq.type = self.eq_type.text().strip() or None
                eq.power = self.eq_power.value() or None
                eq.cost_per_hour = self.eq_cost.value() or None
        self._load_equipment()

    def _delete_equipment(self):
        row = self.eq_table.currentRow()
        if row < 0:
            return
        eq_id = int(self.eq_table.item(row, 0).text())
        name = self.eq_table.item(row, 1).text()
        if QMessageBox.question(self, "Удаление", f"Удалить «{name}»?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                ) == QMessageBox.StandardButton.Yes:
            try:
                with self.db_manager.get_session() as session:
                    eq = session.get(Equipment, eq_id)
                    if eq:
                        session.delete(eq)
                self._load_equipment()
                self._clear_equipment_form()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось удалить: {e}")

    def _clear_equipment_form(self):
        self.eq_name.clear()
        self.eq_model.clear()
        self.eq_type.clear()
        self.eq_power.setValue(0)
        self.eq_cost.setValue(0)
        self.eq_table.clearSelection()

    # ============================================================
    # Вкладка Инструмент
    # ============================================================
    def _make_tools_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        self.tool_table = QTableWidget()
        self.tool_table.setColumnCount(4)
        self.tool_table.setHorizontalHeaderLabels(["ID", "Обозначение", "Наименование", "Тип"])
        self.tool_table.setColumnHidden(0, True)
        self.tool_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tool_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tool_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tool_table.setAlternatingRowColors(True)
        layout.addWidget(self.tool_table)

        form_frame = QFrame()
        form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        fl = QFormLayout(form_frame)
        fl.setSpacing(7)

        self.tool_desig = QLineEdit()
        self.tool_name = QLineEdit()
        self.tool_type_combo = QComboBox()
        self.tool_type_combo.addItems(["Режущий", "Измерительный", "Вспомогательный", "Слесарный"])
        self.tool_desc = QLineEdit()

        fl.addRow("Обозначение *:", self.tool_desig)
        fl.addRow("Наименование:", self.tool_name)
        fl.addRow("Тип инструмента:", self.tool_type_combo)
        fl.addRow("Описание:", self.tool_desc)
        layout.addWidget(form_frame)

        btn_layout = QHBoxLayout()
        self.tool_add_btn = PrimaryPushButton("Добавить")
        self.tool_add_btn.clicked.connect(self._add_tool)
        self.tool_edit_btn = QPushButton("Изменить")
        self.tool_edit_btn.clicked.connect(self._edit_tool)
        self.tool_del_btn = QPushButton("Удалить")
        self.tool_del_btn.clicked.connect(self._delete_tool)
        self.tool_clear_btn = QPushButton("Очистить")
        self.tool_clear_btn.clicked.connect(self._clear_tool_form)
        for btn in [self.tool_add_btn, self.tool_edit_btn, self.tool_del_btn, self.tool_clear_btn]:
            btn.setFixedHeight(28)
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.tool_table.selectionModel().selectionChanged.connect(self._on_tool_selected)
        return w

    def _load_tools(self):
        session = self.db_manager.Session()
        try:
            tools = session.query(Tool).order_by(Tool.designation).all()
            self.tool_table.setRowCount(0)
            for t in tools:
                row = self.tool_table.rowCount()
                self.tool_table.insertRow(row)
                self.tool_table.setItem(row, 0, QTableWidgetItem(str(t.id)))
                self.tool_table.setItem(row, 1, QTableWidgetItem(t.designation or ''))
                self.tool_table.setItem(row, 2, QTableWidgetItem(t.name or ''))
                self.tool_table.setItem(row, 3, QTableWidgetItem(t.tool_type or ''))
        finally:
            session.close()

    def _on_tool_selected(self):
        row = self.tool_table.currentRow()
        if row < 0:
            return
        self.tool_desig.setText(self.tool_table.item(row, 1).text())
        self.tool_name.setText(self.tool_table.item(row, 2).text())
        idx = self.tool_type_combo.findText(self.tool_table.item(row, 3).text())
        if idx >= 0:
            self.tool_type_combo.setCurrentIndex(idx)

    def _add_tool(self):
        desig = self.tool_desig.text().strip()
        if not desig:
            QMessageBox.warning(self, "Ошибка", "Введите обозначение инструмента")
            return
        with self.db_manager.get_session() as session:
            t = Tool(
                designation=desig,
                name=self.tool_name.text().strip() or None,
                tool_type=self.tool_type_combo.currentText(),
            )
            session.add(t)
        self._load_tools()
        self._clear_tool_form()

    def _edit_tool(self):
        row = self.tool_table.currentRow()
        if row < 0:
            return
        tool_id = int(self.tool_table.item(row, 0).text())
        with self.db_manager.get_session() as session:
            t = session.get(Tool, tool_id)
            if t:
                t.designation = self.tool_desig.text().strip()
                t.name = self.tool_name.text().strip() or None
                t.tool_type = self.tool_type_combo.currentText()
        self._load_tools()

    def _delete_tool(self):
        row = self.tool_table.currentRow()
        if row < 0:
            return
        tool_id = int(self.tool_table.item(row, 0).text())
        name = self.tool_table.item(row, 1).text()
        if QMessageBox.question(self, "Удаление", f"Удалить «{name}»?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                ) == QMessageBox.StandardButton.Yes:
            try:
                with self.db_manager.get_session() as session:
                    t = session.get(Tool, tool_id)
                    if t:
                        session.delete(t)
                self._load_tools()
                self._clear_tool_form()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось удалить: {e}")

    def _clear_tool_form(self):
        self.tool_desig.clear()
        self.tool_name.clear()
        self.tool_table.clearSelection()

    # ============================================================
    # Вкладка Профессии
    # ============================================================
    def _make_professions_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        self.prof_table = QTableWidget()
        self.prof_table.setColumnCount(3)
        self.prof_table.setHorizontalHeaderLabels(["ID", "Наименование", "Типовой разряд"])
        self.prof_table.setColumnHidden(0, True)
        self.prof_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.prof_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.prof_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.prof_table.setAlternatingRowColors(True)
        layout.addWidget(self.prof_table)

        form_frame = QFrame()
        form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        fl = QFormLayout(form_frame)
        fl.setSpacing(7)

        self.prof_name = QLineEdit()
        self.prof_grade = QSpinBox()
        self.prof_grade.setRange(1, 6)
        self.prof_grade.setValue(3)
        self.prof_grade.setFixedWidth(80)

        fl.addRow("Наименование *:", self.prof_name)
        fl.addRow("Типовой разряд:", self.prof_grade)
        layout.addWidget(form_frame)

        btn_layout = QHBoxLayout()
        self.prof_add_btn = PrimaryPushButton("Добавить")
        self.prof_add_btn.clicked.connect(self._add_profession)
        self.prof_edit_btn = QPushButton("Изменить")
        self.prof_edit_btn.clicked.connect(self._edit_profession)
        self.prof_del_btn = QPushButton("Удалить")
        self.prof_del_btn.clicked.connect(self._delete_profession)
        self.prof_clear_btn = QPushButton("Очистить")
        self.prof_clear_btn.clicked.connect(self._clear_prof_form)
        for btn in [self.prof_add_btn, self.prof_edit_btn, self.prof_del_btn, self.prof_clear_btn]:
            btn.setFixedHeight(28)
            btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.prof_table.selectionModel().selectionChanged.connect(self._on_prof_selected)
        return w

    def _load_professions(self):
        session = self.db_manager.Session()
        try:
            profs = session.query(Profession).order_by(Profession.name).all()
            self.prof_table.setRowCount(0)
            for p in profs:
                row = self.prof_table.rowCount()
                self.prof_table.insertRow(row)
                self.prof_table.setItem(row, 0, QTableWidgetItem(str(p.id)))
                self.prof_table.setItem(row, 1, QTableWidgetItem(p.name or ''))
                self.prof_table.setItem(row, 2, QTableWidgetItem(str(p.typical_grade or '')))
        finally:
            session.close()

    def _on_prof_selected(self):
        row = self.prof_table.currentRow()
        if row < 0:
            return
        self.prof_name.setText(self.prof_table.item(row, 1).text())
        try:
            self.prof_grade.setValue(int(self.prof_table.item(row, 2).text()))
        except (ValueError, TypeError, AttributeError):
            self.prof_grade.setValue(3)

    def _add_profession(self):
        name = self.prof_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите наименование профессии")
            return
        grade = self.prof_grade.value()
        rates = {str(i): 200 + (i - 1) * 25 for i in range(1, 7)}
        with self.db_manager.get_session() as session:
            p = Profession(
                name=name,
                typical_grade=grade,
                hourly_rates=json.dumps(rates)
            )
            session.add(p)
        self._load_professions()
        self._clear_prof_form()

    def _edit_profession(self):
        row = self.prof_table.currentRow()
        if row < 0:
            return
        prof_id = int(self.prof_table.item(row, 0).text())
        with self.db_manager.get_session() as session:
            p = session.get(Profession, prof_id)
            if p:
                p.name = self.prof_name.text().strip()
                p.typical_grade = self.prof_grade.value()
        self._load_professions()

    def _delete_profession(self):
        row = self.prof_table.currentRow()
        if row < 0:
            return
        prof_id = int(self.prof_table.item(row, 0).text())
        name = self.prof_table.item(row, 1).text()
        if QMessageBox.question(self, "Удаление", f"Удалить «{name}»?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                ) == QMessageBox.StandardButton.Yes:
            try:
                with self.db_manager.get_session() as session:
                    p = session.get(Profession, prof_id)
                    if p:
                        session.delete(p)
                self._load_professions()
                self._clear_prof_form()
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось удалить: {e}")

    def _clear_prof_form(self):
        self.prof_name.clear()
        self.prof_grade.setValue(3)
        self.prof_table.clearSelection()

    # ============================================================
    # Переключение вкладок — ленивая загрузка
    # ============================================================
    def _on_tab_changed(self, index):
        if index == 0:
            self._load_materials()
        elif index == 1:
            self._load_equipment()
        elif index == 2:
            self._load_tools()
        elif index == 3:
            self._load_professions()
