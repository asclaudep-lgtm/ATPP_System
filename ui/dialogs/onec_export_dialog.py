"""Диалог экспорта данных в формат 1C."""
from pathlib import Path

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QCheckBox, QComboBox,
                              QPushButton, QFileDialog, QLabel, QHBoxLayout,
                              QDialogButtonBox, QMessageBox, QGroupBox)


class OneCExportDialog(QDialog):
    """Экспорт себестоимости / сроков / спецификации в 1C."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle('Экспорт в 1С')
        self.setMinimumWidth(450)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Что экспортировать
        what_grp = QGroupBox('Что экспортировать:')
        what_lay = QVBoxLayout(what_grp)
        self.cb_cost = QCheckBox('Данные о себестоимости (XML)')
        self.cb_cost.setChecked(True)
        what_lay.addWidget(self.cb_cost)
        self.cb_timeline = QCheckBox('График выполнения нарядов (XML)')
        what_lay.addWidget(self.cb_timeline)
        self.cb_spec = QCheckBox('Спецификация изделий (XLSX)')
        self.cb_spec.setChecked(True)
        what_lay.addWidget(self.cb_spec)
        layout.addWidget(what_grp)

        # BOM option
        self.cb_bom = QCheckBox('Включить структуру БОМ в спецификацию')
        layout.addWidget(self.cb_bom)

        # Output dir
        dir_lay = QHBoxLayout()
        self.dir_label = QLabel('data/exports/')
        dir_lay.addWidget(self.dir_label)
        dir_btn = QPushButton('Выбрать папку...')
        dir_btn.clicked.connect(self._browse_dir)
        dir_lay.addWidget(dir_btn)
        layout.addLayout(dir_lay)

        # Buttons
        btns = QDialogButtonBox()
        export_btn = QPushButton('Экспортировать')
        export_btn.clicked.connect(self._export)
        btns.addButton(export_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = QPushButton('Отмена')
        cancel_btn.clicked.connect(self.reject)
        btns.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(btns)

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, 'Папка для экспорта')
        if d:
            self.dir_label.setText(d)
            self._out_dir = Path(d)
        else:
            self._out_dir = None

    def _export(self):
        from config import EXPORT_DIR
        from modules.onec_exchange import (export_cost_data,
                                            export_timeline_data,
                                            export_specification_xls_v2)
        self._out_dir = getattr(self, '_out_dir', None) or EXPORT_DIR
        results = []

        try:
            with self.db_manager.get_session() as s:
                if self.cb_cost.isChecked():
                    p = export_cost_data(
                        s, out_path=self._out_dir / '1c_cost.xml')
                    results.append(f'Себестоимость: {p}')
                if self.cb_timeline.isChecked():
                    p = export_timeline_data(
                        s, out_path=self._out_dir / '1c_timeline.xml')
                    results.append(f'График: {p}')
                if self.cb_spec.isChecked():
                    p = export_specification_xls_v2(
                        s, out_path=self._out_dir / '1c_spec.xlsx',
                        include_bom=self.cb_bom.isChecked())
                    results.append(f'Спецификация: {p}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка экспорта', str(e))
            return

        QMessageBox.information(
            self, 'Экспорт завершён',
            'Созданы файлы:\n' + '\n'.join(f'• {r}' for r in results))
        self.accept()
