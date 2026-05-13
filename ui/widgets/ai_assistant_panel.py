"""Dock-панель AI-помощника с подсказками при редактировании ТП."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QTableWidget, QTableWidgetItem,
                              QProgressBar)
from PyQt6.QtCore import Qt, QTimer


class AIAssistantPanel(QWidget):
    """Боковая панель AI-помощника."""

    def __init__(self, db_manager, product_id=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.product_id = product_id
        self._suggestion = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel('<b>🧠 AI-помощник</b>'))
        hdr.addStretch()
        self.refresh_btn = QPushButton('↻')
        self.refresh_btn.setFixedWidth(30)
        self.refresh_btn.clicked.connect(self.refresh_suggestions)
        hdr.addWidget(self.refresh_btn)
        layout.addLayout(hdr)

        self.info_label = QLabel(
            'Нажмите «Обновить» для подсказок на основе похожих ТП.')
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.ops_table = QTableWidget()
        self.ops_table.setColumnCount(4)
        self.ops_table.setHorizontalHeaderLabels([
            '№', 'Операция', 'Оборуд.', 'Тшт'])
        self.ops_table.setColumnWidth(0, 35)
        self.ops_table.setColumnWidth(1, 120)
        self.ops_table.setColumnWidth(2, 90)
        self.ops_table.setColumnWidth(3, 45)
        layout.addWidget(self.ops_table)

        self.conf_label = QLabel('')
        self.conf_label.setWordWrap(True)
        layout.addWidget(self.conf_label)

        layout.addStretch()

    def set_product(self, product_id):
        self.product_id = product_id
        self.refresh_suggestions()

    def refresh_suggestions(self):
        if self.product_id is None:
            return
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

        try:
            from modules.ai_assistant import suggest_operations
            with self.db_manager.get_session() as s:
                ops = suggest_operations(s, product_id=self.product_id,
                                         similar_count=3)
            self._suggestion = ops

            self.ops_table.setRowCount(len(ops))
            for i, op in enumerate(ops):
                self.ops_table.setItem(i, 0, QTableWidgetItem(
                    op.operation_number))
                self.ops_table.setItem(i, 1, QTableWidgetItem(
                    op.operation_name))
                self.ops_table.setItem(i, 2, QTableWidgetItem(
                    op.equipment_name[:15] if op.equipment_name else ''))
                self.ops_table.setItem(i, 3, QTableWidgetItem(
                    f'{op.t_piece:.1f}'))

            if ops:
                avg_conf = sum(o.confidence for o in ops) / len(ops)
                self.conf_label.setText(
                    f'Уверенность: {avg_conf * 100:.0f}% '
                    f'(на основе {len(ops)} операций)')
                self.info_label.setText(
                    f'Найдено {sum(1 for o in ops if o.confidence > 0.5)} '
                    f'надёжных подсказок.')
            else:
                self.conf_label.setText('Нет похожих ТП для анализа.')
                self.info_label.setText('Недостаточно данных.')

        except Exception as e:
            self.info_label.setText(f'Ошибка: {e}')
        finally:
            self.progress.setVisible(False)
