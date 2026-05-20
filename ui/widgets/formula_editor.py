"""Formula editor widget — customise calculation formulas.

Stores user formulas in data/settings.json under the "formulas" key.
Each formula is a Python expression evaluated with a restricted set of
predefined variables (D, L, t, S, n, V, HB, etc.).
"""

import ast
import logging
import math
import operator

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

_logger = logging.getLogger(__name__)

# ——— Safe expression evaluator ———————————————————————————————
# Replaces eval() with a whitelist-based AST walker.
# Only numeric literals, variables, arithmetic operators and
# built-in math functions (abs, min, max, pow, round, sum, sqrt, etc.)

_SAFE_BUILTINS = {
    'abs': abs, 'min': min, 'max': max, 'pow': pow, 'round': round, 'sum': sum,
    'sqrt': math.sqrt, 'log': math.log, 'log10': math.log10,
    'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
    'pi': math.pi, 'e': math.e,
}

_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}

_CMP_OPS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
}


class _FormulaError(Exception):
    pass


def safe_eval(expr: str, variables: dict) -> float:
    """Evaluate a math expression using AST whitelist — no eval()."""
    try:
        tree = ast.parse(expr.strip(), '<formula>', 'eval')
    except SyntaxError:
        raise _FormulaError(f'Синтаксическая ошибка в выражении: {expr}')

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise _FormulaError(f'Недопустимая константа: {node.value}')
        elif isinstance(node, ast.Name):
            if node.id in variables:
                return variables[node.id]
            if node.id in _SAFE_BUILTINS:
                return _SAFE_BUILTINS[node.id]
            raise _FormulaError(f'Неизвестная переменная: {node.id}')
        elif isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            op = _BIN_OPS.get(type(node.op))
            if op is None:
                raise _FormulaError(f'Недопустимый оператор: {type(node.op).__name__}')
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            op = _UNARY_OPS.get(type(node.op))
            if op is None:
                raise _FormulaError(f'Недопустимый унарный оператор: {type(node.op).__name__}')
            return op(_eval(node.operand))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _SAFE_BUILTINS:
                args = [_eval(a) for a in node.args]
                return _SAFE_BUILTINS[node.func.id](*args)
            raise _FormulaError(f'Вызовы разрешены только для: {list(_SAFE_BUILTINS.keys())}')
        elif isinstance(node, ast.Compare):
            left = _eval(node.left)
            for op_node, comp in zip(node.ops, node.comparators):
                right = _eval(comp)
                op = _CMP_OPS.get(type(op_node))
                if op is None:
                    raise _FormulaError('Недопустимое сравнение')
                if not op(left, right):
                    return 0.0
            return 1.0
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result = 1.0
                for v in node.values:
                    if not _eval(v):
                        return 0.0
                return result
            elif isinstance(node.op, ast.Or):
                for v in node.values:
                    if _eval(v):
                        return 1.0
                return 0.0
            raise _FormulaError('Недопустимая булева операция')
        raise _FormulaError(f'Недопустимый элемент выражения: {type(node).__name__}')

    result = _eval(tree)
    return float(result)


# ——— Default formula catalogue ———————————————————————————————————
# Structure: {category: {formula_key: (label, expression, description, vars)}}

DEFAULT_FORMULAS = {
    'Режимы резания': {
        'cutting_speed': (
            'Скорость резания V (м/мин)',
            'Cv / (T**m * t**xv * S**yv) * Kv',
            'V = Cv / (T^m × t^xv × S^yv) × Kv',
            {'Cv': 'Коэффициент', 'T': 'Стойкость, мин', 'm': 'Показатель',
             't': 'Глубина, мм', 'xv': 'Показатель',
             'S': 'Подача, мм/об', 'yv': 'Показатель', 'Kv': 'Поправочный'},
        ),
        'spindle_rpm': (
            'Частота вращения n (об/мин)',
            '1000 * V / (3.14159 * D)',
            'n = 1000 × V / (π × D)',
            {'V': 'Скорость, м/мин', 'D': 'Диаметр, мм'},
        ),
        'feed_per_rev': (
            'Подача S (мм/об)',
            'So * Ks',
            'S = So × Ks',
            {'So': 'Табличная подача', 'Ks': 'Коэффициент условий'},
        ),
    },
    'Нормы времени': {
        't_main_turning': (
            'Основное время — точение',
            '(L + L1 + L2) / (n * S) * i',
            'То = (L + L1 + L2) / (n × S) × i',
            {'L': 'Длина обработки', 'L1': 'Врезание',
             'L2': 'Перебег', 'n': 'Обороты', 'S': 'Подача',
             'i': 'Число проходов'},
        ),
        't_piece': (
            'Штучное время Тшт',
            'To + Tv + Tobs + Totd',
            'Тшт = То + Тв + Тобс + Тотд',
            {'To': 'Основное', 'Tv': 'Вспомогательное',
             'Tobs': 'Обслуживание', 'Totd': 'Отдых'},
        ),
        't_setup': (
            'Подготовительно-заключительное Тпз',
            'Tpz_org + Tpz_nal + Tpz_sn',
            'Тпз = Тпз.орг + Тпз.нал + Тпз.сн',
            {'Tpz_org': 'Организационное',
             'Tpz_nal': 'Наладка', 'Tpz_sn': 'Снятие'},
        ),
    },
    'Материальные нормы': {
        'kim': (
            'Коэффициент использования материала',
            'M_det / M_zag',
            'КИМ = Mдет / Mзаг',
            {'M_det': 'Масса детали', 'M_zag': 'Масса заготовки'},
        ),
        'waste_pct': (
            'Процент отходов',
            '(M_zag - M_det) / M_zag * 100',
            'Отходы% = (Mзаг − Mдет) / Mзаг × 100',
            {'M_zag': 'Масса заготовки', 'M_det': 'Масса детали'},
        ),
        'stock_volume': (
            'Объём заготовки (круг)',
            '3.14159 * D**2 / 4 * L',
            'V = π × D² / 4 × L',
            {'D': 'Диаметр, мм', 'L': 'Длина, мм'},
        ),
    },
    'Себестоимость': {
        'material_cost': (
            'Затраты на материал',
            'M_zag * C_mat / 1000',
            'Смат = Mзаг × Cмат / 1000',
            {'M_zag': 'Масса заготовки, кг', 'C_mat': 'Цена, руб/т'},
        ),
        'labor_cost': (
            'Заработная плата',
            'T_piece * R_hour / 60',
            'Сзп = Тшт × Rчас / 60',
            {'T_piece': 'Тшт, мин', 'R_hour': 'Часовая ставка, руб'},
        ),
        'full_cost': (
            'Полная себестоимость',
            'Cm + Czp + Co + Cceh + Czav',
            'Спол = См + Сзп + Соб + Сцех + Сзав',
            {'Cm': 'Материалы', 'Czp': 'Зарплата', 'Co': 'Оборудование',
             'Cceh': 'Цеховые', 'Czav': 'Заводские'},
        ),
    },
}


class FormulaEditorWidget(QWidget):
    """Tree-based formula catalogue with expression editor."""

    formula_changed = pyqtSignal()

    def __init__(self, db_manager=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._formulas = self._load_formulas()
        self._init_ui()

    def _load_formulas(self):
        """Load formulas from settings, merging with defaults."""
        import copy
        formulas = copy.deepcopy(DEFAULT_FORMULAS)
        try:
            from modules import settings as us
            overrides = us.get('formulas', {})
            for cat, entries in overrides.items():
                if cat in formulas:
                    for key, val in entries.items():
                        if key in formulas[cat]:
                            # val is (label, expression) override
                            old = formulas[cat][key]
                            formulas[cat][key] = (
                                val[0] if len(val) > 0 else old[0],
                                val[1] if len(val) > 1 else old[1],
                                old[2], old[3],
                            )
        except Exception:
            _logger.exception("Unhandled error")
        return formulas

    def _save_formulas(self):
        """Persist overrides to user settings."""
        overrides = {}
        for cat, entries in self._formulas.items():
            for key, (label, expr, desc, vars_dict) in entries.items():
                default = DEFAULT_FORMULAS.get(cat, {}).get(key, ('', '', '', {}))
                if expr != default[1] or label != default[0]:
                    overrides.setdefault(cat, {})[key] = [label, expr]
        try:
            from modules import settings as us
            us.set('formulas', overrides)
        except Exception:
            _logger.exception("Unhandled error")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        hdr = QHBoxLayout()
        title = QLabel('Редактор расчётных формул')
        tf = QFont()
        tf.setPointSize(12)
        tf.setBold(True)
        title.setFont(tf)
        hdr.addWidget(title)
        hdr.addStretch()

        reset_btn = QPushButton('Сбросить на defaults')
        reset_btn.clicked.connect(self._reset_defaults)
        hdr.addWidget(reset_btn)
        layout.addLayout(hdr)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: formula tree
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumWidth(240)
        for cat, entries in self._formulas.items():
            cat_item = QTreeWidgetItem([cat])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            f = cat_item.font(0)
            f.setBold(True)
            cat_item.setFont(0, f)
            for key, (label, expr, desc, vars_dict) in entries.items():
                item = QTreeWidgetItem([label])
                item.setData(0, Qt.ItemDataRole.UserRole, (cat, key))
                cat_item.addChild(item)
            self._tree.addTopLevelItem(cat_item)
            cat_item.setExpanded(True)
        self._tree.currentItemChanged.connect(self._on_select)
        splitter.addWidget(self._tree)

        # Right: editor
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)

        info_grp = QGroupBox('Описание')
        info_lay = QVBoxLayout(info_grp)
        self._desc_label = QLabel('Выберите формулу слева.')
        self._desc_label.setWordWrap(True)
        info_lay.addWidget(self._desc_label)
        rl.addWidget(info_grp)

        vars_grp = QGroupBox('Переменные')
        vars_lay = QVBoxLayout(vars_grp)
        self._vars_label = QLabel('')
        self._vars_label.setWordWrap(True)
        vars_lay.addWidget(self._vars_label)
        rl.addWidget(vars_grp)

        expr_grp = QGroupBox('Формула (Python-выражение)')
        expr_lay = QVBoxLayout(expr_grp)
        self._expr_edit = QLineEdit()
        self._expr_edit.setFont(QFont('Consolas', 10))
        expr_lay.addWidget(self._expr_edit)
        rl.addWidget(expr_grp)

        btn_row = QHBoxLayout()
        test_btn = QPushButton('✓ Проверить')
        test_btn.clicked.connect(self._test_formula)
        btn_row.addWidget(test_btn)
        save_btn = QPushButton('Сохранить')
        save_btn.setStyleSheet(
            'QPushButton { background-color: #27ae60; color: white; '
            'border: none; padding: 6px 16px; border-radius: 4px; }')
        save_btn.clicked.connect(self._save_current)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        rl.addLayout(btn_row)
        splitter.addWidget(right)

        splitter.setSizes([280, 500])
        layout.addWidget(splitter, stretch=1)

    def _on_select(self):
        item = self._tree.currentItem()
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return
        cat, key = data
        label, expr, desc, vars_dict = self._formulas[cat][key]
        self._current_key = (cat, key)
        self._desc_label.setText(desc)
        self._expr_edit.setText(expr)
        vars_text = ', '.join(f'{k} — {v}' for k, v in vars_dict.items())
        self._vars_label.setText(vars_text)

    def _save_current(self):
        if not hasattr(self, '_current_key'):
            return
        cat, key = self._current_key
        old = self._formulas[cat][key]
        self._formulas[cat][key] = (
            old[0], self._expr_edit.text().strip(), old[2], old[3])
        self._save_formulas()
        self.formula_changed.emit()

    def _test_formula(self):
        expr = self._expr_edit.text().strip()
        if not expr:
            QMessageBox.warning(self, 'Проверка', 'Введите выражение.')
            return
        try:
            # Collect variable names via AST
            tree = ast.parse(expr, '<formula>', 'eval')
            var_names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id not in _SAFE_BUILTINS:
                    var_names.add(node.id)
            test_vars = {n: 1.0 for n in var_names}
            result = safe_eval(expr, test_vars)
            QMessageBox.information(
                self, 'Проверка',
                f'Выражение корректно.\n'
                f'Тест с единицами: {result:.3f}')
        except Exception as e:
            QMessageBox.critical(
                self, 'Ошибка', f'Ошибка выражения:\n{e}')

    def _reset_defaults(self):
        reply = QMessageBox.question(
            self, 'Сброс',
            'Вернуть все формулы к заводским настройкам?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        import copy
        self._formulas = copy.deepcopy(DEFAULT_FORMULAS)
        try:
            from modules import settings as us
            us.set('formulas', {})
        except Exception:
            _logger.exception("Unhandled error")
        self.formula_changed.emit()

    def evaluate(self, category: str, key: str, variables: dict) -> float:
        """Evaluate a formula with given variables. Returns float."""
        entry = self._formulas.get(category, {}).get(key)
        if entry is None:
            raise KeyError(f'Formula {category}/{key} not found')
        expr = entry[1]
        return safe_eval(expr, variables)
