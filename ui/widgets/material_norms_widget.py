"""
Виджет материального нормирования
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QDoubleSpinBox, QPushButton,
    QTableWidget, QTableWidgetItem, QGroupBox,
    QMessageBox, QHeaderView, QAbstractItemView, QSplitter, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from database.models import Material, MaterialNorm, TechProcess
from modules.material_calc import MaterialCalculator


PROFILES = ["Круг", "Квадрат", "Шестигранник", "Лист", "Труба"]

PROFILE_FIELDS = {
    "Круг":        [("Диаметр D, мм", "diameter"), ("Длина L, мм", "length")],
    "Квадрат":     [("Сторона a, мм", "side"), ("Длина L, мм", "length")],
    "Шестигранник":[("Сторона a, мм", "side"), ("Длина L, мм", "length")],
    "Лист":        [("Ширина B, мм", "width"), ("Длина L, мм", "length"), ("Толщина h, мм", "thickness")],
    "Труба":       [("Нар. диаметр D, мм", "outer_diameter"), ("Вн. диаметр d, мм", "inner_diameter"), ("Длина L, мм", "length")],
}


class MaterialNormsWidget(QWidget):
    """Расчёт и хранение норм расхода материалов"""

    def __init__(self, db_manager, tp_id, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.tp_id = tp_id

        self._load_materials()
        self._init_ui()
        self._load_existing_norms()

    def _load_materials(self):
        session = self.db_manager.Session()
        try:
            mats = session.query(Material).order_by(Material.name).all()
            self._materials = [(m.id, f"{m.name} {m.grade or ''}".strip(), m.density) for m in mats]
        finally:
            session.close()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Форма расчёта ──
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)

        calc_group = QGroupBox("Расчёт нормы расхода материала")
        calc_main = QHBoxLayout(calc_group)

        # Левая часть формы
        left_form = QFormLayout()
        left_form.setSpacing(8)
        left_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._mat_combo = QComboBox()
        self._mat_combo.setMinimumWidth(240)
        for mat_id, mat_name, density in self._materials:
            self._mat_combo.addItem(mat_name, mat_id)
        left_form.addRow("Материал:", self._mat_combo)

        self._profile_combo = QComboBox()
        self._profile_combo.addItems(PROFILES)
        self._profile_combo.currentTextChanged.connect(self._on_profile_changed)
        left_form.addRow("Профиль заготовки:", self._profile_combo)

        calc_main.addLayout(left_form)

        # Размеры заготовки (динамические)
        self._dims_group = QGroupBox("Размеры заготовки")
        self._dims_form = QFormLayout(self._dims_group)
        self._dims_form.setSpacing(7)
        self._dim_spins = {}
        calc_main.addWidget(self._dims_group)

        # Правая часть
        right_form = QFormLayout()
        right_form.setSpacing(8)
        right_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._allowance_spin = QDoubleSpinBox()
        self._allowance_spin.setRange(0, 100)
        self._allowance_spin.setDecimals(1)
        self._allowance_spin.setValue(2.0)
        self._allowance_spin.setSuffix(" мм")
        self._allowance_spin.setFixedWidth(120)
        right_form.addRow("Припуск на обр.:", self._allowance_spin)

        self._cut_spin = QDoubleSpinBox()
        self._cut_spin.setRange(0, 100)
        self._cut_spin.setDecimals(1)
        self._cut_spin.setValue(3.0)
        self._cut_spin.setSuffix(" мм")
        self._cut_spin.setFixedWidth(120)
        right_form.addRow("Припуск на отрезку:", self._cut_spin)

        self._coeff_spin = QDoubleSpinBox()
        self._coeff_spin.setRange(1.0, 5.0)
        self._coeff_spin.setDecimals(3)
        self._coeff_spin.setValue(1.0)
        self._coeff_spin.setFixedWidth(120)
        right_form.addRow("Коэф. расхода:", self._coeff_spin)

        self._parts_spin = QDoubleSpinBox()
        self._parts_spin.setRange(1, 999)
        self._parts_spin.setDecimals(0)
        self._parts_spin.setValue(1)
        self._parts_spin.setFixedWidth(120)
        right_form.addRow("Деталей из заготовки:", self._parts_spin)

        calc_main.addLayout(right_form)

        # Кнопка расчёта
        btn_layout = QVBoxLayout()
        calc_btn = QPushButton("Рассчитать")
        calc_btn.setFixedHeight(36)
        calc_btn.clicked.connect(self._calculate)
        btn_layout.addStretch()
        btn_layout.addWidget(calc_btn)
        calc_main.addLayout(btn_layout)

        form_layout.addWidget(calc_group)

        # Результат расчёта
        result_group = QGroupBox("Результат")
        result_layout = QHBoxLayout(result_group)
        self._result_labels = {}
        for key, label in [
            ('norm', 'Норма расхода, кг:'),
            ('waste', 'Отходы, %:'),
            ('cost', 'Стоимость, руб:'),
            ('kim', 'КИМ:'),
        ]:
            vl = QVBoxLayout()
            vl.addWidget(QLabel(label))
            val_lbl = QLabel("—")
            val_font = QFont()
            val_font.setPointSize(13)
            val_font.setBold(True)
            val_lbl.setFont(val_font)
            vl.addWidget(val_lbl)
            self._result_labels[key] = val_lbl
            result_layout.addLayout(vl)
            if key != 'kim':
                line = QFrame()
                line.setFrameShape(QFrame.Shape.VLine)
                result_layout.addWidget(line)

        form_layout.addWidget(result_group)
        splitter.addWidget(form_widget)

        # ── Таблица норм ──
        norms_widget = QWidget()
        norms_layout = QVBoxLayout(norms_widget)
        norms_layout.setContentsMargins(0, 0, 0, 0)

        norms_header = QHBoxLayout()
        norms_header.addWidget(QLabel("Нормы расхода материала по данному ТП"))
        norms_header.addStretch()
        del_btn = QPushButton("Удалить выбранную")
        del_btn.clicked.connect(self._delete_norm)
        norms_header.addWidget(del_btn)
        norms_layout.addLayout(norms_header)

        self._norms_table = QTableWidget()
        self._norms_table.setColumnCount(6)
        self._norms_table.setHorizontalHeaderLabels([
            "ID", "Материал", "Профиль", "Норма, кг", "Отходы, %", "Стоимость, руб"
        ])
        self._norms_table.setColumnHidden(0, True)
        self._norms_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._norms_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._norms_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._norms_table.setAlternatingRowColors(True)
        norms_layout.addWidget(self._norms_table)

        splitter.addWidget(norms_widget)
        splitter.setSizes([300, 200])

        layout.addWidget(splitter)

        # Инициализировать поля размеров
        self._on_profile_changed(self._profile_combo.currentText())

    def _on_profile_changed(self, profile):
        # Очищаем старые поля
        while self._dims_form.count() > 0:
            item = self._dims_form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                pass
        self._dim_spins.clear()

        fields = PROFILE_FIELDS.get(profile, [])
        for label, key in fields:
            spin = QDoubleSpinBox()
            spin.setRange(0, 99999)
            spin.setDecimals(1)
            spin.setSuffix(" мм")
            spin.setFixedWidth(130)
            self._dims_form.addRow(label, spin)
            self._dim_spins[key] = spin

    def _calculate(self):
        mat_id = self._mat_combo.currentData()
        if not mat_id:
            QMessageBox.warning(self, "Ошибка", "Выберите материал")
            return

        profile = self._profile_combo.currentText()
        dims = {k: s.value() for k, s in self._dim_spins.items() if s.value() > 0}
        if not dims:
            QMessageBox.warning(self, "Ошибка", "Введите размеры заготовки")
            return

        session = self.db_manager.Session()
        try:
            calc = MaterialCalculator(session)
            norm = calc.calculate_material_norm(
                tech_process_id=self.tp_id,
                material_id=mat_id,
                blank_profile=profile,
                blank_dimensions=dims,
                part_dimensions={},
                allowance=self._allowance_spin.value(),
                cutting_allowance=self._cut_spin.value(),
                consumption_coefficient=self._coeff_spin.value(),
                parts_per_blank=int(self._parts_spin.value()),
            )

            # Рассчитываем КИМ
            blank_vol = calc.calculate_blank_volume(profile, dims)
            kim = 0
            if blank_vol > 0:
                kim = min(blank_vol * 0.5 / blank_vol, 1.0)

            self._result_labels['norm'].setText(f"{norm.norm_per_piece:.4f}")
            self._result_labels['waste'].setText(f"{norm.waste_percent:.1f}")
            self._result_labels['cost'].setText(f"{norm.cost_per_piece:.2f}")
            self._result_labels['kim'].setText(f"{(1 - norm.waste_percent / 100):.3f}" if norm.waste_percent else "—")

            session.commit()
            self._load_existing_norms()

        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Ошибка расчёта", str(e))
        finally:
            session.close()

    def _load_existing_norms(self):
        session = self.db_manager.Session()
        try:
            norms = (session.query(MaterialNorm)
                     .filter_by(tech_process_id=self.tp_id)
                     .all())
            self._norms_table.setRowCount(0)
            for n in norms:
                mat = session.get(Material, n.material_id)
                mat_name = f"{mat.name} {mat.grade or ''}".strip() if mat else '—'

                row = self._norms_table.rowCount()
                self._norms_table.insertRow(row)
                self._norms_table.setItem(row, 0, QTableWidgetItem(str(n.id)))
                self._norms_table.setItem(row, 1, QTableWidgetItem(mat_name))
                self._norms_table.setItem(row, 2, QTableWidgetItem(n.blank_profile or ''))
                self._norms_table.setItem(row, 3, QTableWidgetItem(
                    f"{n.norm_per_piece:.4f}" if n.norm_per_piece else ''))
                self._norms_table.setItem(row, 4, QTableWidgetItem(
                    f"{n.waste_percent:.1f}" if n.waste_percent else ''))
                self._norms_table.setItem(row, 5, QTableWidgetItem(
                    f"{n.cost_per_piece:.2f}" if n.cost_per_piece else ''))
        finally:
            session.close()

    def _delete_norm(self):
        row = self._norms_table.currentRow()
        if row < 0:
            return
        norm_id = int(self._norms_table.item(row, 0).text())
        if QMessageBox.question(self, "Удаление", "Удалить норму расхода?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                                ) == QMessageBox.StandardButton.Yes:
            with self.db_manager.get_session() as session:
                n = session.get(MaterialNorm, norm_id)
                if n:
                    session.delete(n)
            self._load_existing_norms()
