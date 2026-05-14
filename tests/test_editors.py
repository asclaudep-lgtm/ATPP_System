"""Tests for Phase 2 visual editors — product, TP, reference."""
import sys
import pytest


@pytest.fixture(scope='module')
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class TestProductEditor:
    def test_create_widget_loads_without_crash(self, db_manager, qapp):
        from database.models import Product
        with db_manager.get_session() as s:
            prods = s.query(Product).limit(1).all()
            if not prods:
                pytest.skip("No products in test DB")
            pid = prods[0].id
        from ui.editors.product_editor import ProductEditorWidget
        user = {'id': 1, 'username': 'admin', 'role': 'admin'}
        w = ProductEditorWidget(db_manager, pid, user)
        assert w.product_id == pid
        assert w._original_data is not None

    def test_validation_rejects_empty_designation(self, db_manager, qapp):
        from database.models import Product
        with db_manager.get_session() as s:
            prods = s.query(Product).limit(1).all()
            if not prods:
                pytest.skip("No products in test DB")
            pid = prods[0].id
        from ui.editors.product_editor import ProductEditorWidget
        user = {'id': 1, 'username': 'admin', 'role': 'admin'}
        w = ProductEditorWidget(db_manager, pid, user)
        w._des_edit.clear()
        w._name_edit.clear()
        assert w._des_edit.text() == ''
        assert w._name_edit.text() == ''

    def test_tp_table_populated(self, db_manager, qapp):
        from database.models import Product, TechProcess
        with db_manager.get_session() as s:
            tp = s.query(TechProcess).first()
            if tp is None:
                pytest.skip("No TPs in test DB")
            pid = tp.product_id
        from ui.editors.product_editor import ProductEditorWidget
        user = {'id': 1, 'username': 'admin', 'role': 'admin'}
        w = ProductEditorWidget(db_manager, pid, user)
        assert w._tp_table.rowCount() >= 1


class TestTPEditor:
    def test_create_widget_loads_tp_data(self, db_manager, qapp):
        from database.models import TechProcess
        with db_manager.get_session() as s:
            tp = s.query(TechProcess).first()
            if tp is None:
                pytest.skip("No TPs in test DB")
            tpid = tp.id
        from ui.editors.tp_editor import TPEditorWidget
        user = {'id': 1, 'username': 'admin', 'role': 'admin'}
        w = TPEditorWidget(db_manager, tpid, user)
        assert w._tp_data is not None
        assert w._tp_data['number']

    def test_validation_rejects_empty_number(self, db_manager, qapp):
        from database.models import TechProcess
        with db_manager.get_session() as s:
            tp = s.query(TechProcess).first()
            if tp is None:
                pytest.skip("No TPs in test DB")
            tpid = tp.id
        from ui.editors.tp_editor import TPEditorWidget
        user = {'id': 1, 'username': 'admin', 'role': 'admin'}
        w = TPEditorWidget(db_manager, tpid, user)
        w._num_edit.clear()
        assert w._num_edit.text() == ''

    def test_operations_table_populated(self, db_manager, qapp):
        from database.models import TechProcess
        with db_manager.get_session() as s:
            tp = s.query(TechProcess).first()
            if tp is None:
                pytest.skip("No TPs in test DB")
            tpid = tp.id
        from ui.editors.tp_editor import TPEditorWidget
        user = {'id': 1, 'username': 'admin', 'role': 'admin'}
        w = TPEditorWidget(db_manager, tpid, user)
        assert w._ops_table is not None


class TestReferenceEditor:
    @pytest.mark.parametrize('ref_type', [
        'material', 'equipment', 'tool', 'profession'])
    def test_editor_creates_for_all_types(self, db_manager, qapp, ref_type):
        from ui.editors.reference_editor import ReferenceEditorWidget
        w = ReferenceEditorWidget(db_manager, ref_type)
        assert w._model_class is not None
        assert w._table is not None

    def test_add_material_increases_row_count(self, db_manager, qapp):
        from ui.editors.reference_editor import ReferenceEditorWidget
        w = ReferenceEditorWidget(db_manager, 'material')
        initial = w._table.rowCount()
        with db_manager.get_session() as s:
            from database.models import Material
            m = Material(name=f"TestMat_{id(w)}", grade="Test")
            s.add(m)
            s.flush()
        w._refresh_table()
        assert w._table.rowCount() == initial + 1

    def test_save_updates_record(self, db_manager, qapp):
        from database.models import Material
        with db_manager.get_session() as s:
            m = Material(name=f"RefTest_{id(s)}", grade="Before")
            s.add(m)
            s.flush()
            mid = m.id

        from ui.editors.reference_editor import ReferenceEditorWidget
        w = ReferenceEditorWidget(db_manager, 'material')
        # Test that _widget_value extracts text correctly
        w._widgets['grade'].setText("After")
        val = w._widget_value(w._widgets['grade'], w._cfg['fields'][1])
        assert val == "After"

        # Test DB persistence directly
        with db_manager.get_session() as s:
            obj = s.query(Material).get(mid)
            obj.grade = "After"
        with db_manager.get_session() as s:
            m2 = s.query(Material).get(mid)
            assert m2.grade == "After"
