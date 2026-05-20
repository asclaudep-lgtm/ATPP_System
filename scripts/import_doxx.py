"""
Импорт технологических процессов из файлов DOXX (САПР ТП ТехноПро/СпрутТП)
Читает все .DOXX файлы из указанной папки и импортирует в БД АТПП.

Запуск:
    python scripts/import_doxx.py [--path D:\\тп] [--clear]
"""

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

# Добавляем корень проекта в путь
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.db_manager import DatabaseManager
from database.models import (
    Base,
    Equipment,
    Material,
    MaterialNorm,
    Operation,
    OperationTool,
    Product,
    ProductGroup,
    Profession,
    TechnologyType,
    TechProcess,
    Tool,
    TPStatus,
    TPType,
    Transition,
)

# ─────────────────────────────────────────────────────────────────────────────
# Конфигурация групп
# ─────────────────────────────────────────────────────────────────────────────

# Маппинг prefix → (родительская группа, подгруппа)
GROUP_CONFIG = {
    # prefix_key: (parent_name, subgroup_name, parent_display, sub_display)
    '53-74.80': ('53-74',   '53-74.80',  'Агрегаты 53-74', 'Агрегаты 53-74.80'),
    '51-74.88': ('51-74',   '51-74.88',  'Агрегаты 51-74', 'Агрегаты 51-74.88'),
    '48-74.88': ('48-74',   '48-74.88',  'Агрегаты 48-74', 'Агрегаты 48-74.88'),
    '45-74.88': ('45-74',   '45-74.88',  'Агрегаты 45-74', 'Агрегаты 45-74.88'),
    '41-74.88': ('41-74',   '41-74.88',  'Агрегаты 41-74', 'Агрегаты 41-74.88'),
    '35-74.88': ('35-74',   '35-74.88',  'Агрегаты 35-74', 'Агрегаты 35-74.88'),
    '35-74.08': ('35-74',   '35-74.08',  'Агрегаты 35-74', 'Агрегаты 35-74.08'),
    '31-74.80': ('31-74',   '31-74.80',  'Агрегаты 31-74', 'Агрегаты 31-74.80'),
    '11-74.80': ('11-74',   '11-74.80',  'Агрегаты 11-74', 'Агрегаты 11-74.80'),
    '74.00':    ('74',      '74.00',     'Агрегаты 74',    'Агрегаты 74.00'),
    '74.80':    ('74',      '74.80',     'Агрегаты 74',    'Агрегаты 74.80'),
    '74.88':    ('74',      '74.88',     'Агрегаты 74',    'Агрегаты 74.88'),
    '7610.0496':('7610',    '7610.0496', 'Агрегаты 7610',  'Агрегаты 7610.0496'),
    '7610.0396':('7610',    '7610.0396', 'Агрегаты 7610',  'Агрегаты 7610.0396'),
    '1.7601':   (None,      '1.7601',    None,             'Агрегаты 1.7601'),
    '1.7603':   (None,      '1.7603',    None,             'Агрегаты 1.7603'),
    'ТИПОВОЙ':  (None,      'ТИПОВОЙ',   None,             'Типовые ТП'),
    'УЗГА':     (None,      'УЗГА',      None,             'УЗГА'),
    'ШАБЛОН':   (None,      'ШАБЛОН',    None,             'Шаблоны'),
    'ПРОЧИЕ':   (None,      'ПРОЧИЕ',    None,             'Прочие'),
}

# Соответствие наименований операций → тип технологии
OPERATION_TYPE_MAP = {
    'фрезерн': TechnologyType.MACHINING,
    'токарн':  TechnologyType.MACHINING,
    'сверлильн': TechnologyType.MACHINING,
    'шлифовальн': TechnologyType.MACHINING,
    'слесарн': TechnologyType.OTHER,
    'контрольн': TechnologyType.OTHER,
    'сборн': TechnologyType.ASSEMBLY,
    'сварочн': TechnologyType.WELDING,
    'штампов': TechnologyType.STAMPING,
    'термическ': TechnologyType.HEAT_TREATMENT,
    'литейн': TechnologyType.CASTING,
    'гальваническ': TechnologyType.COATING,
    'окрашиван': TechnologyType.COATING,
    'покрыт': TechnologyType.COATING,
    'резк': TechnologyType.CUTTING,
    'заготовительн': TechnologyType.CUTTING,
    'зенкерн': TechnologyType.MACHINING,
    'расточн': TechnologyType.MACHINING,
    'протяжн': TechnologyType.MACHINING,
    'зубофрезерн': TechnologyType.MACHINING,
}


# ─────────────────────────────────────────────────────────────────────────────
# Парсинг DOXX файла
# ─────────────────────────────────────────────────────────────────────────────

def parse_doxx(filepath: str) -> dict:
    """
    Парсит DOXX файл и возвращает структуру:
    {
        'header': {field_name: value, ...},   # поля заголовка (Section1)
        'rows': [                              # строки ТП (Section3)
            {'type': 'RecA'|'RecB'|'RecO'|'RecT'|'RecM_mater'|...,
             'fields': {name: value, ...},
             'page': int, 'order': int},
            ...
        ]
    }
    """
    with open(filepath, 'rb') as f:
        raw = f.read()

    text = raw.decode('windows-1251')

    # Извлекаем секцию Dox (атрибутный XML формат)
    dox_match = re.search(r'<Dox\s', text)
    if not dox_match:
        return {'header': {}, 'rows': []}

    dox_start = dox_match.start()
    dox_end = text.find('</Dox>') + len('</Dox>')
    dox_text = text[dox_start:dox_end]

    # Исправляем объявление кодировки для парсинга
    dox_xml = '<?xml version="1.0" encoding="utf-8"?>' + dox_text
    try:
        dox_tree = ET.fromstring(dox_xml.encode('utf-8'))
    except ET.ParseError:
        return {'header': {}, 'rows': []}

    pages_el = dox_tree.find('Pages')
    if pages_el is None:
        return {'header': {}, 'rows': []}

    header = {}
    rows = []

    for pi, page in enumerate(pages_el.findall('Page')):
        secs = page.find('Sections')
        if secs is None:
            continue

        for sec in secs.findall('Section'):
            sec.get('Name', '')
            sec_type = sec.get('Type', '')

            # Section1 (Type=0) — заголовок документа
            if sec_type == '0':
                fields_el = sec.find('Fields')
                if fields_el is not None:
                    for field in fields_el.findall('Field'):
                        name = field.get('Name', '')
                        value = field.get('Value', '')
                        if name and value:
                            header[name] = value

            # Section3 (Type=3) — строки ТП (повторяющийся раздел)
            elif sec_type == '3':
                recs_el = sec.find('Records')
                if recs_el is None:
                    continue
                for rec in recs_el.findall('Record'):
                    rec_name = rec.get('Name', '')
                    rec_order = int(rec.get('Order', '0') or '0')
                    fields_el = rec.find('Fields')
                    fields = {}
                    if fields_el is not None:
                        for field in fields_el.findall('Field'):
                            fname = field.get('Name', '')
                            fval = field.get('Value', '')
                            if fname and fval:
                                fields[fname] = fval
                    if fields:
                        rows.append({
                            'type': rec_name,
                            'fields': fields,
                            'page': pi + 1,
                            'order': rec_order,
                        })

    return {'header': header, 'rows': rows}


def clean_sym(text: str) -> str:
    """Удаляет теги <sym:...> и <ind:...> из текста"""
    text = re.sub(r'<sym:[^>]+>', '', text)
    text = re.sub(r'<ind:[^>]+>', '', text)
    return text.strip()


def parse_float(val: str) -> float | None:
    """Безопасное преобразование строки в float"""
    if not val:
        return None
    val = val.replace(',', '.').strip()
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def split_tools(tool_str: str) -> list[str]:
    """Разбивает строку инструментов по разделителям"""
    tools = []
    for t in re.split(r';\s*', tool_str):
        t = clean_sym(t).strip().strip(';').strip()
        if len(t) > 2:
            tools.append(t)
    return tools


# ─────────────────────────────────────────────────────────────────────────────
# Определение группы по обозначению
# ─────────────────────────────────────────────────────────────────────────────

def get_group_key(designation: str) -> str:
    """Возвращает ключ группы для данного обозначения"""
    d = designation.strip()

    if d.startswith('ТИПОВОЙ') or d.startswith('ТИПОВОЙ_'):
        return 'ТИПОВОЙ'
    if d.startswith('УЗГА'):
        return 'УЗГА'
    if d.upper().startswith('ШАБЛОН'):
        return 'ШАБЛОН'
    if d.startswith('.'):
        return 'ПРОЧИЕ'

    # Проверяем точные префиксы от длинных к коротким
    prefixes_ordered = [
        '53-74.80', '51-74.88', '48-74.88', '45-74.88',
        '41-74.88', '35-74.88', '35-74.08', '31-74.80', '11-74.80',
        '74.00', '74.80', '74.88',
        '7610.0496', '7610.0396',
        '1.7601', '1.7603',
    ]
    for pfx in prefixes_ordered:
        if d.startswith(pfx):
            return pfx

    # Неизвестный — прочие
    return 'ПРОЧИЕ'


def get_operation_type(op_name: str) -> TechnologyType:
    """Определяет тип технологии по наименованию операции"""
    name_lower = op_name.lower()
    for keyword, tech_type in OPERATION_TYPE_MAP.items():
        if keyword in name_lower:
            return tech_type
    return TechnologyType.OTHER


# ─────────────────────────────────────────────────────────────────────────────
# Основной импортёр
# ─────────────────────────────────────────────────────────────────────────────

class DoxxImporter:
    def __init__(self, session):
        self.session = session
        self._mat_cache: dict[str, Material] = {}
        self._equip_cache: dict[str, Equipment] = {}
        self._tool_cache: dict[str, Tool] = {}
        self._prof_cache: dict[str, Profession] = {}
        self._group_cache: dict[str, ProductGroup] = {}

        # Счётчики
        self.stats = {
            'products': 0, 'tps': 0, 'operations': 0,
            'transitions': 0, 'tools': 0, 'materials': 0,
            'equipment': 0, 'skipped': 0, 'errors': 0,
        }

    # ──── Получение/создание справочников ────────────────────────────────────

    def get_or_create_group(self, group_key: str) -> ProductGroup | None:
        if group_key in self._group_cache:
            return self._group_cache[group_key]

        cfg = GROUP_CONFIG.get(group_key)
        if cfg is None:
            cfg = (None, group_key, None, group_key)

        parent_key, sub_name, parent_display, sub_display = cfg

        # Создаём родительскую группу если нужно
        parent_group = None
        if parent_key:
            parent_group = self.get_or_create_group(parent_key)

        # Ищем или создаём подгруппу
        group = (self.session.query(ProductGroup)
                 .filter_by(name=sub_name).first())
        if group is None:
            group = ProductGroup(
                name=sub_name,
                display_name=sub_display or sub_name,
                parent_id=parent_group.id if parent_group else None,
                sort_order=self._sort_for(sub_name),
            )
            self.session.add(group)
            self.session.flush()

        self._group_cache[group_key] = group
        return group

    def _sort_for(self, name: str) -> int:
        """Порядок сортировки групп"""
        order_map = {
            '1.7601': 10, '1.7603': 15,
            '11-74': 20, '11-74.80': 21,
            '31-74': 30, '31-74.80': 31,
            '35-74': 40, '35-74.08': 41, '35-74.88': 42,
            '41-74': 50, '41-74.88': 51,
            '45-74': 60, '45-74.88': 61,
            '48-74': 70, '48-74.88': 71,
            '51-74': 80, '51-74.88': 81,
            '53-74': 90, '53-74.80': 91,
            '74': 100, '74.00': 101, '74.80': 102, '74.88': 103,
            '7610': 110, '7610.0396': 111, '7610.0496': 112,
            'ТИПОВОЙ': 200, 'УЗГА': 210, 'ШАБЛОН': 220, 'ПРОЧИЕ': 999,
        }
        return order_map.get(name, 500)

    def get_or_create_material(self, grade: str, gost_sort: str = '') -> Material | None:
        if not grade:
            return None
        key = grade.strip()
        if key in self._mat_cache:
            return self._mat_cache[key]
        mat = self.session.query(Material).filter_by(grade=key).first()
        if mat is None:
            mat = Material(name=key, grade=key, gost=gost_sort[:50] if gost_sort else '')
            self.session.add(mat)
            self.session.flush()
            self.stats['materials'] += 1
        self._mat_cache[key] = mat
        return mat

    def get_or_create_equipment(self, name: str) -> Equipment | None:
        if not name:
            return None
        # Берём первый элемент если несколько через ;
        name = name.split(';')[0].strip()
        if len(name) < 2:
            return None
        key = name[:100]
        if key in self._equip_cache:
            return self._equip_cache[key]
        equip = self.session.query(Equipment).filter_by(name=key).first()
        if equip is None:
            equip = Equipment(name=key)
            self.session.add(equip)
            self.session.flush()
            self.stats['equipment'] += 1
        self._equip_cache[key] = equip
        return equip

    def get_or_create_tool(self, designation: str, tool_type: str = '') -> Tool | None:
        if not designation or len(designation.strip()) < 3:
            return None
        key = designation.strip()[:100]
        if key in self._tool_cache:
            return self._tool_cache[key]
        tool = self.session.query(Tool).filter_by(designation=key).first()
        if tool is None:
            tool = Tool(designation=key, tool_type=tool_type or 'Инструмент')
            self.session.add(tool)
            self.session.flush()
            self.stats['tools'] += 1
        self._tool_cache[key] = tool
        return tool

    def get_or_create_profession(self, name: str) -> Profession | None:
        if not name:
            return None
        key = name.strip()[:100]
        if key in self._prof_cache:
            return self._prof_cache[key]
        prof = self.session.query(Profession).filter_by(name=key).first()
        if prof is None:
            prof = Profession(name=key)
            self.session.add(prof)
            self.session.flush()
        self._prof_cache[key] = prof
        return prof

    # ──── Структурный парсинг строк ТП ───────────────────────────────────────

    def _build_operations(self, rows: list[dict]) -> list[dict]:
        """
        Группирует строки по операциям.
        Возвращает список операций с их строками.
        """
        operations = []
        current_op = None

        for row in rows:
            rtype = row['type']
            fields = row['fields']

            if rtype == 'RecA':
                # Новая операция
                current_op = {
                    'number': fields.get('NumOper', '').strip(),
                    'name': fields.get('NamOper', '').strip(),
                    'code': fields.get('CodOper', '').strip(),
                    'shop': fields.get('NumDep', '').strip(),
                    'equipment_str': '',
                    'profession_str': '',
                    'grade': fields.get('RAZR_RAB', '').strip(),
                    'tpz': None,
                    'tsht': None,
                    'transitions': [],
                    'tool_strings': [],  # списки инструментов
                }
                operations.append(current_op)

            elif rtype == 'RecB' and current_op is not None:
                # Оборудование, профессия, нормы
                cod = fields.get('CodObor', '').strip()
                if cod:
                    current_op['equipment_str'] = cod
                prof = fields.get('CodProf', '').strip()
                if prof:
                    current_op['profession_str'] = prof
                grade = fields.get('RAZR_RAB', '').strip()
                if grade:
                    current_op['grade'] = grade
                tpz = fields.get('Tpz', '')
                tsht = fields.get('Tsht', '')
                if tpz:
                    current_op['tpz'] = parse_float(tpz)
                if tsht:
                    current_op['tsht'] = parse_float(tsht)

            elif rtype in ('RecO',) and current_op is not None:
                # Переход
                text_per = clean_sym(fields.get('TextPer', '')).strip()
                num_per = fields.get('NumPer', '').strip()
                if text_per:
                    current_op['transitions'].append({
                        'number': num_per,
                        'text': text_per,
                    })

            elif rtype == 'RecT' and current_op is not None:
                # Инструмент
                inst_str = clean_sym(fields.get('NumInst', '')).strip()
                if inst_str:
                    current_op['tool_strings'].append(inst_str)

            elif rtype == 'RecOKP' and current_op is not None:
                # Итоговые нормы времени
                tpz = fields.get('Tpz', '')
                tsht = fields.get('Tsht', '')
                if tpz and current_op['tpz'] is None:
                    current_op['tpz'] = parse_float(tpz)
                if tsht and current_op['tsht'] is None:
                    current_op['tsht'] = parse_float(tsht)

        return operations

    # ──── Импорт одного файла ────────────────────────────────────────────────

    def import_file(self, filepath: str, filename: str) -> bool:
        """Импортирует один DOXX файл. Возвращает True если успешно."""

        # ── Парсим имя файла для обозначения и наименования ──
        base = filename
        # Удаляем расширение
        for ext in ('.DOXX', '.doxx'):
            if base.endswith(ext):
                base = base[:-len(ext)]
                break

        # Формат: DESIGNATION, 'NAME', ДОКУМЕНТ 'TYPE'
        parts = base.split(',')
        if len(parts) < 2:
            self.stats['skipped'] += 1
            return False

        designation = parts[0].strip()
        # Наименование в одинарных кавычках
        name_raw = parts[1].strip().strip("'")

        # ── Парсим DOXX ──
        try:
            doc = parse_doxx(filepath)
        except Exception as e:
            print(f"  ОШИБКА парсинга {filename}: {e}")
            self.stats['errors'] += 1
            return False

        header = doc['header']
        rows = doc['rows']

        # Используем значения из заголовка документа если доступны
        designation_from_doc = header.get('OBOZN_DET', '').strip() or designation
        name_from_doc = header.get('NAME_DET', '').strip() or name_raw
        material_grade = header.get('MARKA_MATER', '').strip()
        material_gost = header.get('GOST_MATER', '').strip()
        gost_sort = header.get('GOST_SORT', '').strip()
        blank_profile = header.get('PROFZAG', '').strip()
        mass_str = header.get('MASS_DET_KG', '').strip()
        mass = parse_float(mass_str)

        # Итоговые строки инструмента из RecT на первой странице
        # (для нормы расхода материала)
        norm_rasxod = parse_float(header.get('NORMORAS', ''))

        # ── Определяем группу ──
        group_key = get_group_key(designation_from_doc or designation)
        group = self.get_or_create_group(group_key)

        # ── Создаём/обновляем изделие ──
        product = (self.session.query(Product)
                   .filter_by(designation=designation_from_doc).first())
        if product is None:
            # Материал
            mat = None
            if material_grade:
                mat = self.get_or_create_material(material_grade,
                                                  gost_sort or material_gost)
            product = Product(
                designation=designation_from_doc,
                name=name_from_doc,
                group_id=group.id if group else None,
                material_id=mat.id if mat else None,
                mass=mass,
                blank_type='Прокат' if gost_sort else None,
                blank_dimensions=blank_profile[:100] if blank_profile else None,
                material_gost=(gost_sort or material_gost)[:200] if (gost_sort or material_gost) else None,
            )
            self.session.add(product)
            self.session.flush()
            self.stats['products'] += 1
        else:
            # Обновляем если нужно
            if not product.group_id and group:
                product.group_id = group.id
            if not product.mass and mass:
                product.mass = mass

        # ── Создаём ТП ──
        tp_number = header.get('OBOZN_TP', '').strip() or f"{designation_from_doc} ТП"
        tp_number = tp_number[:50]

        tp = self.session.query(TechProcess).filter_by(number=tp_number).first()
        if tp is not None:
            # ТП с таким номером уже есть — пропускаем
            self.stats['skipped'] += 1
            return True

        # Определяем тип технологии по первой операции
        tech_type = TechnologyType.MACHINING  # по умолчанию
        for row in rows:
            if row['type'] == 'RecA':
                tech_type = get_operation_type(row['fields'].get('NamOper', ''))
                break

        tp = TechProcess(
            number=tp_number,
            product_id=product.id,
            tp_type=TPType.SINGLE,
            technology_type=tech_type,
            status=TPStatus.APPROVED,
            description=header.get('TypeDocum', ''),
        )
        self.session.add(tp)
        self.session.flush()
        self.stats['tps'] += 1

        # ── Материальная норма ──
        if material_grade or gost_sort:
            mat = (self.get_or_create_material(material_grade or gost_sort, gost_sort)
                   if (material_grade or gost_sort) else None)
            if mat:
                mn = MaterialNorm(
                    tech_process_id=tp.id,
                    material_id=mat.id,
                    blank_profile=gost_sort[:50] if gost_sort else '',
                    blank_dimensions=blank_profile[:100] if blank_profile else '',
                    norm_per_piece=norm_rasxod,
                )
                self.session.add(mn)

        # ── Операции ──
        op_structs = self._build_operations(rows)
        for op_idx, op_data in enumerate(op_structs):
            if not op_data['number'] and not op_data['name']:
                continue

            # Оборудование
            equip = self.get_or_create_equipment(op_data['equipment_str'])

            # Профессия
            prof = self.get_or_create_profession(op_data['profession_str']) if op_data['profession_str'] else None

            # Разряд
            grade_str = op_data.get('grade', '').strip()
            grade_int = None
            if grade_str:
                m = re.search(r'\d+', grade_str)
                if m:
                    grade_int = int(m.group())

            operation = Operation(
                tech_process_id=tp.id,
                number=op_data['number'] or str((op_idx + 1) * 5).zfill(3),
                name=op_data['name'] or 'Операция',
                code=op_data['code'],
                shop=op_data['shop'],
                equipment_id=equip.id if equip else None,
                profession_id=prof.id if prof else None,
                grade=grade_int,
                t_setup=op_data['tpz'] or 0.0,
                t_piece=op_data['tsht'] or 0.0,
                sort_order=op_idx,
            )
            self.session.add(operation)
            self.session.flush()
            self.stats['operations'] += 1

            # ── Переходы ──
            prev_text = ''
            trans_sort = 0
            for t_data in op_data['transitions']:
                # Объединяем продолжение предыдущей строки (без номера перехода)
                if not t_data['number'] and prev_text:
                    # Это продолжение предыдущего перехода
                    # Обновляем последний добавленный переход
                    last = (self.session.query(Transition)
                            .filter_by(operation_id=operation.id)
                            .order_by(Transition.sort_order.desc())
                            .first())
                    if last:
                        last.text = (last.text + ' ' + t_data['text']).strip()
                    continue

                trans = Transition(
                    operation_id=operation.id,
                    number=t_data['number'].rstrip('.').strip() or str(trans_sort + 1),
                    text=t_data['text'],
                    sort_order=trans_sort,
                )
                self.session.add(trans)
                trans_sort += 1
                prev_text = t_data['text']
                self.stats['transitions'] += 1

            # ── Инструмент ──
            seen_tools = set()
            for tool_str in op_data['tool_strings']:
                for tool_name in split_tools(tool_str):
                    if not tool_name or tool_name in seen_tools:
                        continue
                    seen_tools.add(tool_name)

                    # Определяем тип инструмента по ключевым словам
                    tool_type = 'Инструмент'
                    tname_lower = tool_name.lower()
                    if any(k in tname_lower for k in ('фреза', 'сверл', 'резец', 'зенкер',
                                                        'развёртка', 'метчик', 'плашка',
                                                        'полотно', 'пила')):
                        tool_type = 'Режущий'
                    elif any(k in tname_lower for k in ('штангенциркуль', 'микрометр', 'шаблон',
                                                         'лупа', 'угломер', 'нутромер',
                                                         'индикатор', 'скоба', 'калибр')):
                        tool_type = 'Измерительный'
                    elif any(k in tname_lower for k in ('тиски', 'патрон', 'оправка', 'прихват',
                                                         'кондуктор', 'приспособление', 'упор')):
                        tool_type = 'Вспомогательный'
                    elif any(k in tname_lower for k in ('напильник', 'шабер', 'надфиль',
                                                         'шкурка', 'ключ', 'молоток')):
                        tool_type = 'Слесарный'

                    tool = self.get_or_create_tool(tool_name[:100], tool_type)
                    if tool:
                        op_tool = OperationTool(
                            operation_id=operation.id,
                            tool_id=tool.id,
                            quantity=1,
                        )
                        self.session.add(op_tool)

        return True

    # ──── Массовый импорт ────────────────────────────────────────────────────

    def import_all(self, folder: str, progress_cb=None):
        """Импортирует все МК файлы из папки"""
        doxx_files = [f for f in os.listdir(folder)
                      if f.upper().endswith('.DOXX')
                      and 'МАРШРУТНАЯ КАРТА' in f.upper()]

        total = len(doxx_files)
        print(f"Найдено {total} файлов маршрутных карт")

        for i, fname in enumerate(sorted(doxx_files)):
            fpath = os.path.join(folder, fname)
            short = fname[:70]
            print(f"[{i+1:3d}/{total}] {short}...", end='', flush=True)
            try:
                ok = self.import_file(fpath, fname)
                print(" OK" if ok else " пропущен")
            except Exception as e:
                print(f" ОШИБКА: {e}")
                self.stats['errors'] += 1
                self.session.rollback()

            if progress_cb:
                progress_cb(i + 1, total, fname)

            # Коммит каждые 20 файлов
            if (i + 1) % 20 == 0:
                self.session.commit()
                print(f"  >> Сохранено {i+1} из {total}")

        self.session.commit()
        return self.stats


# ─────────────────────────────────────────────────────────────────────────────
# Точка входа
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Импорт ТП из DOXX файлов в базу данных АТПП'
    )
    parser.add_argument('--path', default=r'D:\тп',
                        help='Путь к папке с DOXX файлами')
    parser.add_argument('--clear', action='store_true',
                        help='Очистить таблицы перед импортом')
    args = parser.parse_args()

    if not os.path.isdir(args.path):
        print(f"Папка не найдена: {args.path}")
        sys.exit(1)

    print("Подключение к базе данных...")
    db = DatabaseManager()
    session = db.Session()

    try:
        if args.clear:
            print("Очистка таблиц...")
            for table in reversed(Base.metadata.sorted_tables):
                if table.name not in ('users',):
                    session.execute(table.delete())
            session.commit()
            print("Таблицы очищены")

        print(f"\nИмпорт из: {args.path}\n")
        importer = DoxxImporter(session)
        stats = importer.import_all(args.path)

        print("\n" + "="*60)
        print("ИТОГ ИМПОРТА:")
        print(f"  Изделий создано:      {stats['products']}")
        print(f"  ТП создано:           {stats['tps']}")
        print(f"  Операций создано:     {stats['operations']}")
        print(f"  Переходов создано:    {stats['transitions']}")
        print(f"  Инструментов создано: {stats['tools']}")
        print(f"  Материалов создано:   {stats['materials']}")
        print(f"  Оборудования создано: {stats['equipment']}")
        print(f"  Пропущено (дубли):    {stats['skipped']}")
        print(f"  Ошибок:               {stats['errors']}")
        print("="*60)

    except Exception as e:
        session.rollback()
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == '__main__':
    main()
