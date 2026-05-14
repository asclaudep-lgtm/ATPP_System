"""Integration tests — end-to-end workflows across multiple modules."""

import pytest
from pathlib import Path


class TestProductToMKWorkflow:
    """Create Product → TP → Operations → Material norms → cost → doc."""

    def test_full_workflow_creates_valid_mk(self, db_manager):
        from database.models import (
            Product, TechProcess, Operation, Material,
            MaterialNorm, TPStatus, TPType, TechnologyType,
        )
        from modules.doc_generator import DocumentGenerator
        # 1. Create Product
        with db_manager.get_session() as s:
            mat = Material(name="Integration Steel", grade="45X",
                           gost="ГОСТ 1050-88", density=7850,
                           price_per_kg=120.0)
            s.add(mat)
            s.flush()

            prod = Product(
                designation="INTEG.TEST.001",
                name="Integration Test Part",
                material_id=mat.id, mass=5.0,
                dimensions="100x50x30", blank_type="Лист",
            )
            s.add(prod)
            s.flush()
            pid = prod.id

            # 2. Create TP
            tp = TechProcess(
                number="ТП-INTEG-001", product_id=pid,
                tp_type=TPType.SINGLE,
                technology_type=TechnologyType.MACHINING,
                status=TPStatus.DRAFT, version="1.0",
            )
            s.add(tp)
            s.flush()
            tpid = tp.id

            # 3. Add operations
            op1 = Operation(number="005", name="Токарная",
                            tech_process_id=tpid,
                            t_piece=12.0, t_setup=30.0, shop="Цех 1")
            s.add(op1)
            op2 = Operation(number="010", name="Фрезерная",
                            tech_process_id=tpid,
                            t_piece=8.0, t_setup=20.0, shop="Цех 2")
            s.add(op2)
            s.flush()

            # 4. Material norm
            norm = MaterialNorm(
                tech_process_id=tpid, material_id=mat.id,
                norm_per_piece=6.0, waste_percent=15.0,
                cost_per_piece=720.0,
            )
            s.add(norm)
            s.flush()

            # 5. Generate route card
            gen = DocumentGenerator(s)
            mk_path = gen.generate_route_card(tpid, 'xlsx')

        # 7. Verify file
        assert mk_path.exists()
        assert mk_path.suffix == '.xlsx'
        assert mk_path.stat().st_size > 100  # Not empty

    def test_product_to_tp_to_operation_card(self, db_manager):
        from database.models import (
            Product, TechProcess, Operation, Material, TPStatus,
        )
        from modules.doc_generator import DocumentGenerator

        with db_manager.get_session() as s:
            # Setup
            mat = Material(name="OK Test Steel", grade="ST3")
            s.add(mat); s.flush()
            prod = Product(designation="OK.TEST.001", name="OK Part",
                           material_id=mat.id, mass=3.0)
            s.add(prod); s.flush()
            tp = TechProcess(number="ТП-OK-TEST", product_id=prod.id,
                             status=TPStatus.DRAFT)
            s.add(tp); s.flush()
            op = Operation(number="005", name="Test Op",
                           tech_process_id=tp.id, t_piece=5.0, t_setup=10.0)
            s.add(op); s.flush()

            # Generate OK for each operation
            gen = DocumentGenerator(s)
            ok_paths = gen.generate_all_operation_cards(tp.id, 'xlsx')

        assert len(ok_paths) >= 1
        for p in ok_paths:
            assert p.exists()
            assert p.suffix == '.xlsx'


class TestBOMToNestingWorkflow:
    """Create product with BOM → import BOM to nesting → calculate layout."""

    def test_bom_to_nesting_layout(self, db_manager):
        from database.models import (
            Product, Material, BOMItem, TPStatus, TechProcess,
        )
        from modules.pdm_integration import export_bom_json
        import json

        with db_manager.get_session() as s:
            mat = Material(name="BOM Nest Steel", grade="NS1")
            s.add(mat); s.flush()

            root = Product(
                designation="BOM.ROOT.001", name="Root Assembly",
                material_id=mat.id, mass=10.0, dimensions="500x300",
            )
            s.add(root); s.flush()

            child1 = Product(
                designation="BOM.CHILD.001", name="Child Part 1",
                material_id=mat.id, mass=2.0, dimensions="100x80",
            )
            s.add(child1); s.flush()
            child2 = Product(
                designation="BOM.CHILD.002", name="Child Part 2",
                material_id=mat.id, mass=1.5, dimensions="80x60",
            )
            s.add(child2); s.flush()

            s.add(BOMItem(product_id=root.id, quantity=1))
            s.flush()
            root_bom = s.query(BOMItem).filter(
                BOMItem.product_id == root.id).first()
            s.add(BOMItem(parent_id=root_bom.id, product_id=child1.id,
                          quantity=2))
            s.add(BOMItem(parent_id=root_bom.id, product_id=child2.id,
                          quantity=4))
            s.flush()

            # Export BOM to JSON
            bom_json = export_bom_json(s, root.id)

        assert bom_json['designation'] == 'BOM.ROOT.001'
        assert len(bom_json['children']) == 2
        child_designations = [c['designation'] for c in bom_json['children']]
        assert 'BOM.CHILD.001' in child_designations
        assert 'BOM.CHILD.002' in child_designations


class TestSketchVersioningWorkflow:
    """Add sketch → add version → verify versions."""

    def test_sketch_versioning_roundtrip(self, db_manager, tmp_path):
        from modules.sketch_versioning import (
            add_sketch_version, get_sketch_versions,
            restore_sketch_version, delete_sketch_version,
        )
        from database.models import Product, TechProcess, Operation
        from database.models import Material, TPStatus

        with db_manager.get_session() as s:
            # Create a TP with an operation
            mat = Material(name="Sketch Steel", grade="SV1")
            s.add(mat); s.flush()
            prod = Product(designation="SKETCH.TEST.001", name="Sketch Part",
                           material_id=mat.id)
            s.add(prod); s.flush()
            tp = TechProcess(number="TP-SKETCH", product_id=prod.id,
                             status=TPStatus.DRAFT)
            s.add(tp); s.flush()
            op = Operation(number="005", name="Sketch Op",
                           tech_process_id=tp.id)
            s.add(op); s.flush()

            # Create a dummy sketch file
            img = tmp_path / "test_sketch.png"
            img.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 20)

            # Add first version
            sk1 = add_sketch_version(
                s, operation_id=op.id, file_path=img,
                title="Initial sketch", file_type="image",
            )
            assert sk1.id is not None
            assert sk1.sort_order == 1

            # Add second version
            sk2 = add_sketch_version(
                s, operation_id=op.id, file_path=img,
                title="Updated sketch", file_type="image",
            )
            assert sk2.sort_order == 2

            # List versions
            versions = get_sketch_versions(s, op.id)
            assert len(versions) == 2

            # Delete first version
            ok = delete_sketch_version(s, sk1.id)
            assert ok is True

            versions = get_sketch_versions(s, op.id)
            assert len(versions) == 1
