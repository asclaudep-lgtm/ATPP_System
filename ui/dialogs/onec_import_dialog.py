"""Диалог импорта спецификации из 1C (XML/JSON)."""
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class OneCImportDialog(QDialog):
    """Импорт спецификации заказа из 1C XML или JSON."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._file_path = None
        self.setWindowTitle('Импорт из 1С')
        self.setMinimumSize(700, 400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # File selector
        fl = QHBoxLayout()
        self.file_label = QLabel('Файл не выбран')
        fl.addWidget(self.file_label)
        browse_btn = QPushButton('Обзор...')
        browse_btn.clicked.connect(self._browse)
        fl.addWidget(browse_btn)
        layout.addLayout(fl)

        # Preview table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            'Обозначение', 'Наименование', 'Материал'])
        layout.addWidget(self.table)

        # Buttons
        btns = QDialogButtonBox()
        self.import_btn = QPushButton('Импортировать')
        self.import_btn.clicked.connect(self._import)
        self.import_btn.setEnabled(False)
        btns.addButton(self.import_btn,
                       QDialogButtonBox.ButtonRole.AcceptRole)
        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(self.reject)
        btns.addButton(close_btn, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(btns)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите файл спецификации 1С',
            '', '1C Files (*.xml *.json);;XML (*.xml);;JSON (*.json)')
        if not path:
            return
        self._file_path = Path(path)
        self.file_label.setText(path)
        self.import_btn.setEnabled(True)
        self._preview()

    def _preview(self):
        import json
        from xml.etree import ElementTree as ET
        self.table.setRowCount(0)

        suffix = self._file_path.suffix.lower()
        products = []

        try:
            if suffix == '.xml':
                tree = ET.parse(str(self._file_path))
                root = tree.getroot()
                products_el = root.find('Изделия') or root
                for el in products_el.findall('Изделие'):
                    products.append((
                        el.get('Обозначение', ''),
                        el.get('Наименование', ''),
                        el.get('Материал', ''),
                    ))
            elif suffix == '.json':
                data = json.loads(
                    self._file_path.read_text(encoding='utf-8'))
                for p in data.get('products', []):
                    mat = p.get('material', {})
                    products.append((
                        p.get('designation', ''),
                        p.get('name', ''),
                        mat.get('grade', ''),
                    ))
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка',
                                f'Не удалось прочитать файл:\n{e}')
            return

        self.table.setRowCount(len(products))
        for i, (des, name, mat) in enumerate(products):
            self.table.setItem(i, 0, QTableWidgetItem(des))
            self.table.setItem(i, 1, QTableWidgetItem(name))
            self.table.setItem(i, 2, QTableWidgetItem(mat))

    def _import(self):
        if self._file_path is None:
            return
        from modules.onec_exchange import import_specification_json, import_specification_xml

        suffix = self._file_path.suffix.lower()
        try:
            with self.db_manager.get_session() as s:
                if suffix == '.xml':
                    result = import_specification_xml(s, xml_path=self._file_path)
                else:
                    result = import_specification_json(s,
                                                       json_path=self._file_path)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка импорта', str(e))
            return

        msg = (
            f'Создано изделий: {result.created_products}\n'
            f'Обновлено: {result.updated_products}\n'
            f'Пропущено: {result.skipped}'
        )
        if result.errors:
            msg += '\n\nОшибки:\n' + '\n'.join(result.errors)
        QMessageBox.information(self, 'Результат импорта', msg)
        self.accept()
