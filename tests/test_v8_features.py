"""Тесты улучшений v8.

Покрывают:
- Корзина расширена на Product / WorkOrder + 30-дневная автоочистка
- Шаблоны переходов (TransitionTemplate)
- Расчёт себестоимости по факту (RouteStep)
- Экспорт МТП в PDF (single + batch)
- Индикатор готовности ТП (modules.completeness)
"""
from datetime import datetime, timedelta


from database.models import (
    Product, TechProcess, WorkOrder, WorkOrderItem, Operation,
    RouteStep, RouteStepStatus, TransitionTemplate, Profession,
    TPStatus, WorkOrderStatus, Equipment,
)


def _make_tp(s, designation='TEST-1', tp_number='TP-1'):
    p = Product(designation=designation, name='Test product')
    s.add(p)
    s.flush()
    tp = TechProcess(number=tp_number, product_id=p.id,
                     status=TPStatus.DRAFT, version='1.0')
    s.add(tp)
    s.flush()
    return tp, p


# ──────────────────────────────────────────────────────────────────
# v8-2: Корзина — soft-delete для Product и WorkOrder
# ──────────────────────────────────────────────────────────────────

def test_product_soft_delete_persists(db_manager):
    with db_manager.get_session() as s:
        p = Product(designation='SD-1', name='Soft Delete Test')
        s.add(p)
        s.flush()
        pid = p.id

    with db_manager.get_session() as s:
        p = s.get(Product, pid)
        p.is_deleted = True
        p.deleted_at = datetime.now()

    with db_manager.get_session() as s:
        p = s.get(Product, pid)
        assert p.is_deleted is True
        assert p.deleted_at is not None

        # Восстанавливаем
        p.is_deleted = False
        p.deleted_at = None

    with db_manager.get_session() as s:
        p = s.get(Product, pid)
        assert p.is_deleted is False


def test_workorder_soft_delete_persists(db_manager):
    with db_manager.get_session() as s:
        tp, _ = _make_tp(s, 'WO-SD-1', 'TP-WO-1')
        wo = WorkOrder(number='WO-X1', tech_process_id=tp.id,
                       product_id=tp.product_id, qty_total=10,
                       status=WorkOrderStatus.RELEASED)
        s.add(wo)
        s.flush()
        wid = wo.id

    with db_manager.get_session() as s:
        wo = s.get(WorkOrder, wid)
        wo.is_deleted = True
        wo.deleted_at = datetime.now()

    with db_manager.get_session() as s:
        wo = s.get(WorkOrder, wid)
        assert wo.is_deleted is True


def test_recycle_bin_filters_live_products(db_manager):
    """В дереве групп удалённые детали отсутствуют."""
    with db_manager.get_session() as s:
        p1 = Product(designation='LIVE-1', name='Live')
        p2 = Product(designation='DEL-1', name='Deleted',
                     is_deleted=True, deleted_at=datetime.now())
        s.add_all([p1, p2])
        s.flush()

    with db_manager.get_session() as s:
        live = (s.query(Product)
                .filter((not Product.is_deleted)
                        | (Product.is_deleted.is_(None)))
                .filter(Product.designation.in_(['LIVE-1', 'DEL-1']))
                .all())
        assert len(live) == 1
        assert live[0].designation == 'LIVE-1'


# ──────────────────────────────────────────────────────────────────
# v8-5: Шаблоны переходов
# ──────────────────────────────────────────────────────────────────

def test_transition_template_crud(db_manager):
    with db_manager.get_session() as s:
        tpl = TransitionTemplate(
            code='T-001',
            text='Точить наружный диаметр Ø__ на длину __ мм.',
            sort_order=0,
        )
        s.add(tpl)
        s.flush()
        tid = tpl.id

    with db_manager.get_session() as s:
        tpl = s.get(TransitionTemplate, tid)
        assert tpl is not None
        assert 'Точить' in tpl.text
        s.delete(tpl)

    with db_manager.get_session() as s:
        assert s.get(TransitionTemplate, tid) is None


def test_transition_templates_seed_runs_only_once(db_manager):
    """seed заполняет таблицу при пустом, при следующем вызове ничего не делает."""
    from ui.dialogs.transition_templates_dialog import _seed_if_empty
    # Подчищаем перед тестом
    with db_manager.get_session() as s:
        for t in s.query(TransitionTemplate).all():
            s.delete(t)

    _seed_if_empty(db_manager)
    with db_manager.get_session() as s:
        first = s.query(TransitionTemplate).count()
    assert first > 0

    _seed_if_empty(db_manager)
    with db_manager.get_session() as s:
        second = s.query(TransitionTemplate).count()
    assert first == second


# ──────────────────────────────────────────────────────────────────
# v8-6: Себестоимость по факту (RouteStep)
# ──────────────────────────────────────────────────────────────────

def test_cost_calc_uses_actual_time_when_route_steps_exist(db_manager):
    from modules.cost_calc import (
        CostCalculator, TIME_MODE_PLAN, TIME_MODE_ACTUAL,
    )

    with db_manager.get_session() as s:
        tp, p = _make_tp(s, 'COST-A1', 'TP-COST-A1')
        # Профессия с почасовой ставкой.
        prof = Profession(name='Test Toker',
                          hourly_rates='{"3": 600}', typical_grade=3)
        s.add(prof)
        s.flush()
        op = Operation(tech_process_id=tp.id, number='005',
                       name='Точение',
                       profession_id=prof.id, grade=3,
                       t_setup=0, t_piece=10.0,  # план: 10 мин
                       sort_order=1)
        s.add(op)
        s.flush()

        # Создаём WorkOrder + WorkOrderItem + RouteStep с длительностью 20 мин.
        wo = WorkOrder(number='WO-COST-A1', tech_process_id=tp.id,
                       product_id=p.id, qty_total=1,
                       status=WorkOrderStatus.RELEASED)
        s.add(wo)
        s.flush()
        item = WorkOrderItem(
            work_order_id=wo.id, qty=1,
            barcode=f'BC-COST-{wo.id}',
            serial=f'SN-{wo.id}-1',
        )
        s.add(item)
        s.flush()
        started = datetime(2025, 1, 1, 10, 0, 0)
        finished = started + timedelta(minutes=20)
        rs = RouteStep(work_order_item_id=item.id, operation_id=op.id,
                       seq=1, status=RouteStepStatus.DONE,
                       started_at=started, finished_at=finished,
                       qty_good=1, qty_scrap=0)
        s.add(rs)
        s.flush()

        calc = CostCalculator(s)
        plan = calc.calculate_full_cost(
            tech_process_id=tp.id, time_mode=TIME_MODE_PLAN, persist=False)
        fact = calc.calculate_full_cost(
            tech_process_id=tp.id, time_mode=TIME_MODE_ACTUAL, persist=False)

        # 20 мин ÷ 1 шт = 20 мин/шт (факт) vs 10 мин (план).
        # Поэтому ЗП в режиме «по факту» примерно в 2 раза больше.
        assert fact.labor_cost > plan.labor_cost * 1.5
        # Себестоимость тоже выросла.
        assert fact.full_cost > plan.full_cost


def test_cost_calc_actual_fallback_to_plan_when_no_routesteps(db_manager):
    """Без выполненных RouteStep режим actual должен дать тот же результат,
    что и план."""
    from modules.cost_calc import (
        CostCalculator, TIME_MODE_PLAN, TIME_MODE_ACTUAL,
    )
    with db_manager.get_session() as s:
        tp, _ = _make_tp(s, 'COST-B1', 'TP-COST-B1')
        prof = Profession(name='ProfB1',
                          hourly_rates='{"3": 500}', typical_grade=3)
        s.add(prof)
        s.flush()
        op = Operation(tech_process_id=tp.id, number='005',
                       name='Op B', profession_id=prof.id, grade=3,
                       t_setup=0, t_piece=15.0, sort_order=1)
        s.add(op)
        s.flush()

        calc = CostCalculator(s)
        plan = calc.calculate_full_cost(
            tech_process_id=tp.id, time_mode=TIME_MODE_PLAN, persist=False)
        fact = calc.calculate_full_cost(
            tech_process_id=tp.id, time_mode=TIME_MODE_ACTUAL, persist=False)
        assert abs(plan.labor_cost - fact.labor_cost) < 0.01


# ──────────────────────────────────────────────────────────────────
# v8-7: Экспорт МТП в PDF
# ──────────────────────────────────────────────────────────────────

def test_generate_mtp_pdf_single(db_manager, tmp_path):
    from modules.mtp_pdf import generate_mtp_pdf

    with db_manager.get_session() as s:
        tp, _ = _make_tp(s, 'PDF-1', 'TP-PDF-1')
        op = Operation(tech_process_id=tp.id, number='005',
                       name='Точение', t_piece=10, sort_order=1)
        s.add(op)
        s.flush()
        out = tmp_path / 'mtp.pdf'
        data = generate_mtp_pdf(s, tech_process_id=tp.id,
                                out_path=str(out))
        assert out.exists()
        assert len(data) > 1000
        # PDF magic bytes
        assert data[:4] == b'%PDF'


def test_generate_mtp_pdf_batch(db_manager, tmp_path):
    from modules.mtp_pdf import generate_mtp_pdf_batch

    with db_manager.get_session() as s:
        wo_ids = []
        for i in range(3):
            tp, p = _make_tp(s, f'PDF-BATCH-{i}', f'TP-PDF-B{i}')
            op = Operation(tech_process_id=tp.id, number='005',
                           name=f'Op {i}', t_piece=5, sort_order=1)
            s.add(op)
            s.flush()
            wo = WorkOrder(number=f'WO-PDFB-{i}',
                           tech_process_id=tp.id, product_id=p.id,
                           qty_total=1, status=WorkOrderStatus.RELEASED)
            s.add(wo)
            s.flush()
            wo_ids.append(wo.id)

        out = tmp_path / 'batch.pdf'
        data = generate_mtp_pdf_batch(
            s, work_order_ids=wo_ids, out_path=str(out))
        assert out.exists()
        assert data[:4] == b'%PDF'
        assert len(data) > 3000  # 3 страницы


# ──────────────────────────────────────────────────────────────────
# v8-10: Индикатор готовности ТП
# ──────────────────────────────────────────────────────────────────

def test_completeness_module_score_tp_empty(db_manager):
    from modules.completeness import score_tp, score_label

    with db_manager.get_session() as s:
        tp, _ = _make_tp(s, 'CMP-EMPTY', 'TP-CMP-EMPTY')
        score, missing = score_tp(tp)
        assert 0 <= score <= 100
        assert isinstance(missing, list)
        # Полностью пустой ТП должен дать <40%.
        assert score < 40
        # ⚫🔴🟡🟢 — должен быть один из эмодзи.
        assert score_label(score) in ('⚫', '🔴', '🟡', '🟢')


def test_completeness_module_score_tp_full(db_manager):
    from modules.completeness import score_tp

    with db_manager.get_session() as s:
        tp, _ = _make_tp(s, 'CMP-FULL', 'TP-CMP-FULL')
        # Автор есть.
        from database.models import User
        user = User(username='cmp_user', password_hash='x',
                    role='engineer', full_name='Test')
        s.add(user)
        s.flush()
        tp.author_id = user.id

        # Профессия / оборудование.
        prof = Profession(name='CmpProf',
                          hourly_rates='{"3": 600}', typical_grade=3)
        eq = Equipment(name='CmpEQ', model='EQ-1')
        s.add_all([prof, eq])
        s.flush()

        op = Operation(tech_process_id=tp.id, number='005',
                       name='Full op', t_setup=1, t_piece=10,
                       profession_id=prof.id, equipment_id=eq.id,
                       sort_order=1)
        s.add(op)
        s.flush()
        s.refresh(tp)
        score, missing = score_tp(tp)
        # Без material_norms 5/6 ≈ 83 %.
        assert score >= 80
        # Сектор материалов должен быть в недостающих.
        assert any('материалов' in m.lower() or 'мат' in m.lower()
                   for m in missing)
