"""
Диалог создания и редактирования перехода операции
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QDoubleSpinBox, QSpinBox,
    QPushButton, QTextEdit, QMessageBox, QFrame,
    QGroupBox, QWidget, QTabWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import math


class TransitionDialog(QDialog):
    """Диалог создания и редактирования перехода"""

    def __init__(self, transition_data=None, next_number=None,
                 db_manager=None, product_designation: str = '', parent=None):
        super().__init__(parent)
        self.transition_data = transition_data
        self.is_edit = transition_data is not None
        self.next_number = next_number or '1'
        self.db_manager = db_manager
        self.product_designation = product_designation
        self.result_data = None

        self.setWindowTitle("Редактирование перехода" if self.is_edit else "Новый переход")
        self.setMinimumWidth(560)
        self.setMinimumHeight(560)
        self.setModal(True)

        self._init_ui()
        if self.is_edit:
            self._fill_form()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Редактирование перехода" if self.is_edit else "Новый переход")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        tabs = QTabWidget()

        # — Основное —
        main_tab = QWidget()
        mf = QFormLayout(main_tab)
        mf.setSpacing(9)
        mf.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.number_edit = QLineEdit()
        self.number_edit.setText(self.next_number)
        self.number_edit.setFixedWidth(80)
        mf.addRow("№ перехода *:", self.number_edit)

        # v8: текст + кнопка вставки из библиотеки шаблонов.
        text_box = QWidget()
        text_v = QVBoxLayout(text_box)
        text_v.setContentsMargins(0, 0, 0, 0)
        text_v.setSpacing(3)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Установить и закрепить деталь.\n"
            "Точить пов. 1 Ø25h6 на длину 50 мм."
        )
        self.text_edit.setMinimumHeight(100)
        text_v.addWidget(self.text_edit)

        tpl_row = QHBoxLayout()
        tpl_row.setContentsMargins(0, 0, 0, 0)
        tpl_btn = QPushButton('📋 Из шаблона…')
        tpl_btn.setToolTip(
            'Вставить готовую формулировку из библиотеки шаблонов переходов.'
        )
        tpl_btn.clicked.connect(self._pick_from_templates)
        tpl_row.addWidget(tpl_btn)
        tpl_row.addStretch()
        text_v.addLayout(tpl_row)

        mf.addRow("Текст перехода *:", text_box)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("Код перехода...")
        self.code_edit.setFixedWidth(120)
        mf.addRow("Код:", self.code_edit)

        tabs.addTab(main_tab, "Основное")

        # — Режимы обработки —
        params_tab = QWidget()
        pf = QFormLayout(params_tab)
        pf.setSpacing(9)
        pf.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def make_spin(suffix='', decimals=2, max_val=99999.0):
            s = QDoubleSpinBox()
            s.setRange(0, max_val)
            s.setDecimals(decimals)
            if suffix:
                s.setSuffix(f" {suffix}")
            s.setFixedWidth(140)
            return s

        self.diameter_spin = make_spin("мм")
        pf.addRow("Диаметр D:", self.diameter_spin)

        self.length_spin = make_spin("мм")
        pf.addRow("Длина L:", self.length_spin)

        self.depth_spin = make_spin("мм")
        pf.addRow("Глубина резания t:", self.depth_spin)

        self.feed_spin = make_spin("мм/об", 3)
        pf.addRow("Подача S:", self.feed_spin)

        self.speed_spin = make_spin("м/мин", 1)
        pf.addRow("Скорость V:", self.speed_spin)

        self.rpm_spin = make_spin("об/мин", 0)
        pf.addRow("Частота вращения n:", self.rpm_spin)

        self.passes_spin = QSpinBox()
        self.passes_spin.setRange(1, 999)
        self.passes_spin.setValue(1)
        self.passes_spin.setFixedWidth(100)
        pf.addRow("Число проходов i:", self.passes_spin)

        # Кнопки расчёта
        calc_row = QHBoxLayout()
        calc_rpm_btn = QPushButton("n по V и D")
        calc_rpm_btn.setToolTip("Рассчитать частоту вращения по скорости и диаметру")
        calc_rpm_btn.clicked.connect(self._calc_rpm)
        calc_rpm_btn.setStyleSheet("QPushButton { padding: 4px 10px; }")

        calc_v_btn = QPushButton("V по n и D")
        calc_v_btn.setToolTip("Рассчитать скорость по частоте и диаметру")
        calc_v_btn.clicked.connect(self._calc_speed)
        calc_v_btn.setStyleSheet("QPushButton { padding: 4px 10px; }")

        calc_t_btn = QPushButton("То по режимам")
        calc_t_btn.setToolTip(
            "Рассчитать основное время То = L · i / (n · S)\n"
            "L — длина обработки, i — число проходов,\n"
            "n — частота вращения, S — подача."
        )
        calc_t_btn.clicked.connect(self._calc_t_main)

        calc_row.addWidget(calc_rpm_btn)
        calc_row.addWidget(calc_v_btn)
        calc_row.addWidget(calc_t_btn)
        calc_row.addStretch()
        pf.addRow("Расчёт:", calc_row)

        self._t_main_label = QLabel('То не рассчитано')
        self._t_main_label.setStyleSheet('font-style: italic;')
        pf.addRow("", self._t_main_label)

        tabs.addTab(params_tab, "Режимы обработки")

        # — Эскизы —
        if self.db_manager is not None:
            from ui.widgets.sketches_panel import SketchesPanel
            tr_id = (self.transition_data or {}).get('id') if self.is_edit else None
            self.sketches_panel = SketchesPanel(
                self.db_manager,
                parent_kind='transition',
                parent_id=tr_id,
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

        cancel_btn = QPushButton("  Отмена  ")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _calc_rpm(self):
        v = self.speed_spin.value()
        d = self.diameter_spin.value()
        if d > 0 and v > 0:
            n = (1000 * v) / (math.pi * d)
            self.rpm_spin.setValue(round(n))
        else:
            QMessageBox.information(self, "Расчёт", "Введите скорость V и диаметр D")

    def _calc_speed(self):
        n = self.rpm_spin.value()
        d = self.diameter_spin.value()
        if d > 0 and n > 0:
            v = (math.pi * d * n) / 1000
            self.speed_spin.setValue(round(v, 1))
        else:
            QMessageBox.information(self, "Расчёт", "Введите частоту n и диаметр D")

    def _calc_t_main(self):
        """Основное время по режимам резания.

        То = L · i / (n · S)  [мин]
        L — длина обработки (мм), i — число проходов,
        n — об/мин, S — мм/об.
        """
        L = self.length_spin.value()
        i = self.passes_spin.value() or 1
        n = self.rpm_spin.value()
        S = self.feed_spin.value()
        if not (L > 0 and n > 0 and S > 0):
            QMessageBox.information(
                self, 'Расчёт',
                'Для расчёта То нужны: L (длина), n (частота), S (подача).'
            )
            return
        t = (L * i) / (n * S)
        self._t_main_value = round(t, 3)
        self._t_main_label.setText(
            f'То = {self._t_main_value:.3f} мин '
            f'(L={L:g}, i={i}, n={n:g}, S={S:g})'
        )
        self._t_main_label.setStyleSheet('font-weight: bold;')

    def _pick_from_templates(self):
        """v8: Открыть библиотеку шаблонов и вставить выбранный."""
        if self.db_manager is None:
            QMessageBox.information(
                self, 'Шаблоны',
                'Библиотека недоступна вне приложения.'
            )
            return
        from ui.dialogs.transition_templates_dialog import (
            TransitionTemplatesDialog,
        )
        dlg = TransitionTemplatesDialog(
            self.db_manager, pick_mode=True, parent=self
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        tpl = dlg.selected_template
        if not tpl:
            return
        # Вставляем в текущую позицию курсора. Если текст пустой —
        # заменяем целиком.
        cur_text = self.text_edit.toPlainText().strip()
        if not cur_text:
            self.text_edit.setPlainText(tpl.get('text', ''))
        else:
            self.text_edit.insertPlainText(tpl.get('text', ''))
        if tpl.get('code') and not self.code_edit.text().strip():
            self.code_edit.setText(tpl['code'])

    def _fill_form(self):
        d = self.transition_data
        self.number_edit.setText(str(d.get('number', '') or ''))
        self.text_edit.setPlainText(d.get('text', '') or '')
        self.code_edit.setText(d.get('code', '') or '')
        self.diameter_spin.setValue(float(d.get('diameter', 0) or 0))
        self.length_spin.setValue(float(d.get('length', 0) or 0))
        self.depth_spin.setValue(float(d.get('depth', 0) or 0))
        self.feed_spin.setValue(float(d.get('feed', 0) or 0))
        self.speed_spin.setValue(float(d.get('speed', 0) or 0))
        self.rpm_spin.setValue(float(d.get('rpm', 0) or 0))
        self.passes_spin.setValue(int(d.get('passes', 1) or 1))

    def _on_save(self):
        number = self.number_edit.text().strip()
        text = self.text_edit.toPlainText().strip()

        if not number:
            QMessageBox.warning(self, "Ошибка", "Укажите номер перехода")
            return
        if not text:
            QMessageBox.warning(self, "Ошибка", "Введите текст перехода")
            return

        self.result_data = {
            'number': number,
            'text': text,
            'code': self.code_edit.text().strip() or None,
            'diameter': self.diameter_spin.value() or None,
            'length': self.length_spin.value() or None,
            'depth': self.depth_spin.value() or None,
            'feed': self.feed_spin.value() or None,
            'speed': self.speed_spin.value() or None,
            'rpm': self.rpm_spin.value() or None,
            'passes': self.passes_spin.value(),
        }
        self.accept()

    def get_data(self):
        return self.result_data
