"""Product editor widget — tabbed form with TP list and documents."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QLabel, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QPushButton, QTextEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QFrame, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap

from database.models import Product, Material, TechProcess


class ProductEditorWidget(QWidget):
    """Tabbed editor for a single Product.

    Signals:
        product_saved(product_id) — emitted after successful save.
        tp_open_requested(tp_id) — user double-clicked a TP in the list.
    """

    product_saved = pyqtSignal(int)
    tp_open_requested = pyqtSignal(int)

    def __init__(self, db_manager, product_id, user, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.product_id = product_id
        self.user = user
        self._original_data = None

        self._load_data()
        self._init_ui()

    def _load_data(self):
        self._materials = []
        with self.db_manager.get_session() as s:
            mats = s.query(Material).order_by(Material.name).all()
            self._materials = [
                (m.id, f"{m.name} {m.grade or ''}".strip(), m.gost or '')
                for m in mats
            ]
            prod = s.query(Product).get(self.product_id)
            if prod:
                self._original_data = {
                    'designation': prod.designation,
                    'name': prod.name,
                    'material_id': prod.material_id,
                    'mass': prod.mass,
                    'dimensions': prod.dimensions,
                    'blank_type': prod.blank_type,
                    'accuracy_class': prod.accuracy_class,
                    'roughness': prod.roughness,
                    'quantity_in_assembly': prod.quantity_in_assembly or 1,
                    'description': prod.description or '',
                    'group_id': prod.group_id,
                }
            else:
                self._original_data = None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        if self._original_data is None:
            layout.addWidget(QLabel("Изделие не найдено или удалено."))
            return

        # Header
        header = QHBoxLayout()
        title = QLabel(
            f"Изделие: {self._original_data['designation']} — "
            f"{self._original_data['name']}"
        )
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch()

        save_btn = QPushButton("Сохранить")
        save_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; "
            "border: none; padding: 6px 16px; border-radius: 4px; }"
        )
        save_btn.clicked.connect(self._save)
        header.addWidget(save_btn)
        layout.addLayout(header)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "Общие")
        tabs.addTab(self._build_tp_tab(), "Связанные ТП")
        tabs.addTab(self._build_docs_tab(), "Документы")
        layout.addWidget(tabs)

    def _build_general_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        d = self._original_data

        self._des_edit = QLineEdit(d['designation'])
        self._des_edit.setPlaceholderText("Например: УЗГА.754138.001")
        form.addRow("Обозначение *:", self._des_edit)

        self._name_edit = QLineEdit(d['name'])
        self._name_edit.setPlaceholderText("Наименование детали или сборки")
        form.addRow("Наименование *:", self._name_edit)

        self._mat_combo = QComboBox()
        self._mat_combo.addItem("— не выбран —", None)
        for mat_id, label, gost in self._materials:
            self._mat_combo.addItem(label, mat_id)
            if mat_id == d['material_id']:
                self._mat_combo.setCurrentIndex(self._mat_combo.count() - 1)
        form.addRow("Материал:", self._mat_combo)

        self._mass_sb = QDoubleSpinBox()
        self._mass_sb.setRange(0, 10000)
        self._mass_sb.setDecimals(3)
        self._mass_sb.setSuffix(" кг")
        if d['mass']:
            self._mass_sb.setValue(d['mass'])
        form.addRow("Масса:", self._mass_sb)

        self._dims_edit = QLineEdit(d['dimensions'] or '')
        self._dims_edit.setPlaceholderText("Д×Ш×В, мм")
        form.addRow("Габариты:", self._dims_edit)

        self._blank_combo = QComboBox()
        for bt in ['', 'Круг', 'Квадрат', 'Шестигранник', 'Лист', 'Труба',
                    'Поковка', 'Отливка', 'Штамповка', 'Профиль']:
            self._blank_combo.addItem(bt)
        if d['blank_type']:
            idx = self._blank_combo.findText(d['blank_type'])
            if idx >= 0:
                self._blank_combo.setCurrentIndex(idx)
        form.addRow("Вид заготовки:", self._blank_combo)

        self._acc_edit = QLineEdit(d['accuracy_class'] or '')
        form.addRow("Класс точности:", self._acc_edit)

        self._rough_edit = QLineEdit(d['roughness'] or '')
        form.addRow("Шероховатость:", self._rough_edit)

        self._qty_sb = QSpinBox()
        self._qty_sb.setRange(1, 10000)
        self._qty_sb.setValue(d.get('quantity_in_assembly', 1))
        form.addRow("Кол-во в сборке:", self._qty_sb)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlainText(d.get('description', ''))
        self._desc_edit.setMaximumHeight(100)
        form.addRow("Описание:", self._desc_edit)

        # Sketch placeholder
        sketch_row = QHBoxLayout()
        self._sketch_label = QLabel()
        self._sketch_label.setFixedSize(200, 150)
        self._sketch_label.setStyleSheet(
            "border: 1px dashed #bdc3c7; background: #f8f9fa;")
        self._sketch_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sketch_label.setText("Эскиз\n(нет)")
        sketch_row.addWidget(self._sketch_label)

        sketch_btns = QVBoxLayout()
        load_img_btn = QPushButton("Загрузить...")
        load_img_btn.clicked.connect(self._load_sketch)
        sketch_btns.addWidget(load_img_btn)
        sketch_btns.addStretch()
        sketch_row.addLayout(sketch_btns)
        form.addRow("Эскиз:", sketch_row)

        return w

    def _build_tp_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        self._tp_table = QTableWidget(0, 4)
        self._tp_table.setHorizontalHeaderLabels(
            ["Номер", "Версия", "Статус", "Вариант исп."])
        self._tp_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self._tp_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._tp_table.doubleClicked.connect(self._on_tp_row_dblclick)
        lay.addWidget(self._tp_table)

        btn_row = QHBoxLayout()
        add_tp_btn = QPushButton("+ Создать ТП")
        add_tp_btn.clicked.connect(self._on_add_tp)
        btn_row.addWidget(add_tp_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._refresh_tp_table()
        return w

    def _build_docs_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel(
            "Документы для изделия. Будет расширено в v11 (Фаза 3)."))
        lay.addStretch()
        return w

    # ── Actions ───────────────────────────────────────────────────

    def _save(self):
        designation = self._des_edit.text().strip()
        name = self._name_edit.text().strip()
        if not designation or not name:
            QMessageBox.warning(self, "Валидация",
                                "Обозначение и наименование обязательны.")
            return
        try:
            with self.db_manager.get_session() as s:
                prod = s.query(Product).get(self.product_id)
                if not prod:
                    return
                prod.designation = designation
                prod.name = name
                prod.material_id = self._mat_combo.currentData()
                prod.mass = self._mass_sb.value() or None
                prod.dimensions = self._dims_edit.text().strip() or None
                prod.blank_type = self._blank_combo.currentText() or None
                prod.accuracy_class = self._acc_edit.text().strip() or None
                prod.roughness = self._rough_edit.text().strip() or None
                prod.quantity_in_assembly = self._qty_sb.value()
                prod.description = self._desc_edit.toPlainText().strip() or None
            self._original_data['designation'] = designation
            self._original_data['name'] = name
            self.product_saved.emit(self.product_id)
            QMessageBox.information(self, "Сохранено",
                                    f"Изделие «{designation}» сохранено.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить:\n{e}")

    def _refresh_tp_table(self):
        with self.db_manager.get_session() as s:
            tps = (s.query(TechProcess)
                   .filter(TechProcess.product_id == self.product_id,
                           (TechProcess.is_deleted == False) |
                           (TechProcess.is_deleted.is_(None)))
                   .order_by(TechProcess.number)
                   .all())
            self._tp_table.setRowCount(len(tps))
            for i, tp in enumerate(tps):
                self._tp_table.setItem(
                    i, 0, QTableWidgetItem(tp.number))
                self._tp_table.setItem(
                    i, 1, QTableWidgetItem(tp.version or '1.0'))
                self._tp_table.setItem(
                    i, 2, QTableWidgetItem(tp.status.value
                                           if hasattr(tp.status, 'value')
                                           else str(tp.status)))
                self._tp_table.setItem(
                    i, 3, QTableWidgetItem(
                        getattr(tp, 'execution_variant', '') or ''))
            self._tp_table.resizeColumnsToContents()

    def _on_tp_row_dblclick(self):
        row = self._tp_table.currentRow()
        if row >= 0:
            num = self._tp_table.item(row, 0).text()
            with self.db_manager.get_session() as s:
                tp = s.query(TechProcess).filter_by(number=num).first()
                if tp:
                    self.tp_open_requested.emit(tp.id)

    def _on_add_tp(self):
        # Delegate to main window via parent
        mw = self.window()
        if hasattr(mw, '_new_tech_process'):
            mw._new_tech_process(product_id=self.product_id)

    def _load_sketch(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите эскиз",
            "", "Изображения (*.png *.jpg *.bmp);;Все файлы (*)")
        if path:
            pix = QPixmap(path)
            if not pix.isNull():
                scaled = pix.scaled(
                    200, 150, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                self._sketch_label.setPixmap(scaled)
                self._sketch_label.setText("")

    def get_tab_title(self):
        d = self._original_data or {}
        return f"Изделие: {d.get('designation', '?')}"
