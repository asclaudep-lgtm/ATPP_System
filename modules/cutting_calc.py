"""Калькулятор режимов резания.

Поддерживает: точение, фрезерование, сверление, шлифование.
Формулы — стандартные машиностроительные (Справочник технолога-машиностроителя).
"""
from __future__ import annotations

import math
from typing import Optional, Dict, Any
from dataclasses import dataclass


# ——— База: табличные коэффициенты для групп материалов ———

MATERIAL_GROUPS: Dict[str, Dict[str, Any]] = {
    'Сталь конструкционная': {
        'Cv': 350, 'xv': 0.15, 'yv': 0.35, 'm': 0.20,
        'Cp': 300, 'xp': 1.0, 'yp': 0.75, 'np': -0.15,
        'Ks': 1.0, 'desc': 'Сталь 45, 40Х, Ст3 и аналоги',
    },
    'Сталь нержавеющая': {
        'Cv': 240, 'xv': 0.18, 'yv': 0.30, 'm': 0.20,
        'Cp': 280, 'xp': 1.0, 'yp': 0.75, 'np': -0.15,
        'Ks': 0.7, 'desc': '12Х18Н10Т, AISI 304 и аналоги',
    },
    'Чугун серый': {
        'Cv': 290, 'xv': 0.15, 'yv': 0.40, 'm': 0.20,
        'Cp': 180, 'xp': 1.0, 'yp': 0.75, 'np': -0.15,
        'Ks': 1.1, 'desc': 'СЧ20, СЧ25 и аналоги',
    },
    'Алюминий': {
        'Cv': 550, 'xv': 0.12, 'yv': 0.28, 'm': 0.18,
        'Cp': 80, 'xp': 1.0, 'yp': 0.75, 'np': -0.15,
        'Ks': 3.0, 'desc': 'Д16Т, АМг6, АК4 и аналоги',
    },
    'Титан': {
        'Cv': 120, 'xv': 0.15, 'yv': 0.35, 'm': 0.20,
        'Cp': 260, 'xp': 1.0, 'yp': 0.75, 'np': -0.15,
        'Ks': 0.4, 'desc': 'ВТ6, ОТ4 и аналоги',
    },
    'Латунь/Бронза': {
        'Cv': 450, 'xv': 0.12, 'yv': 0.30, 'm': 0.18,
        'Cp': 90, 'xp': 1.0, 'yp': 0.75, 'np': -0.15,
        'Ks': 2.5, 'desc': 'Л63, БрАЖ9-4 и аналоги',
    },
}

TOOL_MATERIAL: Dict[str, float] = {
    'Твёрдый сплав (ВК8)': 1.0,
    'Твёрдый сплав (Т15К6)': 1.15,
    'Быстрорез (Р6М5)': 0.65,
    'Минералокерамика': 1.4,
    'CBN (куб. нитрид бора)': 1.8,
}

OPERATION_TYPES = ['Токарная', 'Фрезерная', 'Сверлильная', 'Шлифовальная']


@dataclass
class CuttingResult:
    speed_vc: float       # скорость резания, м/мин
    spindle_n: int         # частота вращения, об/мин
    feed_s: float          # подача, мм/об (точение/сверление) или мм/зуб (фрез.)
    feed_min: float        # минутная подача, мм/мин
    depth_t: float         # глубина резания, мм
    power_n: float         # мощность резания, кВт
    main_time: float       # основное время, мин
    force_pz: float        # сила резания, Н
    material_group: str
    tool_material: str


def calculate_turning(*, diameter: float, length: float,
                      depth: float, feed: float = 0.0,
                      material: str = 'Сталь конструкционная',
                      tool: str = 'Твёрдый сплав (Т15К6)',
                      tool_life: float = 60.0,
                      ) -> CuttingResult:
    """Расчёт режимов точения.

    diameter — диаметр обработки, мм
    length   — длина обработки, мм
    depth    — глубина резания, мм
    feed     — подача, мм/об (0 = автовыбор)
    """
    g = MATERIAL_GROUPS.get(material, MATERIAL_GROUPS['Сталь конструкционная'])
    kt = TOOL_MATERIAL.get(tool, 1.0)

    # Автовыбор подачи
    if feed <= 0:
        if depth <= 1.0:
            feed = 0.15
        elif depth <= 3.0:
            feed = 0.25
        elif depth <= 6.0:
            feed = 0.35
        else:
            feed = 0.5

    # Скорость резания: Vc = (Cv * Kv) / (T^m * t^xv * S^yv)
    vc = (g['Cv'] * kt) / (
        (tool_life ** g['m']) *
        (depth ** g['xv']) *
        (feed ** g['yv'])
    )

    # Частота вращения: n = 1000 * Vc / (pi * D)
    n = int(1000 * vc / (math.pi * diameter))

    # Сила резания: Pz = Cp * t^xp * S^yp * Vc^np
    pz = (g['Cp'] * (depth ** g['xp']) *
          (feed ** g['yp']) * (vc ** g['np']))

    # Мощность: N = Pz * Vc / 60000
    power = pz * vc / 60000.0

    # Основное время: To = L / (n * S)
    t_main = length / (n * feed) if n > 0 and feed > 0 else 0.0

    return CuttingResult(
        speed_vc=round(vc, 1),
        spindle_n=n,
        feed_s=round(feed, 3),
        feed_min=round(n * feed, 1),
        depth_t=depth,
        power_n=round(power, 2),
        main_time=round(t_main, 2),
        force_pz=round(pz, 1),
        material_group=material,
        tool_material=tool,
    )


def calculate_milling(*, diameter: float, length: float,
                      depth: float, width: float = 0.0,
                      teeth: int = 4, feed_z: float = 0.0,
                      material: str = 'Сталь конструкционная',
                      tool: str = 'Твёрдый сплав (ВК8)',
                      tool_life: float = 90.0,
                      ) -> CuttingResult:
    """Расчёт режимов фрезерования.

    diameter — диаметр фрезы, мм
    length   — длина обработки, мм
    depth    — глубина резания, мм
    width    — ширина фрезерования (0 = диаметр фрезы)
    teeth    — число зубьев
    feed_z   — подача на зуб, мм/зуб (0 = автовыбор)
    """
    g = MATERIAL_GROUPS.get(material, MATERIAL_GROUPS['Сталь конструкционная'])
    kt = TOOL_MATERIAL.get(tool, 1.0)
    if width <= 0:
        width = diameter

    if feed_z <= 0:
        feed_z = 0.08 if material in ('Сталь конструкционная', 'Сталь нержавеющая') else 0.12

    # Vc для фрезерования (адаптированные коэффициенты)
    cv_adjusted = g['Cv'] * 0.7
    vc = (cv_adjusted * kt) / (
        (tool_life ** g['m']) *
        (depth ** g['xv']) *
        (feed_z ** g['yv']) *
        (width ** 0.1)
    )

    n = int(1000 * vc / (math.pi * diameter))
    feed_min = n * feed_z * teeth
    pz = g['Cp'] * (depth ** g['xp']) * (feed_z ** g['yp']) * (width ** 0.8) * (vc ** g['np'])
    power = pz * vc / 60000.0
    t_main = length / feed_min if feed_min > 0 else 0.0

    return CuttingResult(
        speed_vc=round(vc, 1),
        spindle_n=n,
        feed_s=round(feed_z, 3),
        feed_min=round(feed_min, 1),
        depth_t=depth,
        power_n=round(power, 2),
        main_time=round(t_main, 2),
        force_pz=round(pz, 1),
        material_group=material,
        tool_material=tool,
    )


def calculate_drilling(*, diameter: float, length: float,
                       material: str = 'Сталь конструкционная',
                       tool: str = 'Быстрорез (Р6М5)',
                       ) -> CuttingResult:
    """Расчёт режимов сверления."""
    g = MATERIAL_GROUPS.get(material, MATERIAL_GROUPS['Сталь конструкционная'])
    kt = TOOL_MATERIAL.get(tool, 1.0)

    # Подача для сверления
    if diameter <= 5:
        feed = 0.08
    elif diameter <= 10:
        feed = 0.15
    elif diameter <= 20:
        feed = 0.25
    elif diameter <= 30:
        feed = 0.32
    else:
        feed = 0.4

    vc = (g['Cv'] * 0.55 * kt * (diameter ** 0.4)) / (60 ** g['m'] * feed ** g['yv'])
    n = int(1000 * vc / (math.pi * diameter))
    pz = g['Cp'] * (diameter ** 0.8) * (feed ** 0.7)
    power = pz * vc / 60000.0
    t_main = length / (n * feed) if n > 0 else 0.0

    return CuttingResult(
        speed_vc=round(vc, 1),
        spindle_n=n,
        feed_s=round(feed, 3),
        feed_min=round(n * feed, 1),
        depth_t=diameter / 2,
        power_n=round(power, 2),
        main_time=round(t_main, 2),
        force_pz=round(pz, 1),
        material_group=material,
        tool_material=tool,
    )


def calculate_grinding(*, diameter: float, length: float,
                       depth: float = 0.01, width: float = 0.0,
                       material: str = 'Сталь конструкционная',
                       ) -> CuttingResult:
    """Расчёт режимов круглого шлифования."""
    if width <= 0:
        width = 40.0  # ширина круга по умолчанию

    # Упрощённые формулы для шлифования
    vc = 35.0  # скорость круга, м/с
    v_part = 25.0 if 'алюм' in material.lower() else 15.0  # м/мин

    n = int(1000 * v_part / (math.pi * diameter))
    feed_per_rev = 0.3 * width  # продольная подача за оборот
    feed_min = n * feed_per_rev
    t_main = length / feed_min if feed_min > 0 else 0.0
    power = 2.5  # приблизительно

    return CuttingResult(
        speed_vc=round(vc, 1),
        spindle_n=n,
        feed_s=round(feed_per_rev, 1),
        feed_min=round(feed_min, 1),
        depth_t=depth,
        power_n=power,
        main_time=round(t_main, 2),
        force_pz=0.0,
        material_group=material,
        tool_material='Абразивный круг',
    )
