"""
Диалог создания и редактирования технологического процесса
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from database.models import Product, TechnologyType, TPType


class TPDialog(QDialog):
    """Диалог создания / редактирования ТП"""

    TP_TYPES = {
        TPType.SINGLE: "Единичный",
        TPType.TYPICAL: "Типовой",
        TPType.GROUP: "Групповой",
    }

    TECH_TYPES = {
        TechnologyType.MACHINING: "Механическая обработка",
        TechnologyType.ASSEMBLY: "Сборка",
        TechnologyType.WELDING: "Сварка",
        TechnologyType.STAMPING: "Штамповка",
        TechnologyType.HEAT_TREATMENT: "Термообработка",
        TechnologyType.CASTING: "Литьё",
        TechnologyType.COATING: "Покрытия",
        TechnologyType.CUTTING: "Резка",
        TechnologyType.OTHER: "Другое",
    }

    def __init__(self, db_manager, product_id=None, tp_data=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.forced_product_id = product_id
        self.tp_data = tp_data
        self.is_edit = tp_data is not None
        self.result_data = None

        self.setWindowTitle("Редактирование ТП" if self.is_edit else "Новый технологический процесс")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._load_products()
        self._init_ui()

        if self.is_edit:
            self._fill_form()
        elif product_id:
            self._select_product(product_id)

    def _load_products(self):
        session = self.db_manager.Session()
        try:
            prods = session.query(Product).order_by(Product.designation).all()
            self._products = [(p.id, f"{p.designation}  —  {p.name}") for p in prods]
        finally:
            session.close()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Редактирование ТП" if self.is_edit else "Новый технологический процесс")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #bdc3c7;")
        layout.addWidget(line)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Номер ТП
        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("Например: ТП-001 или 754138.001.МК")
        form.addRow("Номер ТП *:", self.number_edit)

        # Изделие
        self.product_combo = QComboBox()
        self.product_combo.setMinimumWidth(320)
        for prod_id, prod_label in self._products:
            self.product_combo.addItem(prod_label, prod_id)
        if not self._products:
            self.product_combo.addItem("— нет изделий —", None)
        form.addRow("Изделие *:", self.product_combo)

        # Тип ТП
        self.tp_type_combo = QComboBox()
        for tp_type, label in self.TP_TYPES.items():
            self.tp_type_combo.addItem(label, tp_type)
        form.addRow("Тип ТП:", self.tp_type_combo)

        # Вид технологии
        self.tech_type_combo = QComboBox()
        for tech_type, label in self.TECH_TYPES.items():
            self.tech_type_combo.addItem(label, tech_type)
        form.addRow("Вид технологии:", self.tech_type_combo)

        # Версия
        self.version_edit = QLineEdit()
        self.version_edit.setText("1.0")
        self.version_edit.setFixedWidth(100)
        form.addRow("Версия:", self.version_edit)

        # Вариант исполнения (опционально, если на одну деталь несколько ТП)
        self.variant_edit = QLineEdit()
        self.variant_edit.setPlaceholderText("Например: «Исп. А», «С наплавкой», «Без покрытия»…")
        form.addRow("Вариант исполнения:", self.variant_edit)

        # Описание
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(70)
        self.description_edit.setPlaceholderText("Краткое описание технологического процесса...")
        form.addRow("Описание:", self.description_edit)

        layout.addLayout(form)
        layout.addSpacing(8)

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
                border-radius: 4px; font-weight: bold; font-size: 13px;
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

    def _select_product(self, product_id):
        for i in range(self.product_combo.count()):
            if self.product_combo.itemData(i) == product_id:
                self.product_combo.setCurrentIndex(i)
                self.product_combo.setEnabled(False)
                break

    def _fill_form(self):
        d = self.tp_data
        self.number_edit.setText(d.get('number', '') or '')
        self.version_edit.setText(d.get('version', '1.0') or '1.0')
        self.variant_edit.setText(d.get('execution_variant', '') or '')
        self.description_edit.setPlainText(d.get('description', '') or '')

        prod_id = d.get('product_id')
        if prod_id:
            self._select_product(prod_id)

        tp_type = d.get('tp_type')
        for i in range(self.tp_type_combo.count()):
            if self.tp_type_combo.itemData(i) == tp_type:
                self.tp_type_combo.setCurrentIndex(i)
                break

        tech_type = d.get('technology_type')
        for i in range(self.tech_type_combo.count()):
            if self.tech_type_combo.itemData(i) == tech_type:
                self.tech_type_combo.setCurrentIndex(i)
                break

    def _on_save(self):
        number = self.number_edit.text().strip()
        product_id = self.product_combo.currentData()

        if not number:
            QMessageBox.warning(self, "Ошибка", "Поле «Номер ТП» обязательно для заполнения")
            self.number_edit.setFocus()
            return
        if not product_id:
            QMessageBox.warning(self, "Ошибка", "Необходимо выбрать изделие")
            return

        self.result_data = {
            'number': number,
            'product_id': product_id,
            'tp_type': self.tp_type_combo.currentData(),
            'technology_type': self.tech_type_combo.currentData(),
            'version': self.version_edit.text().strip() or '1.0',
            'execution_variant': self.variant_edit.text().strip() or None,
            'description': self.description_edit.toPlainText().strip() or None,
        }
        self.accept()

    def get_data(self):
        return self.result_data
