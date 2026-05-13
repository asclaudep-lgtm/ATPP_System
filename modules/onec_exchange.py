"""Интеграция с 1С — двусторонний обмен данными.

Импорт: спецификации заказа и BOM из 1С (XML/JSON).
Экспорт: фактическая себестоимость, сроки выполнения, спецификации.

Формат XML: стандартный формат обмена 1С:Предприятие 8.
Формат JSON: упрощённый для ручного импорта/экспорта.
"""
from __future__ import annotations

import json
from datetime import date as date_type
from pathlib import Path
from typing import Iterable, List, Optional
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from sqlalchemy.orm import Session
from database.models import (Product, Material, TechProcess, CostCalculation,
                              WorkOrder, RouteStep, BOMItem, AssemblyLevel)
from modules.bom import add_bom_item


# ──────────────────────────────────────────────────────────────
# Result types
# ──────────────────────────────────────────────────────────────


@dataclass
class ImportResult:
    created_products: int = 0
    updated_products: int = 0
    created_tps: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# IMPORT from 1C (XML)
# ──────────────────────────────────────────────────────────────


def import_specification_xml(session: Session, *,
                             xml_path: Path) -> ImportResult:
    """Импорт спецификации из 1C XML.

    Ожидаемая структура:
    <Спецификация>
      <Изделия>
        <Изделие Обозначение="..." Наименование="..." Масса="..."
                 Материал="..." ГОСТ="...">
          <Состав>
            <Строка Обозначение="..." Количество="..." Позиция="..."/>
          </Состав>
        </Изделие>
      </Изделия>
    </Спецификация>
    """
    result = ImportResult()
    if not xml_path.exists():
        result.errors.append(f'Файл не найден: {xml_path}')
        return result

    try:
        tree = ET.parse(str(xml_path))
        root_el = tree.getroot()
    except ET.ParseError as e:
        result.errors.append(f'Ошибка парсинга XML: {e}')
        return result

    products_el = root_el.find('Изделия')
    if products_el is None:
        products_el = root_el

    for prod_el in products_el.findall('Изделие'):
        des = prod_el.get('Обозначение', '').strip()
        name = prod_el.get('Наименование', '').strip()
        if not des or not name:
            result.skipped += 1
            continue

        # Найти или создать материал
        mat_grade = prod_el.get('Материал', '')
        mat_gost = prod_el.get('ГОСТ', '')
        mat_id = None
        if mat_grade:
            mat = session.query(Material).filter(
                Material.grade == mat_grade).first()
            if mat is None:
                mat = Material(name=mat_grade, grade=mat_grade, gost=mat_gost)
                session.add(mat)
                session.flush()
            mat_id = mat.id

        # Найти или создать изделие
        product = session.query(Product).filter(
            Product.designation == des).first()
        if product is None:
            product = Product(
                designation=des, name=name,
                material_id=mat_id,
                mass=float(prod_el.get('Масса', 0) or 0),
            )
            session.add(product)
            session.flush()
            result.created_products += 1
        else:
            product.name = name
            if mat_id:
                product.material_id = mat_id
            result.updated_products += 1
            session.flush()

        # BOM
        bom_el = prod_el.find('Состав')
        if bom_el is not None:
            # Создать корневой BOMItem
            bom_root = BOMItem(
                parent_id=None, product_id=product.id,
                level=AssemblyLevel.PRODUCT, quantity=1,
            )
            session.add(bom_root)
            session.flush()

            for i, row_el in enumerate(bom_el.findall('Строка')):
                child_des = row_el.get('Обозначение', '').strip()
                child_qty = int(row_el.get('Количество', 1))
                child_pos = row_el.get('Позиция', f'поз.{i + 1}')
                if not child_des:
                    continue
                child_product = session.query(Product).filter(
                    Product.designation == child_des).first()
                if child_product is None:
                    child_product = Product(
                        designation=child_des,
                        name=row_el.get('Наименование', child_des),
                    )
                    session.add(child_product)
                    session.flush()
                add_bom_item(session, parent_id=bom_root.id,
                             product_id=child_product.id,
                             level=AssemblyLevel.DETAIL,
                             quantity=child_qty,
                             position=child_pos)

    return result


# ──────────────────────────────────────────────────────────────
# IMPORT from 1C (JSON)
# ──────────────────────────────────────────────────────────────


def import_specification_json(session: Session, *,
                              json_path: Path) -> ImportResult:
    """Импорт спецификации из 1C JSON.

    Структура:
    {
      "products": [
        {
          "designation": "...", "name": "...",
          "material": {"grade": "...", "gost": "..."},
          "mass": 1.2,
          "bom": [
            {"designation": "...", "name": "...", "quantity": 1, "position": "поз.1"}
          ]
        }
      ]
    }
    """
    result = ImportResult()
    if not json_path.exists():
        result.errors.append(f'Файл не найден: {json_path}')
        return result

    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        result.errors.append(f'Ошибка парсинга JSON: {e}')
        return result

    for prod_data in data.get('products', []):
        des = prod_data.get('designation', '').strip()
        name = prod_data.get('name', '').strip()
        if not des or not name:
            result.skipped += 1
            continue

        mat_data = prod_data.get('material', {})
        mat_id = None
        if mat_data.get('grade'):
            mat = session.query(Material).filter(
                Material.grade == mat_data['grade']).first()
            if mat is None:
                mat = Material(
                    name=mat_data['grade'],
                    grade=mat_data['grade'],
                    gost=mat_data.get('gost', ''),
                )
                session.add(mat)
                session.flush()
            mat_id = mat.id

        product = session.query(Product).filter(
            Product.designation == des).first()
        if product is None:
            product = Product(
                designation=des, name=name,
                material_id=mat_id,
                mass=float(prod_data.get('mass', 0) or 0),
            )
            session.add(product)
            session.flush()
            result.created_products += 1
        else:
            result.updated_products += 1
            session.flush()

        bom = prod_data.get('bom', [])
        if bom:
            bom_root = BOMItem(
                parent_id=None, product_id=product.id,
                level=AssemblyLevel.PRODUCT, quantity=1,
            )
            session.add(bom_root)
            session.flush()

            for i, row in enumerate(bom):
                child_des = row.get('designation', '').strip()
                child_qty = int(row.get('quantity', 1))
                child_pos = row.get('position', f'поз.{i + 1}')
                if not child_des:
                    continue
                child = session.query(Product).filter(
                    Product.designation == child_des).first()
                if child is None:
                    child = Product(
                        designation=child_des,
                        name=row.get('name', child_des),
                    )
                    session.add(child)
                    session.flush()
                add_bom_item(session, parent_id=bom_root.id,
                             product_id=child.id,
                             level=AssemblyLevel.DETAIL,
                             quantity=child_qty, position=child_pos)

    return result


# ──────────────────────────────────────────────────────────────
# EXPORT to 1C
# ──────────────────────────────────────────────────────────────


def export_cost_data(session: Session, *,
                     tp_ids: Optional[Iterable[int]] = None,
                     out_path: Optional[Path] = None) -> Path:
    """Экспорт себестоимости в 1C XML.

    Для каждого ТП выгружает: обозначение, наименование, статьи затрат,
    производственную и полную себестоимость, цену, прибыль.
    """
    if out_path is None:
        from config import EXPORT_DIR
        from datetime import datetime
        out_path = EXPORT_DIR / \
            f'1c_cost_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tp_query = session.query(TechProcess).filter(
        TechProcess.is_deleted == False)
    if tp_ids is not None:
        tp_list = list(tp_ids)
        tp_query = tp_query.filter(TechProcess.id.in_(tp_list))
    else:
        tp_list = None

    root = ET.Element('СпецификацияСебестоимости')
    root.set('ДатаВыгрузки', date_type.today().isoformat())

    for tp in tp_query.all():
        tp_el = ET.SubElement(root, 'Техпроцесс')
        ET.SubElement(tp_el, 'Номер').text = tp.number
        ET.SubElement(tp_el, 'Версия').text = tp.version or ''
        if tp.product:
            ET.SubElement(tp_el, 'Обозначение').text = \
                tp.product.designation or ''
            ET.SubElement(tp_el, 'Наименование').text = tp.product.name or ''

        cc = tp.cost_calculation
        if cc:
            costs = ET.SubElement(tp_el, 'Затраты')
            ET.SubElement(costs, 'Материалы').text = f'{cc.material_cost:.2f}'
            ET.SubElement(costs, 'Зарплата').text = f'{cc.labor_cost:.2f}'
            ET.SubElement(costs, 'Отчисления').text = \
                f'{cc.social_contributions:.2f}'
            ET.SubElement(costs, 'Оборудование').text = \
                f'{cc.equipment_cost:.2f}'
            ET.SubElement(costs, 'Цеховые').text = f'{cc.shop_overhead:.2f}'
            ET.SubElement(costs, 'Общезаводские').text = \
                f'{cc.factory_overhead:.2f}'
            ET.SubElement(costs, 'Производственная').text = \
                f'{cc.production_cost:.2f}'
            ET.SubElement(costs, 'Полная').text = f'{cc.full_cost:.2f}'
            ET.SubElement(costs, 'Цена').text = f'{cc.price:.2f}'
            ET.SubElement(costs, 'Прибыль').text = f'{cc.profit:.2f}'

    tree_str = ET.tostring(root, encoding='unicode')
    out_path.write_text(tree_str, encoding='utf-8')
    return out_path


def export_timeline_data(session: Session, *,
                         wo_ids: Optional[Iterable[int]] = None,
                         out_path: Optional[Path] = None) -> Path:
    """Экспорт сроков выполнения нарядов в 1C XML."""
    if out_path is None:
        from config import EXPORT_DIR
        from datetime import datetime
        out_path = EXPORT_DIR / \
            f'1c_timeline_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wo_query = session.query(WorkOrder).filter(
        WorkOrder.is_deleted == False)
    if wo_ids is not None:
        wo_list = list(wo_ids)
        wo_query = wo_query.filter(WorkOrder.id.in_(wo_list))

    root = ET.Element('ГрафикВыполнения')
    root.set('ДатаВыгрузки', date_type.today().isoformat())

    for wo in wo_query.all():
        wo_el = ET.SubElement(root, 'Наряд')
        ET.SubElement(wo_el, 'Номер').text = wo.number
        ET.SubElement(wo_el, 'Статус').text = wo.status.value \
            if hasattr(wo.status, 'value') else str(wo.status)
        if wo.due_date:
            ET.SubElement(wo_el, 'Срок').text = wo.due_date.isoformat()
        ET.SubElement(wo_el, 'КоличествоВсего').text = str(wo.qty_total)
        ET.SubElement(wo_el, 'Выполнено').text = str(wo.qty_done)

        if wo.product:
            ET.SubElement(wo_el, 'Обозначение').text = \
                wo.product.designation or ''

        ops_el = ET.SubElement(wo_el, 'Операции')
        for item in wo.items:
            for step in item.route_steps:
                step_el = ET.SubElement(ops_el, 'Шаг')
                ET.SubElement(step_el, 'Порядок').text = str(step.seq)
                ET.SubElement(step_el, 'Статус').text = step.status.value \
                    if hasattr(step.status, 'value') else str(step.status)
                if step.started_at:
                    ET.SubElement(step_el, 'Начало').text = \
                        step.started_at.isoformat()
                if step.finished_at:
                    ET.SubElement(step_el, 'Окончание').text = \
                        step.finished_at.isoformat()

    tree_str = ET.tostring(root, encoding='unicode')
    out_path.write_text(tree_str, encoding='utf-8')
    return out_path


def export_specification_xls_v2(session: Session, *,
                                tp_ids: Optional[Iterable[int]] = None,
                                out_path: Optional[Path] = None,
                                include_bom: bool = False) -> Path:
    """Расширенный экспорт спецификации в XLSX с опциональным BOM."""
    import openpyxl
    from config import EXPORT_DIR
    from datetime import datetime

    if out_path is None:
        out_path = EXPORT_DIR / \
            f'spec_1c_v2_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Спецификация'
    headers = ['Обозначение', 'Наименование', 'Номер ТП', 'Статус ТП',
               'Материал', 'Масса, кг', 'Себестоимость произв.',
               'Себестоимость полная', 'Цена']
    if include_bom:
        headers.extend(['Уровень БОМ', 'Позиция', 'Кол-во в сборке'])
    ws.append(headers)

    tp_query = session.query(TechProcess).filter(
        TechProcess.is_deleted == False)
    if tp_ids is not None:
        tp_list = list(tp_ids)
        tp_query = tp_query.filter(TechProcess.id.in_(tp_list))

    for tp in tp_query.order_by(TechProcess.number).all():
        p = tp.product
        mat_name = p.material.name if p and p.material else ''
        cc = tp.cost_calculation
        row_data = [
            p.designation if p else '',
            p.name if p else '',
            tp.number,
            tp.status.value if hasattr(tp.status, 'value') else str(tp.status),
            mat_name,
            p.mass if p else '',
            cc.production_cost if cc else '',
            cc.full_cost if cc else '',
            cc.price if cc else '',
        ]
        if include_bom:
            bom_item = session.query(BOMItem).filter(
                BOMItem.product_id == tp.product_id).first()
            row_data.extend([
                bom_item.level.value if bom_item and hasattr(
                    bom_item.level, 'value') else '',
                bom_item.position or '' if bom_item else '',
                bom_item.quantity if bom_item else '',
            ])
        ws.append(row_data)

    wb.save(str(out_path))
    return out_path


def batch_import_from_watch(session: Session, *,
                            watch_dir: Path) -> ImportResult:
    """Сканировать watch_dir и импортировать все XML/JSON файлы.

    Обработанные файлы перемещаются в watch_dir/_imported/.
    """
    result = ImportResult()
    if not watch_dir.exists():
        result.errors.append(f'Директория не найдена: {watch_dir}')
        return result

    done_dir = watch_dir / '_imported'
    done_dir.mkdir(exist_ok=True)

    for f in sorted(watch_dir.iterdir()):
        if not f.is_file():
            continue
        suffix = f.suffix.lower()
        try:
            if suffix == '.xml':
                r = import_specification_xml(session, xml_path=f)
            elif suffix == '.json':
                r = import_specification_json(session, json_path=f)
            else:
                continue
            result.created_products += r.created_products
            result.updated_products += r.updated_products
            result.created_tps += r.created_tps
            result.skipped += r.skipped
            result.errors.extend(r.errors)
        except Exception as e:
            result.errors.append(f'{f.name}: {e}')
        else:
            import shutil
            shutil.move(str(f), str(done_dir / f.name))

    return result
