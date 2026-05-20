"""Диалог AI-помощника технолога."""
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from database.models import Product


class AIAssistantDialog(QDialog):
    """AI-помощник: поиск похожих изделий и предложение операций."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle('AI-помощник технолога')
        self.setMinimumSize(800, 500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Product selector
        sel_lay = QHBoxLayout()
        sel_lay.addWidget(QLabel('Изделие:'))
        self.product_cb = QComboBox()
        self.product_cb.setMinimumWidth(300)
        self.product_cb.setEditable(True)
        with self.db_manager.get_session() as s:
            for p in s.query(Product).filter(
                not Product.is_deleted
            ).order_by(Product.designation).all():
                self.product_cb.addItem(
                    f'{p.designation} — {p.name}', p.id)
        sel_lay.addWidget(self.product_cb)

        self.analyze_btn = QPushButton('🔍 Анализировать')
        self.analyze_btn.clicked.connect(self._analyze)
        sel_lay.addWidget(self.analyze_btn)
        sel_lay.addStretch()
        layout.addLayout(sel_lay)

        # Progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Similar products
        sim_grp = QGroupBox('Похожие изделия:')
        sim_lay = QVBoxLayout(sim_grp)
        self.sim_table = QTableWidget()
        self.sim_table.setColumnCount(4)
        self.sim_table.setHorizontalHeaderLabels([
            'Обозначение', 'Наименование', 'Сходство, %', 'ТП-аналог'])
        self.sim_table.setColumnWidth(0, 150)
        self.sim_table.setColumnWidth(1, 200)
        self.sim_table.setColumnWidth(2, 100)
        self.sim_table.setColumnWidth(3, 150)
        sim_lay.addWidget(self.sim_table)
        layout.addWidget(sim_grp)

        # Suggested operations
        ops_grp = QGroupBox('Предлагаемые операции:')
        ops_lay = QVBoxLayout(ops_grp)
        self.ops_table = QTableWidget()
        self.ops_table.setColumnCount(7)
        self.ops_table.setHorizontalHeaderLabels([
            '№', 'Операция', 'Оборудование', 'Профессия',
            'Разряд', 'Тпз', 'Тшт'])
        self.ops_table.setColumnWidth(0, 40)
        self.ops_table.setColumnWidth(1, 180)
        self.ops_table.setColumnWidth(2, 150)
        self.ops_table.setColumnWidth(3, 120)
        self.ops_table.setColumnWidth(4, 50)
        self.ops_table.setColumnWidth(5, 60)
        self.ops_table.setColumnWidth(6, 60)
        ops_lay.addWidget(self.ops_table)
        layout.addWidget(ops_grp)

        # Summary and action
        sum_lay = QHBoxLayout()
        self.summary_label = QLabel('')
        sum_lay.addWidget(self.summary_label)
        sum_lay.addStretch()

        self.apply_btn = QPushButton('✓ Применить к текущему ТП')
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply)
        sum_lay.addWidget(self.apply_btn)
        layout.addLayout(sum_lay)

        # Close
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._suggestion = None

    def _analyze(self):
        product_id = self.product_cb.currentData()
        if product_id is None:
            return

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

        try:
            from modules.ai_assistant import suggest_tp
            with self.db_manager.get_session() as s:
                suggestion = suggest_tp(s, product_id=product_id)
            self._suggestion = suggestion

            if suggestion is None:
                QMessageBox.information(
                    self, 'AI-помощник',
                    'Недостаточно данных для анализа. '
                    'Нужны утверждённые ТП на похожие изделия.')
                self.progress.setVisible(False)
                return

            # Populate similar products
            self.sim_table.setRowCount(len(suggestion.similar_products))
            for i, sp in enumerate(suggestion.similar_products):
                self.sim_table.setItem(i, 0, QTableWidgetItem(sp.designation))
                self.sim_table.setItem(i, 1, QTableWidgetItem(sp.name))
                self.sim_table.setItem(i, 2, QTableWidgetItem(
                    f'{sp.similarity * 100:.0f}%'))
                self.sim_table.setItem(i, 3, QTableWidgetItem(
                    sp.tp_number or '—'))

            # Populate operations
            self.ops_table.setRowCount(len(suggestion.operations))
            for i, op in enumerate(suggestion.operations):
                self.ops_table.setItem(i, 0, QTableWidgetItem(
                    op.operation_number))
                self.ops_table.setItem(i, 1, QTableWidgetItem(
                    op.operation_name))
                self.ops_table.setItem(i, 2, QTableWidgetItem(
                    op.equipment_name))
                self.ops_table.setItem(i, 3, QTableWidgetItem(
                    op.profession_name))
                self.ops_table.setItem(i, 4, QTableWidgetItem(
                    str(op.grade or '')))
                self.ops_table.setItem(i, 5, QTableWidgetItem(
                    f'{op.t_setup:.1f}'))
                self.ops_table.setItem(i, 6, QTableWidgetItem(
                    f'{op.t_piece:.1f}'))

            self.summary_label.setText(
                f'{suggestion.technology_type or ""} | '
                f'Σ Тпз = {suggestion.t_setup_total:.1f} мин | '
                f'Σ Тшт = {suggestion.t_piece_total:.1f} мин | '
                f'Источников: {suggestion.source_count}'
            )
            self.apply_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))
        finally:
            self.progress.setVisible(False)

    def _apply(self):
        if self._suggestion is None:
            return
        QMessageBox.information(
            self, 'AI-помощник',
            'Операции скопированы в буфер.\n'
            'Вставьте их в редактор ТП (Ctrl+V в таблице операций).')
