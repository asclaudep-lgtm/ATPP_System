"""Tests for previously uncovered v9 modules — tooling, material_trace,
metrology, scrap_journal, ecn.  Happy path + edge cases."""

import pytest
from datetime import date, timedelta


class TestTooling:
    def test_issue_to_user_requires_existing_item(self, db_manager):
        from modules.tooling import issue_to_user
        with db_manager.get_session() as s:
            with pytest.raises(ValueError):
                issue_to_user(s, tooling_item_id=99999,
                              issued_to=1, issued_by=1)

    def test_issue_to_user_creates_record(self, db_manager):
        from modules.tooling import issue_to_user
        from database.models import ToolingItem, ToolingStatus

        with db_manager.get_session() as s:
            ti = ToolingItem(inventory_no="TST-001", name="Test Fixture",
                             status=ToolingStatus.AVAILABLE, location="Shelf A")
            s.add(ti)
            s.flush()
            ti_id = ti.id
            issue = issue_to_user(s, tooling_item_id=ti_id,
                                  issued_to=1, issued_by=1,
                                  notes="Test issue")
            assert issue.id is not None
            assert issue.tooling_item_id == ti_id


class TestMaterialTrace:
    def test_add_batch_creates_record(self, db_manager):
        from modules.material_trace import add_batch
        from database.models import Material

        with db_manager.get_session() as s:
            m = Material(name="Test Steel", grade="45")
            s.add(m)
            s.flush()
            batch = add_batch(s, material_id=m.id,
                              lot_no="LOT-001", qty_received=100.0)
            assert batch.id is not None
            assert batch.lot_no == "LOT-001"

    def test_add_batch_defaults(self, db_manager):
        from modules.material_trace import add_batch
        from database.models import Material

        with db_manager.get_session() as s:
            m = Material(name="Test Steel 2", grade="40X")
            s.add(m)
            s.flush()
            batch = add_batch(s, material_id=m.id,
                              lot_no="LOT-002", qty_received=50.0)
            assert batch.id is not None


class TestMetrology:
    def test_add_calibration_creates_record(self, db_manager):
        from modules.metrology import add_calibration
        from database.models import Instrument, InstrumentStatus

        with db_manager.get_session() as s:
            inst = Instrument(name="Test Micrometer", inventory_no="MC-001",
                              status=InstrumentStatus.ACTIVE)
            s.add(inst)
            s.flush()
            cal = add_calibration(s, instrument_id=inst.id,
                                  performed_at=date.today(),
                                  result="годен")
            assert cal.id is not None

    def test_instruments_due_soon_returns_list(self, db_manager):
        from modules.metrology import instruments_due_soon
        from database.models import Instrument, InstrumentStatus

        with db_manager.get_session() as s:
            inst = Instrument(name="Test Caliper", inventory_no="CL-001",
                              status=InstrumentStatus.ACTIVE)
            s.add(inst)
            s.flush()
            due = instruments_due_soon(s, days=365)
            assert isinstance(due, list)


class TestScrapJournal:
    def test_create_scrap_creates_entry(self, db_manager):
        from modules.scrap_journal import create_scrap
        from database.models import (ScrapReason, WorkOrder,
                                      WorkOrderStatus, TechProcess,
                                      Product, Material, TPStatus)

        with db_manager.get_session() as s:
            # Create fresh TP + WO in this session to avoid test ordering issues
            m = Material(name="ScrapTest", grade="ST")
            s.add(m)
            s.flush()
            p = Product(designation="SCRAP.TEST.001", name="Scrap Part",
                        material_id=m.id)
            s.add(p)
            s.flush()
            tp = TechProcess(number="TP-SCRAP-TEST", product_id=p.id,
                             status=TPStatus.DRAFT)
            s.add(tp)
            s.flush()
            wo = WorkOrder(number="WO-SCRAP-TEST", tech_process_id=tp.id,
                           status=WorkOrderStatus.RELEASED)
            s.add(wo)
            s.flush()

            rec = create_scrap(
                s, work_order_id=wo.id,
                reason=ScrapReason.OTHER,
                qty_scrap=3,
                description="Test scrap entry",
                reported_by=1,
            )
            assert rec.id is not None
            assert rec.qty_scrap == 3

    def test_scrap_by_reason_returns_list(self, db_manager):
        from modules.scrap_journal import scrap_by_reason

        with db_manager.get_session() as s:
            stats = scrap_by_reason(s, days=365)
            assert isinstance(stats, list)


class TestECN:
    def test_next_ecn_number(self, db_manager):
        from modules.ecn import next_ecn_number
        with db_manager.get_session() as s:
            num = next_ecn_number(s)
            assert isinstance(num, str)
            assert len(num) > 0

    def test_create_ecn_and_submit(self, db_manager):
        from modules.ecn import create_ecn, submit_for_review
        from database.models import (TechProcess, Product, Material,
                                      TPStatus)

        with db_manager.get_session() as s:
            tp = s.query(TechProcess).first()
            if tp is None:
                m = Material(name="ECNTest", grade="ET")
                s.add(m); s.flush()
                p = Product(designation="ECN.TEST.001", name="ECN Part",
                            material_id=m.id)
                s.add(p); s.flush()
                tp = TechProcess(number="TP-ECN-TEST", product_id=p.id,
                                 status=TPStatus.DRAFT)
                s.add(tp); s.flush()
            ecn = create_ecn(
                s, title="Change material",
                reason="Material upgrade",
                proposed_change="Change material to 40X",
                tech_process_id=tp.id,
                created_by=1,
            )
            assert ecn is not None
            assert ecn.id is not None

            submitted = submit_for_review(s, ecn_id=ecn.id)
            assert submitted is not None
