"""
Браузер шаблонов КТД (Комплект Технологической Документации)
"""
import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.report_generator import ReportGenerator


class KTDBrowserDialog(QDialog):
    """
    Диалог просмотра и открытия шаблонов КТД и отчётов УЗГА
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Библиотека шаблонов КТД")
        self.setMinimumSize(900, 580)
        self.setModal(True)
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Заголовок
        title = QLabel("Библиотека шаблонов технологической документации")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        sub = QLabel("Шаблоны ГОСТ 3.1xxx (КТД) и формы отчётов УЗГА")
        sub.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        layout.addWidget(sub)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #bdc3c7;")
        layout.addWidget(line)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._make_ktd_tab(), "Формы КТД (ГОСТ 3.1xxx)")
        self.tabs.addTab(self._make_reports_tab(), "Ведомости и отчёты")
        layout.addWidget(self.tabs)

        # Подсказка
        hint = QLabel("Двойной клик по строке — открыть шаблон в Word / Excel")
        hint.setStyleSheet("color: #95a5a6; font-size: 10px; padding: 2px;")
        layout.addWidget(hint)

        # Кнопка закрытия
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.setFixedWidth(90)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    # ──────────────────────────────────────────────────────────────
    # Вкладка КТД
    # ──────────────────────────────────────────────────────────────
    def _make_ktd_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)

        info = QLabel(
            "Шаблоны форм комплекта технологической документации согласно ГОСТ 3.1xxx-82/84/85/86.\n"
            "Открываются в Microsoft Word. Содержат стандартные бланки для ручного заполнения."
        )
        info.setStyleSheet("color: #555; font-size: 10px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.ktd_table = QTableWidget()
        self.ktd_table.setColumnCount(5)
        self.ktd_table.setHorizontalHeaderLabels(["ГОСТ", "Документ", "Форма", "Размер", "Файл"])
        self.ktd_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.ktd_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.ktd_table.setColumnWidth(0, 75)
        self.ktd_table.setColumnWidth(2, 180)
        self.ktd_table.setColumnWidth(3, 60)
        self.ktd_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ktd_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ktd_table.setAlternatingRowColors(True)
        self.ktd_table.verticalHeader().setVisible(False)
        self.ktd_table.doubleClicked.connect(self._open_ktd_template)
        layout.addWidget(self.ktd_table)

        btn_layout = QHBoxLayout()
        open_btn = QPushButton("Открыть в Word")
        open_btn.clicked.connect(self._open_ktd_template)
        open_btn.setStyleSheet("QPushButton { background-color: #2980b9; color: white; border: none; padding: 6px 16px; border-radius: 3px; }")
        import_btn = QPushButton("Импорт шаблона...")
        import_btn.clicked.connect(self._import_ktd_template)
        import_btn.setStyleSheet("QPushButton { background-color: #f97316; color: white; border: none; padding: 6px 16px; border-radius: 3px; }")
        import_btn.setToolTip("Добавить свой шаблон .doc/.docx в библиотеку КТД")
        open_folder_btn = QPushButton("Открыть папку")
        open_folder_btn.clicked.connect(self._open_ktd_folder)
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(open_folder_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return w

    # ──────────────────────────────────────────────────────────────
    # Вкладка Отчёты
    # ──────────────────────────────────────────────────────────────
    def _make_reports_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)

        info = QLabel(
            "Формы отчётов и ведомостей УЗГА в формате Excel.\n"
            "Содержат пример данных — открываются для ознакомления или ручного заполнения."
        )
        info.setStyleSheet("color: #555; font-size: 10px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.rep_table = QTableWidget()
        self.rep_table.setColumnCount(3)
        self.rep_table.setHorizontalHeaderLabels(["Наименование отчёта", "Размер", "Файл"])
        self.rep_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.rep_table.setColumnWidth(1, 70)
        self.rep_table.setColumnWidth(2, 240)
        self.rep_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rep_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rep_table.setAlternatingRowColors(True)
        self.rep_table.verticalHeader().setVisible(False)
        self.rep_table.doubleClicked.connect(self._open_report_template)
        layout.addWidget(self.rep_table)

        btn_layout = QHBoxLayout()
        open_btn = QPushButton("Открыть в Excel")
        open_btn.clicked.connect(self._open_report_template)
        open_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border: none; padding: 6px 16px; border-radius: 3px; }")
        import_btn = QPushButton("Импорт шаблона...")
        import_btn.clicked.connect(self._import_report_template)
        import_btn.setStyleSheet("QPushButton { background-color: #f97316; color: white; border: none; padding: 6px 16px; border-radius: 3px; }")
        import_btn.setToolTip("Добавить свой шаблон .xls/.xlsx в библиотеку отчётов")
        open_folder_btn = QPushButton("Открыть папку")
        open_folder_btn.clicked.connect(self._open_reports_folder)
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(open_folder_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        return w

    # ──────────────────────────────────────────────────────────────
    # Загрузка данных
    # ──────────────────────────────────────────────────────────────
    def _load_data(self):
        # КТД шаблоны
        templates = ReportGenerator.list_ktd_templates()
        self.ktd_table.setRowCount(0)
        self._ktd_paths = []
        for tmpl in templates:
            row = self.ktd_table.rowCount()
            self.ktd_table.insertRow(row)
            self._ktd_paths.append(tmpl['path'])

            gost_item = QTableWidgetItem(tmpl['gost'])
            gost_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            gost_item.setForeground(QColor('#2980b9'))
            self.ktd_table.setItem(row, 0, gost_item)
            self.ktd_table.setItem(row, 1, QTableWidgetItem(tmpl['doc_type']))
            self.ktd_table.setItem(row, 2, QTableWidgetItem(tmpl['name']))
            self.ktd_table.setItem(row, 3, QTableWidgetItem(f"{tmpl['size_kb']} КБ"))
            self.ktd_table.setItem(row, 4, QTableWidgetItem(Path(tmpl['path']).suffix.upper()))

        # Отчёты
        reports = ReportGenerator.list_report_templates()
        self.rep_table.setRowCount(0)
        self._rep_paths = []
        for rep in reports:
            row = self.rep_table.rowCount()
            self.rep_table.insertRow(row)
            self._rep_paths.append(rep['path'])
            name = Path(rep['name']).stem  # без расширения
            self.rep_table.setItem(row, 0, QTableWidgetItem(name))
            self.rep_table.setItem(row, 1, QTableWidgetItem(f"{rep['size_kb']} КБ"))
            self.rep_table.setItem(row, 2, QTableWidgetItem(rep['name']))

    # ──────────────────────────────────────────────────────────────
    # Действия
    # ──────────────────────────────────────────────────────────────
    def _open_ktd_template(self):
        row = self.ktd_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Выбор", "Выберите шаблон в таблице")
            return
        path = self._ktd_paths[row] if row < len(self._ktd_paths) else ''
        if path and Path(path).exists():
            try:
                os.startfile(path)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл:\n{e}")
        else:
            QMessageBox.information(
                self, "Генерация документа",
                "Этот документ формируется динамически через диалог генерации.\n"
                "Откройте ТП и нажмите «Документы» в панели навигации, затем добавьте\n"
                "нужную форму в список и нажмите «Сгенерировать»."
            )

    def _open_report_template(self):
        row = self.rep_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Выбор", "Выберите отчёт в таблице")
            return
        path = self._rep_paths[row] if row < len(self._rep_paths) else ''
        if path and Path(path).exists():
            try:
                os.startfile(path)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл:\n{e}")
        else:
            QMessageBox.information(
                self, "Генерация отчёта",
                "Этот отчёт формируется динамически через диалог генерации документов.\n"
                "Откройте ТП и перейдите на вкладку «Документы»."
            )

    def _open_ktd_folder(self):
        folder = Path(__file__).parent.parent.parent / 'resources' / 'templates' / 'ktd'
        if folder.exists():
            subprocess.Popen(f'explorer "{folder}"')

    def _open_reports_folder(self):
        folder = Path(__file__).parent.parent.parent / 'resources' / 'templates' / 'reports'
        if folder.exists():
            subprocess.Popen(f'explorer "{folder}"')

    def _import_ktd_template(self):
        """Импортировать .doc/.docx файл в библиотеку КТД."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт шаблона КТД", "",
            "Шаблоны Word (*.doc *.docx *.dot);;Все файлы (*.*)")
        if not path:
            return
        src = Path(path)
        dst_dir = Path(__file__).parent.parent.parent / 'resources' / 'templates' / 'ktd'
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        if dst.exists():
            ans = QMessageBox.question(
                self, "Файл существует",
                f"Файл '{src.name}' уже есть в библиотеке. Заменить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return
        import shutil
        shutil.copy2(str(src), str(dst))
        self._load_data()
        QMessageBox.information(self, "Готово",
                               f"Шаблон '{src.name}' добавлен в библиотеку КТД")

    def _import_report_template(self):
        """Импортировать .xls/.xlsx файл в библиотеку отчётов."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт шаблона отчёта", "",
            "Книги Excel (*.xls *.xlsx);;Все файлы (*.*)")
        if not path:
            return
        src = Path(path)
        dst_dir = Path(__file__).parent.parent.parent / 'resources' / 'templates' / 'reports'
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        if dst.exists():
            ans = QMessageBox.question(
                self, "Файл существует",
                f"Файл '{src.name}' уже есть в библиотеке. Заменить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return
        import shutil
        shutil.copy2(str(src), str(dst))
        self._load_data()
        QMessageBox.information(self, "Готово",
                               f"Шаблон '{src.name}' добавлен в библиотеку отчётов")
