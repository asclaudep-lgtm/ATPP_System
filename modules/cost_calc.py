"""
Модуль расчёта себестоимости.

С v8 поддерживает два режима:
    plan   — по плановым нормам времени (T-шт. / T-п.з.) операции;
    actual — по фактическому времени из RouteStep (finished_at − started_at),
             если операция уже выполнялась хотя бы раз.

Если в режиме `actual` для операции ещё нет завершённых RouteStep,
используется плановое время в качестве запасного значения.
"""
import json
from typing import Dict, Optional

from config import DEFAULT_FACTORY_OVERHEAD, DEFAULT_LABOR_OVERHEAD, DEFAULT_PROFIT_MARGIN, DEFAULT_SHOP_OVERHEAD
from database.models import (
    CostCalculation,
    Operation,
    Profession,
    RouteStep,
    TechProcess,
)

# Режимы расчёта времени операции.
TIME_MODE_PLAN = 'plan'
TIME_MODE_ACTUAL = 'actual'


class CostCalculator:
    """Класс для расчёта себестоимости"""

    def __init__(self, db_session):
        self.session = db_session

    # ─────────────────────────────────────────────────── helpers
    def _avg_actual_minutes(self, operation: Operation) -> Optional[float]:
        """Среднее фактическое время операции в минутах (по RouteStep).

        Возвращает ``None``, если нет завершённых RouteStep для операции.
        """
        try:
            steps = (self.session.query(RouteStep)
                     .filter(RouteStep.operation_id == operation.id,
                             RouteStep.started_at.isnot(None),
                             RouteStep.finished_at.isnot(None))
                     .all())
        except Exception:
            return None
        if not steps:
            return None
        total_min = 0.0
        total_qty = 0
        for st in steps:
            duration = (st.finished_at - st.started_at).total_seconds() / 60.0
            qty = (st.qty_good or 0) + (st.qty_scrap or 0)
            if duration <= 0:
                continue
            if qty > 0:
                # Норма «на штуку» = общее время / количество.
                total_min += duration
                total_qty += qty
            else:
                # без учёта партии — на единицу всё время шага
                total_min += duration
                total_qty += 1
        if total_qty <= 0:
            return None
        return total_min / total_qty

    def _operation_time_minutes(self, operation: Operation,
                                time_mode: str) -> float:
        """Время операции в минутах для расчёта стоимости."""
        plan = float(operation.t_piece or 0)
        if time_mode == TIME_MODE_ACTUAL:
            fact = self._avg_actual_minutes(operation)
            if fact is not None:
                return fact
        return plan

    def calculate_material_cost(self, tech_process: TechProcess) -> float:
        """
        Рассчитать стоимость материалов
        
        Args:
            tech_process: Технологический процесс
            
        Returns:
            Стоимость материалов
        """
        total_cost = 0

        for norm in tech_process.material_norms:
            total_cost += float(norm.cost_per_piece or 0)

        return total_cost

    def calculate_labor_cost(self, tech_process: TechProcess,
                             time_mode: str = TIME_MODE_PLAN) -> float:
        """
        Рассчитать заработную плату.
        
        Args:
            tech_process: Технологический процесс
            time_mode:    'plan'  — по плановой норме T-шт.;
                          'actual' — по среднему фактическому времени
                                     (RouteStep) с fallback на план.
            
        Returns:
            Заработная плата
        """
        total_cost = 0

        for operation in tech_process.operations:
            t_piece = self._operation_time_minutes(operation, time_mode)
            if operation.profession_id and t_piece > 0:
                profession = self.session.get(Profession, operation.profession_id)

                if profession and profession.hourly_rates:
                    try:
                        rates = json.loads(profession.hourly_rates)
                    except (TypeError, ValueError):
                        rates = {}
                    grade = operation.grade or profession.typical_grade or 3
                    try:
                        hourly_rate = float(rates.get(str(grade), 250) or 250)
                    except (TypeError, ValueError):
                        hourly_rate = 250.0

                    # Переводим минуты в часы и умножаем на ставку
                    cost = (t_piece / 60.0) * hourly_rate
                    total_cost += cost

        return total_cost

    def calculate_equipment_cost(self, tech_process: TechProcess,
                                 time_mode: str = TIME_MODE_PLAN) -> float:
        """
        Рассчитать стоимость эксплуатации оборудования.
        
        Args:
            tech_process: Технологический процесс
            time_mode:    'plan' | 'actual' — см. ``calculate_labor_cost``.
            
        Returns:
            Стоимость эксплуатации оборудования
        """
        total_cost = 0

        for operation in tech_process.operations:
            t_piece = self._operation_time_minutes(operation, time_mode)
            if operation.equipment and t_piece > 0:
                rate = float(getattr(operation.equipment, 'cost_per_hour', 0) or 0)
                cost = (t_piece / 60.0) * rate
                total_cost += cost

        return total_cost

    def calculate_full_cost(
        self,
        tech_process_id: int,
        labor_overhead: float = DEFAULT_LABOR_OVERHEAD,
        shop_overhead: float = DEFAULT_SHOP_OVERHEAD,
        factory_overhead: float = DEFAULT_FACTORY_OVERHEAD,
        profit_margin: float = DEFAULT_PROFIT_MARGIN,
        time_mode: str = TIME_MODE_PLAN,
        persist: bool = True,
    ) -> CostCalculation:
        """
        Рассчитать полную себестоимость.
        
        Args:
            tech_process_id: ID технологического процесса
            labor_overhead:  Процент отчислений на соц. нужды (0.302 = 30.2%)
            shop_overhead:   Процент цеховых расходов (0.25 = 25%)
            factory_overhead: Процент общезаводских расходов (0.40 = 40%)
            profit_margin:   Процент рентабельности (0.20 = 20%)
            time_mode:       'plan' | 'actual' — режим времени операций
                             (v8: расчёт по факту из RouteStep).
            persist:         сохранить расчёт в БД (True) или вернуть
                             отдельный объект без сохранения (False).
                             В режиме `actual` рекомендуется persist=False,
                             чтобы не затирать сохранённый плановый расчёт.
            
        Returns:
            Расчёт себестоимости
        """
        tp = self.session.get(TechProcess, tech_process_id)

        if not tp:
            raise ValueError(f"ТП с ID {tech_process_id} не найден")

        # 1. Материалы
        material_cost = self.calculate_material_cost(tp)

        # 2. Заработная плата
        labor_cost = self.calculate_labor_cost(tp, time_mode=time_mode)

        # 3. Отчисления на социальные нужды
        social_contributions = labor_cost * labor_overhead

        # 4. Эксплуатация оборудования
        equipment_cost = self.calculate_equipment_cost(tp, time_mode=time_mode)

        # 5. Цеховые расходы (от ЗП + Эксплуатация)
        shop_overhead_cost = (labor_cost + equipment_cost) * shop_overhead

        # 6. Общезаводские расходы (от ЗП)
        factory_overhead_cost = labor_cost * factory_overhead

        # 7. Производственная себестоимость
        production_cost = (
            material_cost +
            labor_cost +
            social_contributions +
            equipment_cost +
            shop_overhead_cost +
            factory_overhead_cost
        )

        # 8. Полная себестоимость (с прочими расходами 5%)
        full_cost = production_cost * 1.05

        # 9. Цена с рентабельностью
        price = full_cost * (1 + profit_margin)

        # 10. Прибыль
        profit = price - full_cost

        # Создаём или обновляем запись расчёта.
        if persist:
            cost_calc = self.session.query(CostCalculation).filter_by(
                tech_process_id=tech_process_id
            ).first()
            if not cost_calc:
                cost_calc = CostCalculation(tech_process_id=tech_process_id)
                self.session.add(cost_calc)
        else:
            # v8: «расчёт по факту» — не сохраняем, чтобы не затереть план.
            cost_calc = CostCalculation(tech_process_id=tech_process_id)

        cost_calc.material_cost = round(material_cost, 2)
        cost_calc.labor_cost = round(labor_cost, 2)
        cost_calc.social_contributions = round(social_contributions, 2)
        cost_calc.equipment_cost = round(equipment_cost, 2)
        cost_calc.shop_overhead = round(shop_overhead_cost, 2)
        cost_calc.factory_overhead = round(factory_overhead_cost, 2)
        cost_calc.production_cost = round(production_cost, 2)
        cost_calc.full_cost = round(full_cost, 2)
        cost_calc.price = round(price, 2)
        cost_calc.profit = round(profit, 2)

        if persist:
            self.session.flush()

        return cost_calc

    def get_cost_breakdown(self, tech_process_id: int) -> Dict:
        """
        Получить детализацию себестоимости
        
        Args:
            tech_process_id: ID технологического процесса
            
        Returns:
            Словарь с детализацией
        """
        cost_calc = self.session.query(CostCalculation).filter_by(
            tech_process_id=tech_process_id
        ).first()

        if not cost_calc:
            # Рассчитываем если ещё не рассчитано
            cost_calc = self.calculate_full_cost(tech_process_id)

        tp = self.session.get(TechProcess, tech_process_id)

        breakdown = {
            'tech_process': {
                'number': tp.number,
                'product': tp.product.name,
                'designation': tp.product.designation
            },
            'costs': {
                'materials': {
                    'value': cost_calc.material_cost,
                    'percent': (cost_calc.material_cost / cost_calc.full_cost * 100) if cost_calc.full_cost > 0 else 0
                },
                'labor': {
                    'value': cost_calc.labor_cost,
                    'percent': (cost_calc.labor_cost / cost_calc.full_cost * 100) if cost_calc.full_cost > 0 else 0
                },
                'social_contributions': {
                    'value': cost_calc.social_contributions,
                    'percent': (cost_calc.social_contributions / cost_calc.full_cost * 100) if cost_calc.full_cost > 0 else 0
                },
                'equipment': {
                    'value': cost_calc.equipment_cost,
                    'percent': (cost_calc.equipment_cost / cost_calc.full_cost * 100) if cost_calc.full_cost > 0 else 0
                },
                'shop_overhead': {
                    'value': cost_calc.shop_overhead,
                    'percent': (cost_calc.shop_overhead / cost_calc.full_cost * 100) if cost_calc.full_cost > 0 else 0
                },
                'factory_overhead': {
                    'value': cost_calc.factory_overhead,
                    'percent': (cost_calc.factory_overhead / cost_calc.full_cost * 100) if cost_calc.full_cost > 0 else 0
                }
            },
            'totals': {
                'production_cost': cost_calc.production_cost,
                'full_cost': cost_calc.full_cost,
                'price': cost_calc.price,
                'profit': cost_calc.profit,
                'profit_margin_percent': (cost_calc.profit / cost_calc.full_cost * 100) if cost_calc.full_cost > 0 else 0
            }
        }

        return breakdown

    def compare_tech_processes(
        self,
        tp_id_1: int,
        tp_id_2: int
    ) -> Dict:
        """
        Сравнить себестоимость двух вариантов ТП
        
        Args:
            tp_id_1: ID первого ТП
            tp_id_2: ID второго ТП
            
        Returns:
            Словарь со сравнением
        """
        breakdown_1 = self.get_cost_breakdown(tp_id_1)
        breakdown_2 = self.get_cost_breakdown(tp_id_2)

        comparison = {
            'tp1': breakdown_1,
            'tp2': breakdown_2,
            'differences': {}
        }

        # Рассчитываем разницу
        for key in ['materials', 'labor', 'social_contributions', 'equipment', 'shop_overhead', 'factory_overhead']:
            value_1 = breakdown_1['costs'][key]['value']
            value_2 = breakdown_2['costs'][key]['value']
            diff = value_2 - value_1
            diff_percent = (diff / value_1 * 100) if value_1 > 0 else 0

            comparison['differences'][key] = {
                'absolute': round(diff, 2),
                'percent': round(diff_percent, 1)
            }

        # Разница в итоговой себестоимости
        full_cost_diff = breakdown_2['totals']['full_cost'] - breakdown_1['totals']['full_cost']
        full_cost_diff_percent = (full_cost_diff / breakdown_1['totals']['full_cost'] * 100) if breakdown_1['totals']['full_cost'] > 0 else 0

        comparison['differences']['full_cost'] = {
            'absolute': round(full_cost_diff, 2),
            'percent': round(full_cost_diff_percent, 1)
        }

        return comparison
