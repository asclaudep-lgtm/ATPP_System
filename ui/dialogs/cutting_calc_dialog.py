"""Диалог калькулятора режимов резания."""
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from modules.cutting_calc import (
    MATERIAL_GROUPS,
    OPERATION_TYPES,
    TOOL_MATERIAL,
    calculate_drilling,
    calculate_grinding,
    calculate_milling,
    calculate_turning,
)


class CuttingCalcDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Калькулятор режимов резания')
        self.setMinimumWidth(500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Operation type
        fl = QFormLayout()
        self.op_cb = QComboBox()
        self.op_cb.addItems(OPERATION_TYPES)
        self.op_cb.currentIndexChanged.connect(self._on_op_change)
        fl.addRow('Тип операции:', self.op_cb)

        self.mat_cb = QComboBox()
        self.mat_cb.addItems(list(MATERIAL_GROUPS.keys()))
        fl.addRow('Материал:', self.mat_cb)

        self.tool_cb = QComboBox()
        self.tool_cb.addItems(list(TOOL_MATERIAL.keys()))
        fl.addRow('Материал инструмента:', self.tool_cb)

        self.diam_sb = QDoubleSpinBox()
        self.diam_sb.setRange(0.5, 500)
        self.diam_sb.setValue(50)
        self.diam_sb.setSuffix(' мм')
        fl.addRow('Диаметр:', self.diam_sb)

        self.length_sb = QDoubleSpinBox()
        self.length_sb.setRange(1, 5000)
        self.length_sb.setValue(100)
        self.length_sb.setSuffix(' мм')
        fl.addRow('Длина обработки:', self.length_sb)

        self.depth_sb = QDoubleSpinBox()
        self.depth_sb.setRange(0.01, 20)
        self.depth_sb.setValue(2)
        self.depth_sb.setSuffix(' мм')
        fl.addRow('Глубина / припуск:', self.depth_sb)
        layout.addLayout(fl)

        # Calculate button
        calc_btn = QPushButton('▶ Рассчитать')
        calc_btn.clicked.connect(self._calculate)
        layout.addWidget(calc_btn)

        # Results
        res_grp = QGroupBox('Результаты:')
        res_fl = QFormLayout(res_grp)
        self.lbl_vc = QLabel('—')
        res_fl.addRow('Скорость резания Vc:', self.lbl_vc)
        self.lbl_n = QLabel('—')
        res_fl.addRow('Частота вращения n:', self.lbl_n)
        self.lbl_s = QLabel('—')
        res_fl.addRow('Подача S:', self.lbl_s)
        self.lbl_sm = QLabel('—')
        res_fl.addRow('Подача минутная Sm:', self.lbl_sm)
        self.lbl_power = QLabel('—')
        res_fl.addRow('Мощность резания:', self.lbl_power)
        self.lbl_pz = QLabel('—')
        res_fl.addRow('Сила резания Pz:', self.lbl_pz)
        self.lbl_to = QLabel('—')
        res_fl.addRow('Основное время To:', self.lbl_to)
        layout.addWidget(res_grp)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_op_change(self, idx):
        op = self.op_cb.currentText()
        if op == 'Шлифовальная':
            self.depth_sb.setValue(0.02)
            self.depth_sb.setDecimals(3)
            self.depth_sb.setSingleStep(0.005)
        else:
            self.depth_sb.setValue(2)
            self.depth_sb.setDecimals(1)
            self.depth_sb.setSingleStep(0.5)

    def _calculate(self):
        op = self.op_cb.currentText()
        mat = self.mat_cb.currentText()
        tool = self.tool_cb.currentText()
        d = self.diam_sb.value()
        l = self.length_sb.value()
        t = self.depth_sb.value()

        try:
            if op == 'Токарная':
                r = calculate_turning(diameter=d, length=l, depth=t,
                                      material=mat, tool=tool)
            elif op == 'Фрезерная':
                r = calculate_milling(diameter=d, length=l, depth=t,
                                      material=mat, tool=tool)
            elif op == 'Сверлильная':
                r = calculate_drilling(diameter=d, length=l,
                                       material=mat, tool=tool)
            else:
                r = calculate_grinding(diameter=d, length=l, depth=t,
                                       material=mat)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))
            return

        self.lbl_vc.setText(f'{r.speed_vc} м/мин')
        self.lbl_n.setText(f'{r.spindle_n} об/мин')
        self.lbl_s.setText(
            f'{r.feed_s} мм/зуб' if op == 'Фрезерная'
            else f'{r.feed_s} мм/об')
        self.lbl_sm.setText(f'{r.feed_min} мм/мин')
        self.lbl_power.setText(f'{r.power_n} кВт')
        self.lbl_pz.setText(f'{r.force_pz} Н' if r.force_pz > 0 else '—')
        self.lbl_to.setText(f'{r.main_time} мин')
