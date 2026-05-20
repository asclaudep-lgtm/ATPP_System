"""
v8: Полнота заполнения ТП.

Расчёт «процента готовности» ТП — что заполнено, что нет.
Единая логика для дашборда «Полнота данных» и для индикатора в дереве
групп/КТП.

Возвращает кортеж (score:int 0..100, missing:list[str]) — где `missing`
содержит человекочитаемые названия незаполненных секторов.
"""
from __future__ import annotations

from typing import List, Tuple

from database.models import TechProcess

# Список секторов в виде (имя, проверка).
# Каждый сектор даёт равный вклад. 6 секторов × 100 / 6 = 16.67% на каждый.
_SECTORS: List[str] = [
    'Есть операции',
    'Все операции с Тшт/Тпз',
    'Все операции с оборудованием',
    'Все операции с профессией',
    'Заполнены нормы материала',
    'Заполнен автор',
]


def score_tp(tp: TechProcess) -> Tuple[int, List[str]]:
    """Вычислить готовность одного ТП.

    Возвращает (score 0..100, список названий невыполненных секторов).

    `tp` должен быть «живым» SQLAlchemy-объектом внутри открытой сессии,
    чтобы можно было обратиться к `tp.operations` и `tp.material_norms`.
    """
    ops = list(tp.operations or [])
    op_count = len(ops)
    with_time = sum(
        1 for o in ops
        if (o.t_piece or 0) > 0 or (o.t_setup or 0) > 0
    )
    with_eq = sum(1 for o in ops if o.equipment_id)
    with_prof = sum(1 for o in ops if o.profession_id)
    mat_norms = list(getattr(tp, 'material_norms', None) or [])
    with_mat = sum(
        1 for m in mat_norms if (m.norm_per_piece or 0) > 0
    )

    checks = [
        op_count > 0,
        op_count > 0 and with_time == op_count,
        op_count > 0 and with_eq == op_count,
        op_count > 0 and with_prof == op_count,
        bool(mat_norms) and with_mat == len(mat_norms),
        bool(tp.author_id),
    ]
    score = int(round(100.0 * sum(checks) / len(checks)))
    missing = [name for name, ok in zip(_SECTORS, checks) if not ok]
    return score, missing


def score_label(score: int) -> str:
    """Иконка-индикатор для дерева.

    🟢 ≥ 90 — почти готов
    🟡 60..89 — есть пробелы
    🔴 < 60  — много пустого
    ⚫ score == 0  — пустой
    """
    if score == 0:
        return '⚫'
    if score >= 90:
        return '🟢'
    if score >= 60:
        return '🟡'
    return '🔴'


def score_tooltip(score: int, missing: List[str]) -> str:
    """Текст подсказки для индикатора."""
    if score == 100:
        return f'ТП заполнен полностью ({score}%).'
    if not missing:
        return f'Готовность: {score}%.'
    bullets = '\n'.join(f'  • {m}' for m in missing)
    return (
        f'Готовность: {score}%.\n'
        f'Не заполнено:\n{bullets}'
    )
