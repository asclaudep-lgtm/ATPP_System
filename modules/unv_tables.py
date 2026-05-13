"""Укрупнённые нормативы времени (УНВ).

Таблицы типовых норм для быстрого нормирования без детального расчёта.
Интерполяция по массе и габаритам детали.

Основаны на «Общемашиностроительных нормативах времени»
(НИИ Труда, уточнённые коэффициенты).
"""
from __future__ import annotations

from typing import List, Optional, Dict
from dataclasses import dataclass


# ——— Справочник типовых норм ———
# Структура: {тип_детали: [(масса_кг, габарит_мм, Тпз, Тшт), ...]}

UNV_TURNING = {
    'Вал гладкий': [
        (0.5, 100, 12, 3.5),
        (2.0, 250, 14, 5.0),
        (5.0, 400, 16, 7.5),
        (10.0, 600, 18, 10.0),
        (25.0, 1000, 20, 14.0),
        (50.0, 1500, 24, 20.0),
    ],
    'Вал ступенчатый': [
        (0.5, 100, 14, 6.0),
        (2.0, 250, 16, 8.0),
        (5.0, 400, 18, 11.0),
        (10.0, 600, 20, 15.0),
        (25.0, 1000, 24, 21.0),
        (50.0, 1500, 28, 30.0),
    ],
    'Втулка': [
        (0.3, 80, 12, 4.5),
        (1.0, 150, 14, 6.0),
        (3.0, 250, 16, 9.0),
        (8.0, 400, 18, 13.0),
        (20.0, 600, 22, 18.0),
    ],
    'Фланец': [
        (0.5, 120, 14, 5.0),
        (2.0, 200, 16, 7.5),
        (5.0, 350, 18, 10.5),
        (12.0, 500, 20, 15.0),
        (30.0, 800, 24, 22.0),
    ],
    'Крышка': [
        (0.5, 100, 12, 4.0),
        (2.0, 200, 14, 6.0),
        (5.0, 350, 16, 8.5),
        (12.0, 500, 18, 12.0),
    ],
}

UNV_MILLING = {
    'Плита': [
        (1.0, 200, 14, 5.0),
        (5.0, 400, 16, 8.0),
        (15.0, 600, 18, 12.0),
        (40.0, 1000, 22, 18.0),
    ],
    'Корпус': [
        (2.0, 300, 16, 10.0),
        (8.0, 500, 18, 14.0),
        (20.0, 800, 20, 20.0),
        (50.0, 1200, 24, 28.0),
    ],
    'Кронштейн': [
        (1.0, 200, 14, 7.0),
        (4.0, 350, 16, 10.0),
        (12.0, 500, 18, 15.0),
    ],
    'Планка': [
        (0.3, 150, 12, 3.0),
        (1.0, 300, 14, 4.5),
        (3.0, 500, 16, 7.0),
    ],
}

UNV_DRILLING = {
    'Отверстие сквозное': [
        (0.1, 50, 10, 1.0),
        (0.5, 100, 12, 1.5),
        (2.0, 200, 14, 2.5),
        (5.0, 300, 16, 4.0),
    ],
    'Отверстие глухое/резьбовое': [
        (0.1, 50, 12, 1.5),
        (0.5, 100, 14, 2.0),
        (2.0, 200, 16, 3.5),
        (5.0, 300, 18, 5.5),
    ],
}

UNV_WELDING = {
    'Сварной шов (стыковой)': [
        (1.0, 200, 10, 2.0),
        (3.0, 400, 12, 3.5),
        (8.0, 600, 14, 5.5),
    ],
    'Сварной шов (угловой)': [
        (1.0, 200, 12, 3.0),
        (3.0, 400, 14, 5.0),
        (8.0, 600, 16, 8.0),
    ],
}

UNV_ASSEMBLY = {
    'Узел простой': [
        (2.0, 300, 10, 5.0),
        (10.0, 600, 12, 10.0),
        (30.0, 1000, 14, 18.0),
    ],
    'Узел средней сложности': [
        (5.0, 500, 14, 15.0),
        (20.0, 800, 16, 25.0),
        (50.0, 1200, 18, 40.0),
    ],
    'Узел сложный': [
        (10.0, 600, 16, 30.0),
        (30.0, 1000, 20, 50.0),
        (80.0, 1500, 24, 80.0),
    ],
}

CATEGORY_MAP = {
    'turning': ('Токарные работы', UNV_TURNING),
    'milling': ('Фрезерные работы', UNV_MILLING),
    'drilling': ('Сверлильные работы', UNV_DRILLING),
    'welding': ('Сварочные работы', UNV_WELDING),
    'assembly': ('Сборочные работы', UNV_ASSEMBLY),
}


@dataclass
class UNVResult:
    category: str
    part_type: str
    mass_kg: float
    dimension_mm: float
    t_setup: float       # Тпз
    t_piece: float         # Тшт
    source_mass: float     # ближайшая табличная масса
    source_dim: float      # ближайший табличный габарит
    interpolated: bool


def _interpolate(table: List[tuple], mass: float, dim: float) -> tuple:
    """Линейная интерполяция по массе между двумя ближайшими строками."""
    if mass <= table[0][0]:
        return table[0][2], table[0][3], table[0][0], table[0][1], False
    if mass >= table[-1][0]:
        return table[-1][2], table[-1][3], table[-1][0], table[-1][1], False

    for i in range(len(table) - 1):
        m1, d1, tpz1, tsh1 = table[i]
        m2, d2, tpz2, tsh2 = table[i + 1]
        if m1 <= mass <= m2:
            frac = (mass - m1) / (m2 - m1) if m2 > m1 else 0
            tpz = tpz1 + frac * (tpz2 - tpz1)
            tsh = tsh1 + frac * (tsh2 - tsh1)
            src_m = mass
            src_d = dim
            return round(tpz, 1), round(tsh, 1), src_m, src_d, True

    return table[-1][2], table[-1][3], table[-1][0], table[-1][1], False


def lookup_unv(*, category: str, part_type: str,
               mass_kg: float, dimension_mm: float) -> Optional[UNVResult]:
    """Найти укрупнённую норму по справочнику УНВ.

    category   — 'turning' / 'milling' / 'drilling' / 'welding' / 'assembly'
    part_type  — тип детали (ключ во внутренней таблице)
    mass_kg    — масса детали
    dimension_mm — максимальный габарит
    """
    if category not in CATEGORY_MAP:
        return None
    cat_name, table = CATEGORY_MAP[category]
    if part_type not in table:
        return None

    rows = table[part_type]
    tpz, tsh, src_m, src_d, interp = _interpolate(rows, mass_kg, dimension_mm)
    return UNVResult(
        category=cat_name,
        part_type=part_type,
        mass_kg=mass_kg,
        dimension_mm=dimension_mm,
        t_setup=tpz,
        t_piece=tsh,
        source_mass=src_m,
        source_dim=src_d,
        interpolated=interp,
    )


def list_categories() -> Dict[str, List[str]]:
    """Вернуть {категория: [типы_деталей]}."""
    result = {}
    for cat_key, (cat_name, table) in CATEGORY_MAP.items():
        result[cat_name] = list(table.keys())
    return result
