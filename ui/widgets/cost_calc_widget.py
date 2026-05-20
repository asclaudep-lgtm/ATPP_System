"""
Виджет расчёта себестоимости
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config import DEFAULT_FACTORY_OVERHEAD, DEFAULT_LABOR_OVERHEAD, DEFAULT_PROFIT_MARGIN, DEFAULT_SHOP_OVERHEAD
from modules.cost_calc import (
    TIME_MODE_ACTUAL,
    TIME_MODE_PLAN,
    CostCalculator,
)

COST_ROWS = [
    ('material_cost',      'Материалы'),
    ('labor_cost',         'Заработная плата'),
    ('social_contributions','Соц. отчисления'),
    ('equipment_cost',     'Эксплуатация оборудования'),
    ('shop_overhead',      'Цеховые расходы'),
    ('factory_overhead',   'Общезаводские расходы'),
]


class CostCalcWidget(QWidget):
    """Расчёт и отображение себестоимости ТП"""

    def __init__(self, db_manager, tp_id, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.tp_id = tp_id
        self._init_ui()
        self._try_load_existing()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # Параметры расчёта
        params_group = QGroupBox("Параметры расчёта")
        params_layout = QHBoxLayout(params_group)

        def pct_spin(default):
            s = QDoubleSpinBox()
            s.setRange(0, 9.99)
            s.setDecimals(3)
            s.setSuffix("  (доля)")
            s.setValue(default)
            s.setFixedWidth(145)
            return s

        left = QFormLayout()
        left.setSpacing(8)
        left.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._labor_overhead_spin = pct_spin(DEFAULT_LABOR_OVERHEAD)
        self._shop_overhead_spin = pct_spin(DEFAULT_SHOP_OVERHEAD)
        left.addRow("Соц. отчисления:", self._labor_overhead_spin)
        left.addRow("Цеховые расходы:", self._shop_overhead_spin)
        params_layout.addLayout(left)

        right = QFormLayout()
        right.setSpacing(8)
        right.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._factory_overhead_spin = pct_spin(DEFAULT_FACTORY_OVERHEAD)
        self._profit_spin = pct_spin(DEFAULT_PROFIT_MARGIN)
        right.addRow("Общезаводские расходы:", self._factory_overhead_spin)
        right.addRow("Рентабельность:", self._profit_spin)

        # v8: режим времени — по плану / по факту из RouteStep.
        self._time_mode = QComboBox()
        self._time_mode.addItem('по плановой T-шт.', TIME_MODE_PLAN)
        self._time_mode.addItem('по факту (из журналов)', TIME_MODE_ACTUAL)
        self._time_mode.setToolTip(
            'План — нормы T-шт. из операций.\n'
            'Факт — среднее время операции по реальным RouteStep '
            '(если уже есть выполненные шаги, иначе fallback на план).\n'
            '«Факт» НЕ сохраняется в базу, чтобы не затирать плановый '
            'расчёт — это разовый снимок «как было».'
        )
        right.addRow("Время операций:", self._time_mode)
        params_layout.addLayout(right)

        calc_btn = QPushButton("  Рассчитать  ")
        calc_btn.setFixedHeight(40)
        calc_btn.clicked.connect(self._calculate)
        calc_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white;
                border: none; border-radius: 4px;
                font-weight: bold; font-size: 13px; padding: 0 16px;
            }
            QPushButton:hover { background-color: #229954; }
        """)
        params_layout.addWidget(calc_btn)
        layout.addWidget(params_group)

        # Таблица статей себестоимости
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Статья затрат", "Сумма, руб", "Доля, %"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, 130)
        self._table.setColumnWidth(2, 90)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        # Итоги
        totals_group = QGroupBox("Итоговые показатели")
        tg_layout = QHBoxLayout(totals_group)

        self._total_labels = {}
        totals = [
            ('production_cost', 'Производственная\nсебестоимость', '#2c3e50'),
            ('full_cost',       'Полная\nсебестоимость', '#8e44ad'),
            ('price',           'Цена\n(с рентабельностью)', '#27ae60'),
            ('profit',          'Прибыль', '#e67e22'),
        ]
        for key, label, color in totals:
            vl = QVBoxLayout()
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 11px; color: #555;")
            val = QLabel("—")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_font = QFont()
            val_font.setPointSize(14)
            val_font.setBold(True)
            val.setFont(val_font)
            val.setStyleSheet(f"color: {color};")
            vl.addWidget(lbl)
            vl.addWidget(val)
            self._total_labels[key] = val
            tg_layout.addLayout(vl)
            if key != 'profit':
                line = QFrame()
                line.setFrameShape(QFrame.Shape.VLine)
                line.setStyleSheet("color: #bdc3c7;")
                tg_layout.addWidget(line)

        layout.addWidget(totals_group)

    def _calculate(self):
        session = self.db_manager.Session()
        try:
            calc = CostCalculator(session)
            mode = (self._time_mode.currentData() or TIME_MODE_PLAN)
            persist = (mode == TIME_MODE_PLAN)
            result = calc.calculate_full_cost(
                tech_process_id=self.tp_id,
                labor_overhead=self._labor_overhead_spin.value(),
                shop_overhead=self._shop_overhead_spin.value(),
                factory_overhead=self._factory_overhead_spin.value(),
                profit_margin=self._profit_spin.value(),
                time_mode=mode,
                persist=persist,
            )
            if persist:
                session.commit()
            self._display_result(result, mode=mode)
        except Exception as e:
            session.rollback()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка расчёта",
                                 f"Не удалось выполнить расчёт:\n{e}\n\n"
                                 "Убедитесь, что в операциях указаны профессии и нормы времени,\n"
                                 "а в нормировании — нормы расхода материалов.")
        finally:
            session.close()

    def _display_result(self, result, mode: str = TIME_MODE_PLAN):
        self._table.setRowCount(0)
        full_cost = result.full_cost or 1.0
        suffix = ' (по факту)' if mode == TIME_MODE_ACTUAL else ''

        for field, label in COST_ROWS:
            value = getattr(result, field, 0) or 0
            pct = (value / full_cost * 100) if full_cost > 0 else 0

            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(label))
            self._table.setItem(row, 1, QTableWidgetItem(f"{value:,.2f}"))
            self._table.setItem(row, 2, QTableWidgetItem(f"{pct:.1f}%"))

            for col in range(3):
                item = self._table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | (
                        Qt.AlignmentFlag.AlignLeft if col == 0
                        else Qt.AlignmentFlag.AlignRight
                    ))

        # Итого строка
        row = self._table.rowCount()
        self._table.insertRow(row)
        total_item = QTableWidgetItem("ИТОГО (производственная с/с)")
        total_item.setFont(QFont('', -1, QFont.Weight.Bold))
        self._table.setItem(row, 0, total_item)
        pc_item = QTableWidgetItem(f"{result.production_cost:,.2f}")
        pc_item.setFont(QFont('', -1, QFont.Weight.Bold))
        self._table.setItem(row, 1, pc_item)
        self._table.setItem(row, 2, QTableWidgetItem("100%"))

        for col in range(3):
            item = self._table.item(row, col)
            if item:
                item.setBackground(QColor('#ecf0f1'))

        # Итоги
        self._total_labels['production_cost'].setText(
            f"{result.production_cost:,.2f} ₽{suffix}")
        self._total_labels['full_cost'].setText(
            f"{result.full_cost:,.2f} ₽{suffix}")
        self._total_labels['price'].setText(
            f"{result.price:,.2f} ₽{suffix}")
        self._total_labels['profit'].setText(
            f"{result.profit:,.2f} ₽{suffix}")

    def _try_load_existing(self):
        from database.models import CostCalculation
        session = self.db_manager.Session()
        try:
            result = session.query(CostCalculation).filter_by(
                tech_process_id=self.tp_id
            ).first()
            if result:
                self._display_result(result)
        finally:
            session.close()
