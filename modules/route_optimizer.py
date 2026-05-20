"""V12: AI-оптимизатор маршрутов ТП.

Sequence model (Markov 2nd order), multi-objective route optimization,
equipment assignment via linear sum assignment, time norm prediction,
chronometry feedback calibration.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from database.models import (
    Equipment,
    Operation,
    Product,
    RouteStep,
    TechProcess,
    TPStatus,
)


@dataclass
class OpSequencePrediction:
    """Предсказание следующей операции в цепочке."""
    operation_name: str
    probability: float
    equipment_name: str = ''
    t_setup: float = 0.0
    t_piece: float = 0.0
    grade: Optional[int] = None


@dataclass
class OptimizedRoute:
    """Оптимизированный маршрут ТП."""
    product_id: int
    operations: List[dict]
    total_cost: float
    total_time: float
    quality_score: float
    equipment_assignments: Dict[int, int]  # op_index → eq_id
    scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class TimeEstimate:
    """Предсказание нормы времени."""
    t_piece: float
    t_setup: float
    confidence: float = 0.0


@dataclass
class CalibrationReport:
    """Отчёт о калибровке норм по хронометражу."""
    operations_checked: int
    operations_updated: int
    avg_deviation_pct: float
    max_deviation_pct: float
    recommendations: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# 2.1 Markov chain sequence model (2nd order)
# ═══════════════════════════════════════════════════════════════════


def _build_transition_model(session: Session) -> Dict[tuple, Counter]:
    """Построить Марковскую цепь 2-го порядка на исторических ТП.

    Ключ: (prev_op_name, current_op_name) → Counter[next_op_name → count]
    """
    transitions: Dict[tuple, Counter] = defaultdict(Counter)

    tps = session.query(TechProcess).filter(
        not TechProcess.is_deleted,
        TechProcess.status == TPStatus.APPROVED,
    ).all()

    for tp in tps:
        ops = session.query(Operation).filter(
            Operation.tech_process_id == tp.id,
            not Operation.is_deleted,
        ).order_by(Operation.sort_order).all()

        if len(ops) < 2:
            continue

        names = [op.name.strip() for op in ops if op.name]
        for i in range(len(names) - 1):
            if i == 0:
                key = ('<START>', names[i])
            else:
                key = (names[i - 1], names[i])
            transitions[key][names[i + 1]] += 1

        # Терминальный переход
        if len(names) >= 2:
            key = (names[-2], names[-1])
            transitions[key]['<END>'] += 1

    return dict(transitions)


def predict_next_op(session: Session, *,
                    current_ops: List[str],
                    top_n: int = 5) -> List[OpSequencePrediction]:
    """Предсказать наиболее вероятную следующую операцию."""
    model = _build_transition_model(session)

    if len(current_ops) >= 2:
        key = (current_ops[-2].strip(), current_ops[-1].strip())
    elif len(current_ops) == 1:
        key = ('<START>', current_ops[0].strip())
    else:
        key = ('<START>', '<START>')

    counts = model.get(key, {})
    total = sum(counts.values())
    if total == 0:
        return []

    results = []
    for name, count in counts.most_common(top_n):
        if name == '<END>':
            continue
        prob = count / total

        # Найти типичные параметры этой операции
        avg_setup, avg_piece, eq_name, grade = _op_averages(
            session, name)

        results.append(OpSequencePrediction(
            operation_name=name,
            probability=round(prob, 3),
            equipment_name=eq_name,
            t_setup=round(avg_setup, 2),
            t_piece=round(avg_piece, 2),
            grade=grade,
        ))

    return results


def _op_averages(session, op_name: str) -> Tuple[float, float, str, Optional[int]]:
    """Вычислить средние параметры операции по имени."""
    ops = session.query(Operation).filter(
        Operation.name.ilike(f'%{op_name}%'),
        not Operation.is_deleted,
    ).limit(50).all()

    if not ops:
        return 0.0, 0.0, '', None

    setups = [o.t_setup or 0 for o in ops]
    pieces = [o.t_piece or 0 for o in ops]
    eq_names = [o.equipment.name for o in ops if o.equipment]
    grades = [o.grade for o in ops if o.grade]

    return (
        np.mean(setups) if setups else 0.0,
        np.mean(pieces) if pieces else 0.0,
        Counter(eq_names).most_common(1)[0][0] if eq_names else '',
        Counter(grades).most_common(1)[0][0] if grades else None,
    )


# ═══════════════════════════════════════════════════════════════════
# 2.2 Multi-objective route optimization
# ═══════════════════════════════════════════════════════════════════


def optimize_route(session: Session, *,
                   product_id: int,
                   weights: Optional[Dict[str, float]] = None,
                   ) -> OptimizedRoute:
    """Оптимизировать маршрут по нескольким критериям.

    Критерии: cost (себестоимость), time (время), quality (качество).

    weights: {'cost': 0.4, 'time': 0.3, 'quality': 0.3}
    """
    if weights is None:
        weights = {'cost': 0.4, 'time': 0.3, 'quality': 0.3}

    product = session.get(Product, product_id)
    if product is None:
        raise ValueError(f'Product {product_id} not found')

    from modules.ai_assistant import suggest_operations

    suggestions = suggest_operations(session, product_id=product_id,
                                     similar_count=5)
    if not suggestions:
        return OptimizedRoute(
            product_id=product_id, operations=[],
            total_cost=0.0, total_time=0.0, quality_score=0.0,
            equipment_assignments={},
        )

    # Оценить каждый вариант оборудования для каждой операции
    operations = []
    total_cost = 0.0
    total_time = 0.0
    total_quality = 0.0
    equipment_assignments = {}

    for i, sug in enumerate(suggestions):
        # Найти все доступные станки для этой операции
        eq_options = _find_equipment_options(session, sug.operation_name)

        best_score = -float('inf')
        best_eq = None
        best_cost = 0.0
        best_time = 0.0
        best_quality = 0.0

        for eq_id, eq_data in eq_options.items():
            cost_score = 1.0 - min(eq_data['cost_per_hour'] / 2000.0, 1.0)
            time_score = 1.0 - min((sug.t_piece or 0) / 120.0, 1.0)
            quality_score = eq_data.get('quality', 0.5)

            combined = (
                weights.get('cost', 0.3) * cost_score +
                weights.get('time', 0.3) * time_score +
                weights.get('quality', 0.4) * quality_score
            )

            if combined > best_score:
                best_score = combined
                best_eq = eq_id
                best_cost = eq_data['cost_per_hour'] * (sug.t_piece or 0) / 60.0
                best_time = sug.t_piece or 0
                best_quality = quality_score

        if best_eq:
            equipment_assignments[i] = best_eq

        operations.append({
            'number': f'{i * 5 + 5:03d}',
            'name': sug.operation_name,
            'equipment_id': best_eq,
            'equipment_name': eq_options[best_eq]['name'] if best_eq and best_eq in eq_options else '',
            't_setup': sug.t_setup,
            't_piece': sug.t_piece,
            'grade': sug.grade,
            'cost': round(best_cost, 2),
            'score': round(best_score, 3),
        })

        total_cost += best_cost
        total_time += best_time
        total_quality += best_quality

    n_ops = len(operations)
    return OptimizedRoute(
        product_id=product_id,
        operations=operations,
        total_cost=round(total_cost, 2),
        total_time=round(total_time, 2),
        quality_score=round(total_quality / n_ops, 3) if n_ops > 0 else 0.0,
        equipment_assignments=equipment_assignments,
        scores={
            'cost_score': round(1.0 - min(total_cost / 10000.0, 1.0), 3),
            'time_score': round(1.0 - min(total_time / 500.0, 1.0), 3),
            'quality_score': round(total_quality / max(n_ops, 1), 3),
        },
    )


def _find_equipment_options(session, op_name: str) -> Dict[int, dict]:
    """Найти доступные станки для операции по имени."""
    ops = session.query(Operation).filter(
        Operation.name.ilike(f'%{op_name}%'),
        not Operation.is_deleted,
    ).limit(100).all()

    eq_map = {}
    for op in ops:
        if op.equipment_id and op.equipment_id not in eq_map:
            eq = op.equipment
            quality = 0.7
            if eq:
                if eq.power and eq.power > 10:
                    quality = 0.9
                elif eq.power and eq.power > 5:
                    quality = 0.75
                eq_map[eq.id] = {
                    'name': eq.name or '',
                    'cost_per_hour': float(eq.cost_per_hour or 500),
                    'quality': quality,
                }
    return eq_map


# ═══════════════════════════════════════════════════════════════════
# 2.3 Equipment assignment optimization (linear sum assignment)
# ═══════════════════════════════════════════════════════════════════


def assign_equipment(session: Session, *,
                     operations: List[dict],
                     criteria: str = 'cost',
                     ) -> Dict[int, int]:
    """Оптимально назначить оборудование операциям.

    Использует Hungarian algorithm (scipy.optimize.linear_sum_assignment)
    для минимизации суммарной стоимости/времени.

    operations: [{'name': str, 't_piece': float, ...}, ...]
    criteria: 'cost' или 'time'

    Returns: {op_index: equipment_id}
    """
    from scipy.optimize import linear_sum_assignment

    if not operations:
        return {}

    # Собрать уникальные станки
    all_eq = session.query(Equipment).all()

    if not all_eq:
        return {}

    n_ops = len(operations)
    n_eq = len(all_eq)
    n = max(n_ops, n_eq)

    cost_matrix = np.full((n, n), 1e9, dtype=np.float64)

    for i, op in enumerate(operations):
        for j, eq in enumerate(all_eq):
            if criteria == 'cost':
                cost_per_min = (eq.cost_per_hour or 500) / 60.0
                cost_matrix[i, j] = cost_per_min * (op.get('t_piece', 15))
            else:
                # Time: assume 10% speed variation based on power
                base_time = op.get('t_piece', 15)
                power_factor = 1.0 - (eq.power or 5) / 200.0
                cost_matrix[i, j] = base_time * max(power_factor, 0.5)

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    assignments = {}
    for i, j in zip(row_ind, col_ind):
        if i < n_ops and j < n_eq:
            assignments[i] = all_eq[j].id

    return assignments


# ═══════════════════════════════════════════════════════════════════
# 2.4 Time norm prediction (linear regression)
# ═══════════════════════════════════════════════════════════════════


def _build_time_features(op: Operation) -> Optional[np.ndarray]:
    """Построить признаки для предсказания времени операции."""
    if op.equipment is None:
        return None

    vec = np.zeros(8, dtype=np.float64)
    vec[0] = float(op.equipment.power or 5) / 50.0
    vec[1] = float(op.equipment.cost_per_hour or 500) / 2000.0
    vec[2] = float(op.grade or 3) / 6.0
    vec[3] = float(op.t_setup or 10) / 60.0

    # Операционные one-hot категории (упрощённо)
    name = (op.name or '').lower()
    vec[4] = 1.0 if 'токар' in name else 0.0
    vec[5] = 1.0 if 'фрезер' in name else 0.0
    vec[6] = 1.0 if 'сверл' in name else 0.0
    vec[7] = 1.0 if 'шлифова' in name else 0.0

    return vec


def predict_time_norms(session: Session, *,
                       operation_params: dict) -> TimeEstimate:
    """Предсказать нормы времени для операции.

    Использует линейную регрессию на исторических данных.
    """
    operations = session.query(Operation).filter(
        not Operation.is_deleted,
        Operation.t_piece > 0,
    ).limit(500).all()

    if len(operations) < 10:
        return TimeEstimate(
            t_piece=operation_params.get('t_piece', 15.0),
            t_setup=operation_params.get('t_setup', 10.0),
            confidence=0.1,
        )

    X_list = []
    y_list = []
    for op in operations:
        feat = _build_time_features(op)
        if feat is not None:
            X_list.append(feat)
            y_list.append(float(op.t_piece))

    if len(X_list) < 10:
        return TimeEstimate(
            t_piece=operation_params.get('t_piece', 15.0),
            t_setup=operation_params.get('t_setup', 10.0),
            confidence=0.1,
        )

    X = np.stack(X_list, axis=0)
    y = np.array(y_list, dtype=np.float64)

    # Ridge regression via normal equation: w = (X^T X + λI)^(-1) X^T y
    lambda_reg = 1.0
    XtX = X.T @ X + lambda_reg * np.eye(X.shape[1])
    Xty = X.T @ y

    try:
        w = np.linalg.solve(XtX, Xty)
    except np.linalg.LinAlgError:
        w = np.linalg.lstsq(X, y, rcond=None)[0]

    # Построить вектор признаков для запроса
    query = np.zeros(8, dtype=np.float64)
    query[0] = float(operation_params.get('power', 5)) / 50.0
    query[1] = float(operation_params.get('cost_per_hour', 500)) / 2000.0
    query[2] = float(operation_params.get('grade', 3)) / 6.0
    query[3] = float(operation_params.get('t_setup', 10)) / 60.0
    name = (operation_params.get('name', '') or '').lower()
    query[4] = 1.0 if 'токар' in name else 0.0
    query[5] = 1.0 if 'фрезер' in name else 0.0
    query[6] = 1.0 if 'сверл' in name else 0.0
    query[7] = 1.0 if 'шлифова' in name else 0.0

    predicted = float(query @ w)

    # R² оценка
    y_pred = X @ w
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return TimeEstimate(
        t_piece=round(max(predicted, 1.0), 2),
        t_setup=operation_params.get('t_setup', 10.0),
        confidence=round(max(r2, 0.0), 3),
    )


# ═══════════════════════════════════════════════════════════════════
# 2.5 Chronometry feedback loop
# ═══════════════════════════════════════════════════════════════════


def calibrate_from_chrono(session: Session, *,
                          threshold_pct: float = 15.0) -> CalibrationReport:
    """Калибровать нормы времени по фактическому хронометражу.

    Для каждой завершённой RouteStep сравнивает фактическое время
    с плановым и обновляет нормы Operation при значимом отклонении.
    """

    steps = session.query(RouteStep).filter(
        RouteStep.finished_at.isnot(None),
        RouteStep.started_at.isnot(None),
    ).limit(500).all()

    checked = 0
    updated = 0
    deviations = []

    # Группировка по operation_id
    op_actuals: Dict[int, List[float]] = defaultdict(list)
    for step in steps:
        if step.operation_id and step.started_at and step.finished_at:
            actual = (step.finished_at - step.started_at).total_seconds() / 60.0
            op_actuals[step.operation_id].append(actual)

    report = CalibrationReport(
        operations_checked=0,
        operations_updated=0,
        avg_deviation_pct=0.0,
        max_deviation_pct=0.0,
    )

    for op_id, actuals in op_actuals.items():
        if len(actuals) < 3:
            continue

        checked += 1
        op = session.get(Operation, op_id)
        if op is None or not op.t_piece:
            continue

        avg_actual = np.mean(actuals)
        planned = float(op.t_piece)
        deviation = abs(avg_actual - planned) / planned * 100.0
        deviations.append(deviation)

        if deviation > threshold_pct:
            # Экспоненциальное сглаживание
            factor = 0.3
            new_t_piece = planned * (1.0 - factor) + avg_actual * factor
            op.t_piece = round(new_t_piece, 2)
            updated += 1

    if deviations:
        report.avg_deviation_pct = round(np.mean(deviations), 1)
        report.max_deviation_pct = round(max(deviations), 1)

    report.operations_checked = checked
    report.operations_updated = updated

    if report.avg_deviation_pct > 15.0:
        report.recommendations.append(
            'Среднее отклонение > 15% — рекомендуется пересмотр нормативов')
    if report.max_deviation_pct > 50.0:
        report.recommendations.append(
            'Обнаружены операции с отклонением > 50% — проверьте хронометраж')
    if updated > checked * 0.5:
        report.recommendations.append(
            'Более половины операций обновлены — валидируйте нормы с технологом')

    return report


# ═══════════════════════════════════════════════════════════════════
# 2.6 Route generation from sequence model
# ═══════════════════════════════════════════════════════════════════


def generate_route_sequence(session: Session, *,
                            product_id: int,
                            max_ops: int = 15) -> List[OpSequencePrediction]:
    """Сгенерировать полную цепочку операций для изделия.

    Начинает с <START> и следует Марковской цепи пока не <END>
    или не достигнут max_ops.
    """
    product = session.get(Product, product_id)
    if product is None:
        return []

    current_ops: List[str] = []
    route: List[OpSequencePrediction] = []

    for _ in range(max_ops):
        next_ops = predict_next_op(session, current_ops=current_ops, top_n=3)
        if not next_ops:
            break

        best = next_ops[0]
        if best.operation_name in current_ops[-2:]:
            # Избегаем циклов — берём следующую
            if len(next_ops) > 1:
                best = next_ops[1]
            else:
                break

        route.append(best)
        current_ops.append(best.operation_name)

    return route
