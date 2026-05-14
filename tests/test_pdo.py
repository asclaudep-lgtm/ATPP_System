"""Tests for PDO module — order lifecycle."""

import pytest
from datetime import date


class TestPDOOrderLifecycle:
    def test_create_order_assigns_status(self, db_manager):
        from modules import pdo_module
        from database.models import Product, Material

        with db_manager.get_session() as s:
            mat = Material(name="PDO Steel", grade="P1")
            s.add(mat); s.flush()
            prod = Product(designation="PDO.TEST.001", name="PDO Part",
                           material_id=mat.id)
            s.add(prod); s.flush()

            order = pdo_module.create_order(
                s, product_id=prod.id, qty=5,
                due_date=date.today(), created_by=1,
            )
            assert order.id is not None
            assert order.number.startswith('PDO-')
            # New product has no TP → goes to technologist
            assert order.tp_required is True

    def test_full_lifecycle(self, db_manager):
        from modules import pdo_module
        from database.models import (Product, Material, TechProcess,
                                      TPStatus, User)
        from database.models import PDOStatus

        with db_manager.get_session() as s:
            # Ensure technologist user exists (unique name per test run)
            import time
            tech_name = f'pdo_tech_{int(time.time()*1000)%100000}'
            tech = User(username=tech_name, full_name='PDO Tech',
                        role='technologist', password_hash='.',
                        is_active=True)
            s.add(tech); s.flush()
            tech_id = tech.id

            # Setup: product + TP
            mat = Material(name="PDO Life Steel", grade="PL1")
            s.add(mat); s.flush()
            prod = Product(designation="PDO.LIFE.001", name="Lifecycle Part",
                           material_id=mat.id)
            s.add(prod); s.flush()
            tp = TechProcess(number="TP-PDO-LIFE", product_id=prod.id,
                             status=TPStatus.DRAFT)
            s.add(tp); s.flush()
            tech_id = tech.id if tech else 1

            # 1. Create order (TP exists → skip technologist)
            order = pdo_module.create_order(
                s, product_id=prod.id, qty=10,
                due_date=date.today(), created_by=1,
            )

            # 2. Sign MTP
            signoff = pdo_module.sign_mtp(
                s, order_id=order.id, tech_process_id=tp.id,
                signed_by=tech_id,
            )
            assert signoff.id is not None
            assert order.status == PDOStatus.MTP_SIGNED

            # 3. Release to shop
            order = pdo_module.release_to_shop(
                s, order_id=order.id, shop='Цех 1', released_by=1,
            )
            assert order.status == PDOStatus.IN_SHOP

            # 4. Accept in shop
            pdo_module.accept_in_shop(s, order_id=order.id, accepted_by=3)

            # 5. QC
            pdo_module.send_to_qc(s, order_id=order.id, transferred_by=3)
            assert order.status == PDOStatus.QC

            # 6. Close
            pdo_module.close_order(
                s, order_id=order.id, qty_done=10, qty_scrap=0,
            )
            assert order.status == PDOStatus.CLOSED
            assert order.qty_done == 10

    def test_get_order_detail_has_handoffs(self, db_manager):
        from modules import pdo_module
        from database.models import Product, Material

        with db_manager.get_session() as s:
            mat = Material(name="PDO Detail Steel", grade="PD1")
            s.add(mat); s.flush()
            prod = Product(designation="PDO.DETAIL.001", name="Detail Part",
                           material_id=mat.id)
            s.add(prod); s.flush()

            order = pdo_module.create_order(
                s, product_id=prod.id, qty=3,
                due_date=date.today(), created_by=1,
            )
            detail = pdo_module.get_order_detail(s, order.id)
            assert detail['number'] == order.number
            assert len(detail['handoffs']) >= 1  # handoff to technologist
