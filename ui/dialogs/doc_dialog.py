"""
Диалог генерации технологической документации
"""
import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QCheckBox, QPushButton,
    QTextEdit, QMessageBox, QFrame, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from modules.doc_generator import DocumentGenerator


class DocGenerateDialog(QDialog):
    """Диалог генерации технологических документов"""

    def __init__(self, db_manager, tp_id, tp_number, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.tp_id = tp_id
        self.tp_number = tp_number

        self.setWindowTitle(f"Генерация документов — ТП {tp_number}")
        self.setMinimumWidth(480)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel(f"Генерация технологических документов")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        subtitle = QLabel(f"ТП: {self.tp_number}")
        layout.addWidget(subtitle)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        # Формат вывода
        fmt_group = QGroupBox("Формат вывода")
        fmt_layout = QHBoxLayout(fmt_group)
        self.format_combo = QComboBox()
        self.format_combo.addItem("Excel (.xlsx)", "xlsx")
        self.format_combo.addItem("Word (.docx)", "docx")
        self.format_combo.addItem("PDF (.pdf)", "pdf")
        fmt_layout.addWidget(QLabel("Формат:"))
        fmt_layout.addWidget(self.format_combo)
        fmt_layout.addStretch()
        layout.addWidget(fmt_group)

        # Документы
        doc_group = QGroupBox("Документы для генерации")
        doc_layout = QVBoxLayout(doc_group)

        self.check_mk = QCheckBox("Маршрутная карта (МК)  — ГОСТ 3.1109-82")
        self.check_mk.setChecked(True)
        doc_layout.addWidget(self.check_mk)

        self.check_ok = QCheckBox("Операционная карта (ОК)  — ГОСТ 3.1118-82")
        doc_layout.addWidget(self.check_ok)

        self.check_spec = QCheckBox("Ведомость материалов / Спецификация")
        doc_layout.addWidget(self.check_spec)

        layout.addWidget(doc_group)

        # Лог
        log_group = QGroupBox("Журнал генерации")
        log_layout = QVBoxLayout(log_group)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(140)
        self.log_edit.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        log_layout.addWidget(self.log_edit)
        layout.addWidget(log_group)

        # Кнопки
        btn_layout = QHBoxLayout()

        self.gen_btn = QPushButton("  Сгенерировать  ")
        self.gen_btn.clicked.connect(self._generate)

        self.open_folder_btn = QPushButton("Открыть папку")
        self.open_folder_btn.clicked.connect(self._open_export_folder)
        self.open_folder_btn.setEnabled(False)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.gen_btn)
        btn_layout.addWidget(self.open_folder_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._export_dir = None

    def _log(self, msg):
        self.log_edit.append(msg)

    def _generate(self):
        if not self.check_mk.isChecked() and not self.check_ok.isChecked() and not self.check_spec.isChecked():
            QMessageBox.warning(self, "Выбор", "Выберите хотя бы один документ для генерации")
            return

        fmt = self.format_combo.currentData()
        self.gen_btn.setEnabled(False)
        self.log_edit.clear()
        self._log(f"Формат: {self.format_combo.currentText()}")
        self._log(f"ТП: {self.tp_number}")
        self._log("─" * 40)

        session = self.db_manager.Session()
        try:
            generator = DocumentGenerator(session)

            if self.check_mk.isChecked():
                self._log("Генерация маршрутной карты...")
                try:
                    path = generator.generate_route_card(self.tp_id, fmt)
                    self._log(f"  ✓  МК сохранена: {path.name}")
                    self._export_dir = path.parent
                    self.open_folder_btn.setEnabled(True)
                except Exception as e:
                    self._log(f"  ✗  Ошибка МК: {e}")

            if self.check_ok.isChecked():
                self._log("Генерация операционной карты...")
                self._log("  ⓘ  ОК — в разработке (будет добавлена в следующей версии)")

            if self.check_spec.isChecked():
                self._log("Генерация ведомости материалов...")
                self._log("  ⓘ  Спецификация — в разработке")

            self._log("─" * 40)
            self._log("Готово.")
        except Exception as e:
            self._log(f"Критическая ошибка: {e}")
        finally:
            session.close()
            self.gen_btn.setEnabled(True)

    def _open_export_folder(self):
        if self._export_dir and self._export_dir.exists():
            subprocess.Popen(f'explorer "{self._export_dir}"')
