"""Tests for v7.7 model changes (is_default_for_product, is_template)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base, Product, TechProcess, TPStatus,
)


@pytest.fixture
def session():
    eng = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    s = Session()
    yield s
    s.close()


def test_techprocess_has_is_default_column(session):
    """v7.7d: is_default_for_product column exists with default False."""
    cols = {c.name for c in TechProcess.__table__.columns}
    assert 'is_default_for_product' in cols
    assert 'is_template' in cols


def test_techprocess_default_false(session):
    """Новый ТП имеет is_default_for_product=False по умолчанию."""
    p = Product(designation='X-1', name='Test')
    session.add(p)
    session.flush()
    tp = TechProcess(number='TP-1', product_id=p.id, status=TPStatus.DRAFT)
    session.add(tp)
    session.flush()
    assert tp.is_default_for_product is False
    assert tp.is_template is False


def test_one_default_per_product(session):
    """Можно отметить один ТП как default; другие остаются неотмеченными."""
    p = Product(designation='X-2', name='Test')
    session.add(p)
    session.flush()
    tp1 = TechProcess(number='TP-2-1', product_id=p.id, status=TPStatus.DRAFT)
    tp2 = TechProcess(number='TP-2-2', product_id=p.id, status=TPStatus.DRAFT,
                      is_default_for_product=True)
    session.add_all([tp1, tp2])
    session.flush()
    # Проверка
    defaults = (session.query(TechProcess)
                .filter(TechProcess.product_id == p.id,
                        TechProcess.is_default_for_product)
                .all())
    assert len(defaults) == 1
    assert defaults[0].id == tp2.id


def test_group_tree_widget_smoke(tmp_path, monkeypatch):
    """Smoke-test: GroupTreeWidget импортируется и строится без ошибок."""
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PyQt6.QtWidgets import QApplication
    import sys
    QApplication.instance() or QApplication(sys.argv)

    from database.db_manager import DatabaseManager
    db_path = tmp_path / 'test.db'
    dm = DatabaseManager(f'sqlite:///{db_path}')
    dm.init_database()

    from ui.widgets.group_tree import GroupTreeWidget
    w = GroupTreeWidget(dm)
    w.reload()
    # Пустая БД, но виджет должен построиться без ошибок
    assert w.topLevelItemCount() >= 0


def test_product_ktp_widget_with_empty_product(tmp_path, monkeypatch):
    """ProductKTPWidget показывает плейсхолдер для детали без ТП."""
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PyQt6.QtWidgets import QApplication
    import sys
    QApplication.instance() or QApplication(sys.argv)

    from database.db_manager import DatabaseManager
    db_path = tmp_path / 'test.db'
    dm = DatabaseManager(f'sqlite:///{db_path}')
    dm.init_database()

    s = dm.Session()
    try:
        p = Product(designation='UI-001', name='Test part')
        s.add(p)
        s.commit()
        product_id = p.id
    finally:
        s.close()

    from ui.widgets.product_ktp import ProductKTPWidget
    w = ProductKTPWidget(dm, product_id,
                         {'id': 1, 'username': 'admin', 'role': 'admin'})
    assert w._product['designation'] == 'UI-001'
    assert len(w._variants) == 0  # нет ТП → плейсхолдер


def test_tp_compare_dialog_smoke(tmp_path, monkeypatch):
    """TPCompareDialog строится и принимает два TP id."""
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PyQt6.QtWidgets import QApplication
    import sys
    QApplication.instance() or QApplication(sys.argv)

    from database.db_manager import DatabaseManager
    db_path = tmp_path / 'test.db'
    dm = DatabaseManager(f'sqlite:///{db_path}')
    dm.init_database()

    s = dm.Session()
    try:
        p = Product(designation='CMP-1', name='Test')
        s.add(p)
        s.flush()
        tp1 = TechProcess(number='C-1', product_id=p.id, status=TPStatus.DRAFT,
                          execution_variant='Универсальное оборудование')
        tp2 = TechProcess(number='C-2', product_id=p.id, status=TPStatus.DRAFT,
                          execution_variant='ЧПУ')
        s.add_all([tp1, tp2])
        s.commit()
        tp_ids = (tp1.id, tp2.id)
    finally:
        s.close()

    from ui.widgets.tp_compare import TPCompareDialog
    dlg = TPCompareDialog(dm, tp_ids[0], tp_ids[1])
    assert dlg.tbl_left is not None
    assert dlg.tbl_right is not None
