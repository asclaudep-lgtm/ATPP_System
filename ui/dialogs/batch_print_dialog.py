"""Batch print dialog — select multiple TPs and generate all route cards at once."""

import zipfile
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QProgressBar, QMessageBox, QFileDialog,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont


class BatchPrintWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)  # path to ZIP

    def __init__(self, db_manager, tp_ids):
        super().__init__()
        self.db_manager = db_manager
        self.tp_ids = tp_ids

    def run(self):
        from modules.doc_generator import DocumentGenerator
        from config import EXPORT_DIR

        files = []
        total = len(self.tp_ids)
        for i, tpid in enumerate(self.tp_ids):
            try:
                with self.db_manager.get_session() as s:
                    gen = DocumentGenerator(s)
                    f = gen.generate_route_card(tpid, 'xlsx')
                    files.append(f)
                self.progress.emit(i + 1, f'OK: {f.name}')
            except Exception as e:
                self.progress.emit(i + 1, f'ERR: {e}')

        if not files:
            self.finished.emit('')
            return

        zip_path = EXPORT_DIR / f'batch_mk_{total}tps.zip'
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(str(f), f.name)

        self.finished.emit(str(zip_path))


class BatchPrintDialog(QDialog):
    """Select multiple TPs → generate all MK → download ZIP."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle('Пакетная печать МК')
        self.setMinimumSize(700, 500)
        self._all_ids = []
        self._init_ui()
        self._load_tps()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel('Выберите ТП для пакетной генерации маршрутных карт:')
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ['✓', 'Номер ТП', 'Изделие', 'Статус'])
        self._table.setColumnWidth(0, 30)
        self._table.setColumnWidth(1, 150)
        self._table.setColumnWidth(2, 250)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        select_all = QPushButton('Выбрать все')
        select_all.clicked.connect(lambda: self._toggle_all(True))
        btn_row.addWidget(select_all)
        deselect_all = QPushButton('Снять все')
        deselect_all.clicked.connect(lambda: self._toggle_all(False))
        btn_row.addWidget(deselect_all)
        btn_row.addStretch()

        self._generate_btn = QPushButton('▶ Сгенерировать МК для выбранных')
        self._generate_btn.setStyleSheet(
            'QPushButton { background-color: #8e44ad; color: white; '
            'border: none; padding: 8px 16px; border-radius: 4px; }')
        self._generate_btn.clicked.connect(self._start_generation)
        btn_row.addWidget(self._generate_btn)
        layout.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status = QLabel('')
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

    def _load_tps(self):
        from database.models import TechProcess, Product
        with self.db_manager.get_session() as s:
            tps = (s.query(TechProcess)
                   .join(Product)
                   .filter(TechProcess.is_deleted == False)
                   .order_by(TechProcess.number)
                   .limit(500)
                   .all())
            self._table.setRowCount(len(tps))
            for i, tp in enumerate(tps):
                cb = QCheckBox()
                w = QTableWidget()
                self._table.setCellWidget(i, 0, cb)
                self._table.setItem(i, 1, QTableWidgetItem(tp.number))
                prod = tp.product.designation if tp.product else ''
                self._table.setItem(i, 2, QTableWidgetItem(prod))
                status = (tp.status.value
                          if hasattr(tp.status, 'value')
                          else str(tp.status))
                self._table.setItem(i, 3, QTableWidgetItem(status))
                self._all_ids.append(tp.id)

    def _toggle_all(self, checked):
        for i in range(self._table.rowCount()):
            w = self._table.cellWidget(i, 0)
            if isinstance(w, QCheckBox):
                w.setChecked(checked)

    def _start_generation(self):
        selected = []
        for i in range(self._table.rowCount()):
            w = self._table.cellWidget(i, 0)
            if isinstance(w, QCheckBox) and w.isChecked():
                selected.append(self._all_ids[i])

        if not selected:
            QMessageBox.information(self, 'Выбор', 'Выберите хотя бы один ТП.')
            return

        self._generate_btn.setEnabled(False)
        self._progress.setMaximum(len(selected))
        self._progress.setValue(0)
        self._progress.show()

        self._worker = BatchPrintWorker(self.db_manager, selected)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, n, msg):
        self._progress.setValue(n)
        self._status.setText(msg)

    def _on_finished(self, zip_path):
        self._generate_btn.setEnabled(True)
        self._progress.hide()
        if zip_path:
            QMessageBox.information(
                self, 'Готово',
                f'Сгенерировано. Файлы упакованы в ZIP:\n{zip_path}')
            self.accept()
        else:
            QMessageBox.critical(self, 'Ошибка',
                                 'Не удалось сгенерировать ни одного документа.')
