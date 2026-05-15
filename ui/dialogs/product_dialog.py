"""
Диалог создания и редактирования изделия
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QDoubleSpinBox,
    QPushButton, QTextEdit, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from database.models import Material


class ProductDialog(QDialog):
    """Диалог создания и редактирования изделия"""

    def __init__(self, db_manager, product_data=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.product_data = product_data  # dict или None
        self.is_edit = product_data is not None
        self.result_data = None

        self.setWindowTitle("Редактирование изделия" if self.is_edit else "Новое изделие")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._load_materials()
        self._init_ui()

        if self.is_edit:
            self._fill_form()

    def _load_materials(self):
        session = self.db_manager.Session()
        try:
            mats = session.query(Material).order_by(Material.name).all()
            self._materials = [(m.id, f"{m.name} {m.grade or ''}".strip(), m.gost or '') for m in mats]
        finally:
            session.close()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Заголовок
        title = QLabel("Редактирование изделия" if self.is_edit else "Новое изделие")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Обозначение
        self.designation_edit = QLineEdit()
        self.designation_edit.setPlaceholderText("Например: УЗГА.754138.001")
        form.addRow("Обозначение *:", self.designation_edit)

        # Наименование
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Наименование детали или сборки")
        form.addRow("Наименование *:", self.name_edit)

        # Материал
        self.material_combo = QComboBox()
        self.material_combo.setMinimumWidth(280)
        self.material_combo.addItem("— не выбран —", None)
        for mat_id, mat_label, gost in self._materials:
            tooltip = gost
            self.material_combo.addItem(mat_label, mat_id)
            if gost:
                self.material_combo.setItemData(
                    self.material_combo.count() - 1, gost, Qt.ItemDataRole.ToolTipRole
                )
        form.addRow("Материал:", self.material_combo)

        # Масса
        self.mass_spin = QDoubleSpinBox()
        self.mass_spin.setRange(0, 999999)
        self.mass_spin.setDecimals(3)
        self.mass_spin.setSuffix(" кг")
        self.mass_spin.setFixedWidth(150)
        form.addRow("Масса:", self.mass_spin)

        # Габариты
        self.dimensions_edit = QLineEdit()
        self.dimensions_edit.setPlaceholderText("Например: 100×50×25 мм")
        form.addRow("Габариты:", self.dimensions_edit)

        # Вид заготовки
        self.blank_type_combo = QComboBox()
        self.blank_type_combo.addItems([
            "", "Прокат круглый", "Прокат квадратный", "Прокат шестигранный",
            "Лист", "Труба", "Отливка", "Поковка", "Штамповка",
            "Сварная конструкция", "Пруток"
        ])
        form.addRow("Вид заготовки:", self.blank_type_combo)

        # Класс точности
        self.accuracy_edit = QLineEdit()
        self.accuracy_edit.setPlaceholderText("IT6, IT7, IT8...")
        self.accuracy_edit.setFixedWidth(150)
        form.addRow("Класс точности:", self.accuracy_edit)

        # Шероховатость
        self.roughness_edit = QLineEdit()
        self.roughness_edit.setPlaceholderText("Ra 0.8, Ra 1.6, Rz 20...")
        self.roughness_edit.setFixedWidth(150)
        form.addRow("Шероховатость:", self.roughness_edit)

        # Кол-во в сборке
        from PyQt6.QtWidgets import QSpinBox
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 9999)
        self.qty_spin.setValue(1)
        self.qty_spin.setFixedWidth(100)
        form.addRow("Кол-во в сборке:", self.qty_spin)

        # Примечание
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(70)
        self.description_edit.setPlaceholderText("Дополнительные сведения...")
        form.addRow("Примечание:", self.description_edit)

        layout.addLayout(form)
        layout.addSpacing(8)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("  Сохранить  ")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)

        cancel_btn = QPushButton("  Отмена  ")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _fill_form(self):
        p = self.product_data
        self.designation_edit.setText(p.get('designation', '') or '')
        self.name_edit.setText(p.get('name', '') or '')

        mat_id = p.get('material_id')
        if mat_id:
            for i in range(self.material_combo.count()):
                if self.material_combo.itemData(i) == mat_id:
                    self.material_combo.setCurrentIndex(i)
                    break

        self.mass_spin.setValue(float(p.get('mass', 0) or 0))
        self.dimensions_edit.setText(p.get('dimensions', '') or '')

        blank = p.get('blank_type', '') or ''
        idx = self.blank_type_combo.findText(blank)
        if idx >= 0:
            self.blank_type_combo.setCurrentIndex(idx)

        self.accuracy_edit.setText(p.get('accuracy_class', '') or '')
        self.roughness_edit.setText(p.get('roughness', '') or '')
        self.qty_spin.setValue(int(p.get('quantity_in_assembly', 1) or 1))
        self.description_edit.setPlainText(p.get('description', '') or '')

    def _on_save(self):
        designation = self.designation_edit.text().strip()
        name = self.name_edit.text().strip()

        if not designation:
            QMessageBox.warning(self, "Ошибка", "Поле «Обозначение» обязательно для заполнения")
            self.designation_edit.setFocus()
            return
        if not name:
            QMessageBox.warning(self, "Ошибка", "Поле «Наименование» обязательно для заполнения")
            self.name_edit.setFocus()
            return

        self.result_data = {
            'designation': designation,
            'name': name,
            'material_id': self.material_combo.currentData(),
            'mass': self.mass_spin.value() if self.mass_spin.value() > 0 else None,
            'dimensions': self.dimensions_edit.text().strip() or None,
            'blank_type': self.blank_type_combo.currentText() or None,
            'accuracy_class': self.accuracy_edit.text().strip() or None,
            'roughness': self.roughness_edit.text().strip() or None,
            'quantity_in_assembly': self.qty_spin.value(),
            'description': self.description_edit.toPlainText().strip() or None,
        }
        self.accept()

    def get_data(self):
        return self.result_data
