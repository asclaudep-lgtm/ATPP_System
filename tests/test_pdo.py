"""Tests for PDO module — real UZGA workflow."""

from datetime import date


class TestPDOOrderLifecycle:
    def test_create_order_assigns_status(self, db_manager):
        from modules import pdo_module
        from database.models import Product, Material, PDOStatus

        with db_manager.get_session() as s:
            mat = Material(name="PDO Steel v3", grade="P3")
            s.add(mat); s.flush()
            prod = Product(designation="PDO.TEST.003", name="PDO Part v3",
                           material_id=mat.id)
            s.add(prod); s.flush()

            order = pdo_module.create_order(
                s, product_id=prod.id, qty=5,
                due_date=date.today(), created_by=1,
            )
            assert order.id is not None
            assert order.number.startswith('PDO-')
            assert order.status == PDOStatus.NEW

    def test_full_real_flow(self, db_manager):
        """Test the real UZGA process: NEW→OMTS→TECH_DEPT→DEPUTY→APPROVED."""
        from modules import pdo_module
        from database.models import (Product, Material, TechProcess,
                                      TPStatus, PDOStatus)

        with db_manager.get_session() as s:
            # Setup
            mat = Material(name="PDO Real Steel", grade="PR1")
            s.add(mat); s.flush()
            prod = Product(designation="PDO.REAL.001", name="Real Part",
                           material_id=mat.id)
            s.add(prod); s.flush()
            tp = TechProcess(number="TP-PDO-REAL", product_id=prod.id,
                             status=TPStatus.DRAFT)
            s.add(tp); s.flush()

            # 1. Create order
            order = pdo_module.create_order(
                s, product_id=prod.id, qty=10,
                due_date=date.today(), created_by=1,
                aircraft_type='Ту-204-300',
                nomenclature=[
                    {'designation': '74.88.7103.906.000', 'name': 'Деталь', 'qty': 5},
                    {'designation': '74.88.7103.906.001', 'name': 'Деталь 2', 'qty': 3},
                ],
            )
            assert order.status == PDOStatus.NEW

            # 2. OMTS starts review
            pdo_module.omts_start_review(
                s, order_id=order.id, memo_number='250У от 27.07.2023',
                issued_by=1)
            assert order.status == PDOStatus.OMTS_REVIEW

            # 3. Tech dept review
            pdo_module.tech_dept_review(s, order_id=order.id)
            assert order.status == PDOStatus.TECH_DEPT

            # 4. Set all items feasible
            from database.models import NomenclatureItem
            items = s.query(NomenclatureItem).filter(
                NomenclatureItem.order_id == order.id).all()
            assert len(items) == 2
            for item in items:
                pdo_module.set_feasibility(
                    s, item_id=item.id, feasible=True, kd_ready=True,
                    material_name='Пруток Д16чТ')
            assert pdo_module.check_all_feasible(s, order_id=order.id)

            # 5. Complete tech review → FEASIBLE
            pdo_module.complete_tech_review(s, order_id=order.id)
            assert order.status == PDOStatus.FEASIBLE

            # 6. Deputy approves
            pdo_module.deputy_approve(
                s, order_id=order.id,
                memo_number='356п от 03.08.2023', issued_by=1)
            assert order.status == PDOStatus.DEPUTY_APPROVAL

            # 7. Approve
            pdo_module.approve_order(s, order_id=order.id)
            assert order.status == PDOStatus.APPROVED

    def test_not_feasible_flow(self, db_manager):
        """When one item is not feasible, the order goes to NOT_FEASIBLE."""
        from modules import pdo_module
        from database.models import (Product, Material, PDOStatus,
                                      NomenclatureItem)

        with db_manager.get_session() as s:
            mat = Material(name="PDO Fail Steel", grade="PF1")
            s.add(mat); s.flush()
            prod = Product(designation="PDO.FAIL.001", name="Fail Part",
                           material_id=mat.id)
            s.add(prod); s.flush()

            order = pdo_module.create_order(
                s, product_id=prod.id, qty=3,
                due_date=date.today(), created_by=1,
                nomenclature=[
                    {'designation': 'FAIL.001', 'name': 'Деталь', 'qty': 1},
                ],
            )
            pdo_module.tech_dept_review(s, order_id=order.id)

            items = s.query(NomenclatureItem).filter(
                NomenclatureItem.order_id == order.id).all()
            pdo_module.set_feasibility(
                s, item_id=items[0].id, feasible=False,
                tech_notes='Штамповки, изготовить не можем')

            pdo_module.complete_tech_review(s, order_id=order.id)
            assert order.status == PDOStatus.NOT_FEASIBLE

    def test_get_order_detail_has_nomenclature(self, db_manager):
        from modules import pdo_module
        from database.models import Product, Material

        with db_manager.get_session() as s:
            mat = Material(name="PDO Detail Steel v2", grade="PD2")
            s.add(mat); s.flush()
            prod = Product(designation="PDO.DETAIL.002", name="Detail v2",
                           material_id=mat.id)
            s.add(prod); s.flush()

            order = pdo_module.create_order(
                s, product_id=prod.id, qty=3,
                due_date=date.today(), created_by=1,
                aircraft_type='Ил-76МД',
            )
            pdo_module.omts_start_review(
                s, order_id=order.id,
                memo_number='100У от 01.01.2024', issued_by=1)

            detail = pdo_module.get_order_detail(s, order.id)
            assert detail['number'] == order.number
            assert detail['aircraft_type'] == 'Ил-76МД'
            assert len(detail['memos']) >= 1
