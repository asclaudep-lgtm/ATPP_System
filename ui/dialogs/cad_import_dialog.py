"""Диалог импорта CAD-файла (STEP / Kompas CDW/SPW)."""
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class CadImportDialog(QDialog):
    """Импорт геометрии и атрибутов из CAD-файла."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._file_path = None
        self.setWindowTitle('Импорт из CAD')
        self.setMinimumWidth(500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # File picker
        fl = QHBoxLayout()
        self.file_label = QLabel('Файл не выбран')
        fl.addWidget(self.file_label)
        browse_btn = QPushButton('Выбрать CAD-файл...')
        browse_btn.clicked.connect(self._browse)
        fl.addWidget(browse_btn)
        layout.addLayout(fl)

        # Preview
        prev_grp = QGroupBox('Извлечённые данные:')
        prev_lay = QFormLayout(prev_grp)

        self.des_label = QLabel('—')
        prev_lay.addRow('Обозначение:', self.des_label)
        self.mass_label = QLabel('—')
        prev_lay.addRow('Масса, кг:', self.mass_label)
        self.dims_label = QLabel('—')
        prev_lay.addRow('Габариты, мм:', self.dims_label)
        self.volume_label = QLabel('—')
        prev_lay.addRow('Объём, мм³:', self.volume_label)

        layout.addWidget(prev_grp)

        # Target
        tgt_grp = QGroupBox('Целевое изделие:')
        tgt_lay = QHBoxLayout(tgt_grp)
        self.new_rb_label = QLabel(
            'Будет создано новое изделие с обозначением из имени файла.')
        tgt_lay.addWidget(self.new_rb_label)
        layout.addWidget(tgt_grp)

        # Buttons
        btns = QDialogButtonBox()
        import_btn = QPushButton('Импортировать')
        import_btn.clicked.connect(self._import)
        import_btn.setEnabled(False)
        self.import_btn = import_btn
        btns.addButton(import_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = QPushButton('Отмена')
        cancel_btn.clicked.connect(self.reject)
        btns.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(btns)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Выберите CAD-файл', '',
            'CAD Files (*.step *.stp *.cdw *.spw);;'
            'STEP (*.step *.stp);;'
            'Kompas (*.cdw *.spw)')
        if not path:
            return
        self._file_path = Path(path)
        self.file_label.setText(path)

        # Parse and preview
        from modules.cad_import import parse_cdw, parse_spw, parse_step
        suffix = self._file_path.suffix.lower()
        if suffix in ('.step', '.stp'):
            geom = parse_step(self._file_path)
        elif suffix in ('.cdw',):
            geom = parse_cdw(self._file_path)
        else:
            geom = parse_spw(self._file_path)

        designation = self._file_path.stem.strip()
        self.des_label.setText(designation)
        if geom:
            self.mass_label.setText(
                f'{geom.mass_kg:.3f}' if geom.mass_kg else '—')
            self.dims_label.setText(geom.dimensions_mm or '—')
            self.volume_label.setText(
                f'{geom.volume_mm3:.1f}' if geom.volume_mm3 else '—')
        else:
            self.mass_label.setText('— (не удалось извлечь)')
            self.dims_label.setText('—')
            self.volume_label.setText('—')

        self._geom = geom
        self.import_btn.setEnabled(True)

    def _import(self):
        if self._file_path is None:
            return
        from modules.cad_import import import_cad_to_new_product

        try:
            with self.db_manager.get_session() as s:
                result = import_cad_to_new_product(
                    s, file_path=self._file_path)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка импорта', str(e))
            return

        msg = (
            f'Изделие создано:\n'
            f'  Обозначение: {result.designation}\n'
            f'  ID: {result.product_id}'
        )
        if result.warnings:
            msg += '\n\nПредупреждения:\n' + '\n'.join(
                f'• {w}' for w in result.warnings)
        if result.geometry:
            g = result.geometry
            if g.mass_kg:
                msg += f'\n  Масса: {g.mass_kg:.3f} кг'
            if g.dimensions_mm:
                msg += f'\n  Габариты: {g.dimensions_mm} мм'

        QMessageBox.information(self, 'Импорт завершён', msg)
        self.accept()
