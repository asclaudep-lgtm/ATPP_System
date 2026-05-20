"""Tests for v7.7-fix: pending-эскизы до сохранения операции/перехода."""
import os

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PyQt6.QtWidgets import QApplication
    import sys
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def dm(tmp_path, monkeypatch):
    monkeypatch.setattr('config.DATA_DIR', tmp_path)
    monkeypatch.setattr('config.SKETCHES_DIR', tmp_path / 'sketches')
    (tmp_path / 'sketches').mkdir()
    from database.db_manager import DatabaseManager
    db = DatabaseManager(f'sqlite:///{tmp_path}/test.db')
    db.init_database()
    return db


@pytest.fixture
def sample_image(tmp_path):
    """Создаём минимальный валидный PNG (1×1 пиксель)."""
    img = tmp_path / 'sample.png'
    # 1×1 чёрный PNG
    png_bytes = bytes.fromhex(
        '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
        '0000000d49444154789c63000100000005000100200a00000000000049454e44ae'
        '426082'
    )
    img.write_bytes(png_bytes)
    return img


def test_pending_accepts_files_without_parent(app, dm, sample_image):
    """Если parent_id=None, _accept_paths кладёт в _pending_paths без падения."""
    from ui.widgets.sketches_panel import SketchesPanel
    panel = SketchesPanel(dm, parent_kind='operation', parent_id=None,
                          product_designation='TEST-001')
    assert panel.has_pending() is False
    panel._accept_paths([str(sample_image)])
    assert panel.has_pending() is True
    assert len(panel._pending_paths) == 1


def test_add_btn_enabled_without_parent(app, dm):
    """Кнопка «Добавить файл…» доступна, даже если родителя ещё нет."""
    from ui.widgets.sketches_panel import SketchesPanel
    panel = SketchesPanel(dm, parent_kind='operation', parent_id=None)
    panel.refresh()
    assert panel._add_btn.isEnabled() is True


def test_flush_pending_creates_sketch_records(app, dm, sample_image):
    """flush_pending_to() — после сохранения операции переносит pending в БД."""
    from database.models import Operation, Product, TechProcess, TPStatus, Sketch
    s = dm.Session()
    try:
        p = Product(designation='PEND-1', name='X')
        s.add(p)
        s.flush()
        tp = TechProcess(number='TP-PEND-1', product_id=p.id, status=TPStatus.DRAFT)
        s.add(tp)
        s.flush()
        op = Operation(tech_process_id=tp.id, number='005', name='Слесарная',
                       sort_order=0)
        s.add(op)
        s.commit()
        op_id = op.id
    finally:
        s.close()

    from ui.widgets.sketches_panel import SketchesPanel
    panel = SketchesPanel(dm, parent_kind='operation', parent_id=None,
                          product_designation='PEND-1')
    panel._accept_paths([str(sample_image)])
    assert panel.has_pending()
    panel.flush_pending_to(op_id)
    assert not panel.has_pending()
    assert panel.parent_id == op_id

    s = dm.Session()
    try:
        records = s.query(Sketch).filter_by(operation_id=op_id).all()
        assert len(records) == 1
        assert records[0].file_type == 'image'
    finally:
        s.close()
