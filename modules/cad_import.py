"""CAD-интеграция — импорт геометрии и атрибутов из CAD-файлов.

Поддерживает:
- STEP (.step/.stp) — извлечение массы, объёма, габаритов
- Kompas-3D (.cdw/.spw) — базовая разборка бинарного формата

Авто-заполнение полей Product при импорте.
Watcher-режим (как PdmDropWatcher) мониторит папку на новые CAD-файлы.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from database.models import Product, Material


@dataclass
class CadGeometry:
    mass_kg: Optional[float] = None
    volume_mm3: Optional[float] = None
    dimensions_mm: Optional[str] = None
    surface_area_mm2: Optional[float] = None
    bounding_box: Optional[str] = None


@dataclass
class CadImportResult:
    product_id: Optional[int] = None
    designation: Optional[str] = None
    name: Optional[str] = None
    geometry: Optional[CadGeometry] = None
    material_grade: Optional[str] = None
    accuracy_class: Optional[str] = None
    roughness: Optional[str] = None
    blank_type: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# STEP file parser
# ──────────────────────────────────────────────────────────────


def parse_step(file_path: Path) -> Optional[CadGeometry]:
    """Распарсить STEP-файл и извлечь геометрию.

    Формат STEP — текстовый (ISO 10303-21).  Ищем ключевые
    атрибуты в entity-строках:
    - VOLUME_MEASURE / MASS_MEASURE
    - PRODUCT_DEFINITION / PRODUCT
    - CARTESIAN_POINT (для bounding box)
    """
    if not file_path.exists():
        return None
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None

    geom = CadGeometry()

    # Извлечение объёма
    vol_match = re.search(
        r"VOLUME_MEASURE\s*\(\s*'([^']*)'\s*,\s*([\d.Ee+\-]+)\s*\)",
        content, re.IGNORECASE,
    )
    if vol_match:
        try:
            geom.volume_mm3 = float(vol_match.group(2))
        except (ValueError, IndexError):
            pass

    # Извлечение массы
    mass_match = re.search(
        r"MASS_MEASURE\s*\(\s*'([^']*)'\s*,\s*([\d.Ee+\-]+)\s*\)",
        content, re.IGNORECASE,
    )
    if mass_match:
        try:
            geom.mass_kg = float(mass_match.group(2))
        except (ValueError, IndexError):
            pass

    # Bounding box из CARTESIAN_POINT
    points = re.findall(
        r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([\d.Ee+\-]+)"
        r"\s*,\s*([\d.Ee+\-]+)\s*,\s*([\d.Ee+\-]+)\s*\)\s*\)",
        content,
    )
    if points:
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        zs = [float(p[2]) for p in points]
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)
        z_range = max(zs) - min(zs)
        geom.dimensions_mm = (
            f'{x_range:.0f}x{y_range:.0f}x{z_range:.0f}'
        )
        geom.bounding_box = (
            f'X:{min(xs):.1f}..{max(xs):.1f} '
            f'Y:{min(ys):.1f}..{max(ys):.1f} '
            f'Z:{min(zs):.1f}..{max(zs):.1f}'
        )

    # Если ничего не найдено, возвращаем None (файл не содержал геометрии)
    if geom.mass_kg is None and geom.volume_mm3 is None \
            and geom.dimensions_mm is None:
        return None

    return geom


# ──────────────────────────────────────────────────────────────
# Kompas-3D CDW/SPW parser (basic binary reader)
# ──────────────────────────────────────────────────────────────


def _read_cdw_strings(data: bytes, min_len: int = 4) -> List[str]:
    """Извлечь читаемые строки из бинарного CDW-файла."""
    result: List[str] = []
    current: List[int] = []
    for byte in data:
        if 0x20 <= byte <= 0x7E or (0xC0 <= byte <= 0xFF):
            current.append(byte)
        else:
            if len(current) >= min_len:
                try:
                    s = bytes(current).decode('windows-1251', errors='ignore')
                    result.append(s)
                except Exception:
                    pass
            current = []
    if len(current) >= min_len:
        try:
            s = bytes(current).decode('windows-1251', errors='ignore')
            result.append(s)
        except Exception:
            pass
    return result


def parse_cdw(file_path: Path) -> Optional[CadGeometry]:
    """Распарсить Kompas CDW (чертёж) — best-effort.

    Ищет читаемые строки в бинарном файле, пытается извлечь
    атрибуты штампа: обозначение, наименование, материал, массу.
    """
    if not file_path.exists():
        return None
    try:
        data = file_path.read_bytes()
    except Exception:
        return None

    strings = _read_cdw_strings(data, min_len=3)

    geom = CadGeometry()

    # Эвристика: масса обычно в формате "Масса 1.23 кг"
    for s in strings:
        mass_match = re.search(r'[Мм]асс[а]?[:\s]+([\d.,]+)\s*кг', s)
        if mass_match:
            try:
                geom.mass_kg = float(mass_match.group(1).replace(',', '.'))
            except ValueError:
                pass
            break

    # Габариты
    for s in strings:
        dim_match = re.search(
            r'(\d+)\s*[xх×]\s*(\d+)\s*[xх×]\s*(\d+)', s)
        if dim_match:
            geom.dimensions_mm = (
                f'{dim_match.group(1)}x'
                f'{dim_match.group(2)}x'
                f'{dim_match.group(3)}'
            )
            break

    return geom if (geom.mass_kg or geom.dimensions_mm) else None


def parse_spw(file_path: Path) -> Optional[CadGeometry]:
    """Распарсить Kompas SPW (3D-модель) — делегирует в parse_cdw."""
    return parse_cdw(file_path)


# ──────────────────────────────────────────────────────────────
# Product auto-fill
# ──────────────────────────────────────────────────────────────


def auto_fill_product(session: Session, *,
                      product_id: int,
                      file_path: Path) -> CadImportResult:
    """Заполнить поля Product данными из CAD-файла.

    Не перезаписывает существующие не-null значения.
    """
    result = CadImportResult(product_id=product_id)
    product = session.get(Product, product_id)
    if product is None:
        result.warnings.append(f'Product id={product_id} не найден')
        return result

    suffix = file_path.suffix.lower()
    if suffix in ('.step', '.stp'):
        geom = parse_step(file_path)
    elif suffix in ('.cdw',):
        geom = parse_cdw(file_path)
    elif suffix in ('.spw',):
        geom = parse_spw(file_path)
    else:
        result.warnings.append(f'Неподдерживаемый формат: {suffix}')
        return result

    result.geometry = geom
    if geom is None:
        result.warnings.append('Не удалось извлечь геометрию из файла')
        return result

    if geom.mass_kg is not None and product.mass is None:
        product.mass = round(geom.mass_kg, 3)
    if geom.dimensions_mm is not None and product.dimensions is None:
        product.dimensions = geom.dimensions_mm

    # Пробуем извлечь материал и другие атрибуты из имени файла / CDW-строк
    designation = file_path.stem.strip()
    if designation and not product.designation:
        product.designation = designation
    result.designation = designation
    result.name = product.name

    session.flush()
    return result


def import_cad_to_new_product(session: Session, *,
                              file_path: Path,
                              group_id: Optional[int] = None,
                              author_id: Optional[int] = None,
                              ) -> CadImportResult:
    """Создать новый Product из CAD-файла."""
    result = CadImportResult()

    designation = file_path.stem.strip()
    existing = session.query(Product).filter(
        Product.designation == designation).first()
    if existing:
        return auto_fill_product(session, product_id=existing.id,
                                 file_path=file_path)

    suffix = file_path.suffix.lower()
    if suffix in ('.step', '.stp'):
        geom = parse_step(file_path)
    elif suffix in ('.cdw',):
        geom = parse_cdw(file_path)
    elif suffix in ('.spw',):
        geom = parse_spw(file_path)
    else:
        result.warnings.append(f'Неподдерживаемый формат: {suffix}')
        return result

    result.geometry = geom

    product = Product(
        designation=designation,
        name=designation,
        group_id=group_id,
        author_id=author_id,
    )
    if geom:
        if geom.mass_kg is not None:
            product.mass = round(geom.mass_kg, 3)
        if geom.dimensions_mm is not None:
            product.dimensions = geom.dimensions_mm

    session.add(product)
    session.flush()
    if product.id is None:
        # Defensive fallback — only triggers if DB schema is broken (missing PK)
        session.execute(
            __import__('sqlalchemy').text(
                'UPDATE products SET id = rowid WHERE id IS NULL AND designation = :d'),
            {'d': designation})
        session.refresh(product)
    result.product_id = product.id
    result.designation = designation
    result.name = designation
    return result
