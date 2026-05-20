"""
Operation type registry — SprutTP Codifier.dat equivalent.

Defines a catalog of standard operation types with codes, auto-detection
keywords, default equipment/profession bindings, typical transitions,
and norm module references.

Each entry corresponds to one standard operation type in the
machine-building classifier (ОКП).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OperationTypeDef:
    """A standard operation type definition (one row in the codifier)."""
    code: str                                    # e.g. "4100" for rough turning
    name: str                                    # "Токарная (черновая)"
    keywords: List[str] = field(default_factory=list)
    typical_equipment: str = ""
    typical_profession: str = ""
    typical_grade: int = 3
    typical_transitions: List[str] = field(default_factory=list)
    norm_module: str = ""                        # "turning" -> modules/norms/turning.py
    parent_code: str = ""                        # for grouping (e.g. 4100 & 4110 both -> 4000)


# ── Registry ──
OPERATION_TYPE_REGISTRY: List[OperationTypeDef] = []


def _reg(code, name, **kw) -> OperationTypeDef:
    ot = OperationTypeDef(code=code, name=name, **kw)
    OPERATION_TYPE_REGISTRY.append(ot)
    return ot


def register_all():
    """Populate with standard operation types. Called on import."""
    OPERATION_TYPE_REGISTRY.clear()

    _reg("1000", "Заготовительная",
         keywords=["заготовительн", "отрезн", "blank", "заготовк"],
         typical_equipment="Станок отрезной",
         typical_profession="Заготовщик",
         typical_grade=2,
         norm_module="blanking",
         typical_transitions=[
             "Установить заготовку и закрепить.",
             "Отрезать заготовку в размер.",
             "Проверить размеры заготовки.",
         ])

    _reg("4100", "Токарная (черновая)",
         keywords=["токарн.*черн", "черн.*токарн", "токарная предв"],
         typical_equipment="Станок токарный",
         typical_profession="Токарь",
         typical_grade=3,
         norm_module="turning",
         typical_transitions=[
             "Установить деталь в патрон, выставить.",
             "Точить поверхность предварительно.",
             "Точить торцы предварительно.",
         ])

    _reg("4110", "Токарная (чистовая)",
         keywords=["токарн.*чист", "чист.*токарн", "токарная оконч"],
         typical_equipment="Станок токарный",
         typical_profession="Токарь",
         typical_grade=4,
         norm_module="turning",
         typical_transitions=[
             "Установить деталь в патрон, выставить.",
             "Точить поверхность окончательно.",
             "Точить торцы окончательно.",
             "Точить фаски.",
         ])

    _reg("4120", "Токарная (общая)",
         keywords=["токарн", "turning", "lathe", "токар"],
         typical_equipment="Станок токарный",
         typical_profession="Токарь",
         typical_grade=3,
         norm_module="turning",
         typical_transitions=[
             "Установить деталь в патрон, выставить.",
             "Точить поверхность.",
             "Проверить размеры.",
         ])

    _reg("0200", "Фрезерная",
         keywords=["фрезерн", "milling", "фрезер"],
         typical_equipment="Станок фрезерный",
         typical_profession="Фрезеровщик",
         typical_grade=3,
         norm_module="milling",
         typical_transitions=[
             "Установить деталь в приспособление.",
             "Фрезеровать поверхность в размер.",
             "Проверить размеры после фрезерования.",
         ])

    _reg("0300", "Сверлильная",
         keywords=["сверлильн", "drilling", "сверл"],
         typical_equipment="Станок сверлильный",
         typical_profession="Сверловщик",
         typical_grade=3,
         norm_module="drilling",
         typical_transitions=[
             "Установить деталь на стол, закрепить.",
             "Сверлить отверстия по разметке.",
             "Зенковать отверстия.",
         ])

    _reg("5000", "Шлифовальная",
         keywords=["шлифовальн", "grinding", "шлифов"],
         typical_equipment="Станок шлифовальный",
         typical_profession="Шлифовщик",
         typical_grade=4,
         norm_module="grinding",
         typical_transitions=[
             "Установить деталь в центрах.",
             "Шлифовать поверхность в размер.",
             "Проверить шероховатость.",
         ])

    _reg("6000", "Сварочная",
         keywords=["сварочн", "welding", "сварк", "свар"],
         typical_equipment="Аппарат сварочный",
         typical_profession="Сварщик",
         typical_grade=4,
         norm_module="welding",
         typical_transitions=[
             "Зачистить кромки под сварку.",
             "Собрать узел в приспособлении.",
             "Прихватить.",
             "Сварить шов.",
             "Зачистить шов.",
         ])

    _reg("7000", "Термообработка",
         keywords=["термо", "heat", "закалк", "отпуск"],
         typical_equipment="Печь закалочная",
         typical_profession="Термист",
         typical_grade=4,
         norm_module="heat_treatment",
         typical_transitions=[
             "Загрузить деталь в печь.",
             "Выдержать при заданной температуре.",
             "Извлечь и охладить.",
         ])

    _reg("8000", "Слесарная",
         keywords=["слесарн", "assembl", "сборочн", "слесар"],
         typical_equipment="Верстак слесарный",
         typical_profession="Слесарь",
         typical_grade=3,
         norm_module="assembly",
         typical_transitions=[
             "Установить деталь в тиски.",
             "Зачистить заусенцы.",
             "Проверить визуально.",
         ])

    _reg("9000", "Контрольная",
         keywords=["контрольн", "inspection", "отк", "контрол"],
         typical_equipment="Стол ОТК",
         typical_profession="Контролёр",
         typical_grade=3,
         norm_module="inspection",
         typical_transitions=[
             "Проверить размеры согласно чертежу.",
             "Проверить шероховатость.",
             "Оформить заключение.",
         ])

    return OPERATION_TYPE_REGISTRY


# ── Query functions ──

def detect_operation_type(name: str) -> Optional[OperationTypeDef]:
    """Auto-detect operation type from name using keyword matching.

    Replaces all 'any(w in op_lower for w in [...])' patterns
    across time_norms.py, labor_calc.py, and tp_designer.py.
    """
    if not name:
        return None
    import re
    name_lower = name.lower()
    for ot in OPERATION_TYPE_REGISTRY:
        for kw in ot.keywords:
            try:
                if re.search(kw, name_lower):
                    return ot
            except re.error:
                if kw in name_lower:
                    return ot
    return None


def by_code(code: str) -> Optional[OperationTypeDef]:
    """Look up operation type by exact code."""
    for ot in OPERATION_TYPE_REGISTRY:
        if ot.code == code:
            return ot
    return None


def get_typical_transitions(code: str) -> List[str]:
    """Get default transitions for an operation type."""
    ot = by_code(code)
    return list(ot.typical_transitions) if ot else []


def by_norm_module(module: str) -> Optional[OperationTypeDef]:
    """Find first operation type using a given norm module."""
    for ot in OPERATION_TYPE_REGISTRY:
        if ot.norm_module == module:
            return ot
    return None


# ── Initialize on import ──
register_all()
