"""Тесты модуля расчёта себестоимости."""

from database.models import (
    User, Product, Material, TechProcess, Operation, Profession, Equipment,
    MaterialNorm, TPStatus, TPType,
)


def _seed(db):
    with db.get_session() as s:
        u = s.query(User).filter_by(username='admin').first()
        m = Material(name='Сталь 45', grade='45', density=7850.0,
                    price_per_kg=80.0)
        s.add(m); s.flush()
        p = Product(designation='ABC.001', name='Образец',
                    material_id=m.id, mass=1.0, )
        s.add(p); s.flush()
        eq = Equipment(name='Токарный', model='1М63',
                       cost_per_hour=350)
        pr = Profession(name='Токарь', typical_grade=4)
        s.add(eq); s.add(pr); s.flush()

        tp = TechProcess(number='TP-001', version='1.0', author_id=u.id,
                         product_id=p.id, status=TPStatus.DRAFT,
                         tp_type=TPType.SINGLE)
        s.add(tp); s.flush()
        # пара операций — у одной нормы пустые
        s.add(Operation(tech_process_id=tp.id, number='005',
                        name='Токарная', sort_order=1,
                        equipment_id=eq.id, profession_id=pr.id,
                        grade=4, t_main=2.0, t_auxiliary=1.0,
                        t_piece=3.27, t_setup=10))
        s.add(Operation(tech_process_id=tp.id, number='010',
                        name='Контрольная', sort_order=2,
                        t_main=None, t_auxiliary=None,
                        t_piece=None, t_setup=None))
        s.add(MaterialNorm(tech_process_id=tp.id, material_id=m.id,
                           norm_per_piece=1.6, consumption_coefficient=1.15))
        return tp.id


def test_cost_no_crash_with_none_fields(db_manager):
    """Регрессия: cost_calc не падает на None в Tшт/Тпз/нормах."""
    tp_id = _seed(db_manager)
    from modules.cost_calc import CostCalculator
    from database.models import TechProcess
    with db_manager.get_session() as s:
        tp = s.get(TechProcess, tp_id)
        calc = CostCalculator(s)
        # Каждая публичная функция не должна бросать исключение
        m = calc.calculate_material_cost(tp)
        l = calc.calculate_labor_cost(tp)
        e = calc.calculate_equipment_cost(tp)
        f = calc.calculate_full_cost(tp_id)
    assert m >= 0
    assert l >= 0
    assert e >= 0
    assert f is not None
