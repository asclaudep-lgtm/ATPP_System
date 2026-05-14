"""Tests for Phase 3 GOST document generators — OK, sketch card, tooling list, doc pack."""
import pytest


@pytest.fixture
def seeded_tp_id(db_manager):
    """Ensure at least one TP with an operation exists in the test DB."""
    from database.models import (
        Product, TechProcess, Operation, Material, TPStatus,
    )
    with db_manager.get_session() as s:
        tp = s.query(TechProcess).first()
        if tp is not None:
            return tp.id

        m = Material(name="TestSteel", grade="45", gost="ГОСТ 1050-88")
        s.add(m)
        s.flush()
        p = Product(designation="TEST.001", name="Test Part",
                    material_id=m.id, mass=1.5)
        s.add(p)
        s.flush()
        tp = TechProcess(number="ТП-TEST-001", product_id=p.id,
                         status=TPStatus.DRAFT, author_id=1)
        s.add(tp)
        s.flush()
        op = Operation(number="005", name="Test Operation",
                       tech_process_id=tp.id, t_piece=5.0, t_setup=10.0)
        s.add(op)
        return tp.id


class TestOperationCards:
    def test_generate_all_ok_creates_files(self, db_manager, seeded_tp_id):
        from modules.doc_generator import DocumentGenerator
        gen = DocumentGenerator(db_manager.Session())
        files = gen.generate_all_operation_cards(seeded_tp_id, 'xlsx')
        assert len(files) >= 1
        for f in files:
            assert f.exists()
            assert f.suffix == '.xlsx'

    def test_generate_single_ok_creates_file(self, db_manager, seeded_tp_id):
        from database.models import Operation
        from modules.doc_generator import DocumentGenerator
        with db_manager.get_session() as s:
            op = s.query(Operation).first()
            assert op is not None
            opid = op.id

        gen = DocumentGenerator(db_manager.Session())
        f = gen.generate_operation_card(opid, 'xlsx')
        assert f.exists()
        assert f.suffix == '.xlsx'


class TestSketchCard:
    def test_generate_sketch_card_creates_file(self, db_manager, seeded_tp_id):
        from modules.doc_generator import DocumentGenerator
        gen = DocumentGenerator(db_manager.Session())
        f = gen.generate_sketch_card(seeded_tp_id, 'xlsx')
        assert f.exists()
        assert f.suffix == '.xlsx'


class TestToolingList:
    def test_generate_tooling_list_creates_file(self, db_manager, seeded_tp_id):
        from modules.doc_generator import DocumentGenerator
        gen = DocumentGenerator(db_manager.Session())
        f = gen.generate_tooling_list(seeded_tp_id, 'xlsx')
        assert f.exists()
        assert f.suffix == '.xlsx'


class TestDocumentPack:
    def test_generate_pack_creates_zip(self, db_manager, seeded_tp_id):
        from modules.doc_generator import DocumentGenerator
        gen = DocumentGenerator(db_manager.Session())
        files = gen.generate_document_pack(seeded_tp_id)
        assert len(files) >= 2
        for f in files:
            assert f.exists()
        zip_path = files[-1]
        assert zip_path.suffix == '.zip'


class TestMaterialList:
    def test_generate_material_list_is_alias(self, db_manager, seeded_tp_id):
        from modules.doc_generator import DocumentGenerator
        gen = DocumentGenerator(db_manager.Session())
        f = gen.generate_material_list(seeded_tp_id, 'xlsx')
        assert f.exists()
        assert f.suffix == '.xlsx'
