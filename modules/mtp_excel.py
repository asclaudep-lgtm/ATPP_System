"""Генерация маршрутно-технологического процесса (МТП) в формате .xlsx
поверх шаблона УЗГА-Инжиниринг.

Логика:
    1. Открываем готовый xlsx-шаблон ``resources/MTP_УЗГА_template.xlsx``
       (структура, рамки, штамп — оригинальные, как у предприятия).
    2. Заполняем «карты» ячеек данными по ТП и наряду.
    3. Если операций больше, чем строк в шаблоне — вставляем
       дополнительные строки между последней строкой маршрутки
       и подвалом, копируя merge-структуру.
    4. Вставляем небольшой штрих-код Code128 в шапке (между блоком
       «УЗГА-Инжиниринг» и заголовком «Маршрутно-технологический
       паспорт»).

Использование:

    from modules.mtp_excel import generate_mtp_excel

    bytes_ = generate_mtp_excel(
        session,
        tech_process_id=37,
        work_order_id=12,           # опционально
        out_path='/tmp/mtp.xlsx',   # опционально
        collapse_intermediate=True, # свернуть промывочные / промежуточные
                                    # контрольные операции
    )
"""
from __future__ import annotations

import io
from copy import copy
from pathlib import Path
from typing import Iterable, Optional, Union, List

# ────────────────────────────────────────────────────────────────────────
# Координаты ячеек (под шаблон УЗГА-Инжиниринг).
# Если форма поменяется — нужно обновить только эти константы.
# ────────────────────────────────────────────────────────────────────────

TEMPLATE_PATH = Path(__file__).resolve().parent.parent \
    / 'resources' / 'MTP_УЗГА_template.xlsx'

# Шапка
CELL_TITLE_F1 = (1, 6)            # «Маршрутно-технологический паспорт\n№ МТП ...»
CELL_FACTORY_NO = (2, 19)         # S2 — Заводской № / Порядковый №
CELL_WO_NUMBER = (2, 26)          # Z2 — № наряд-задания

# Блок проекта / изделия (строка значений = R4)
CELL_PROJECT_NAME = (4, 1)        # A4 — Наименование проекта
CELL_PRODUCT_NO = (4, 6)          # F4 — № изделия
CELL_DSE_DESIG = (4, 10)          # J4 — Обозначение ДСЕ согласно КД
CELL_DSE_NAME = (4, 17)           # Q4 — Наименование ДСЕ согласно КД
CELL_TP_NUMBER = (4, 22)          # V4 — Номер ТП
CELL_ORDER_CODE = (4, 28)         # AB4 — Шифр заказа / № Заказ

# КОМПЛЕКТОВАНИЕ — строка значений R7 (R6 — заголовки)
CELL_MAT_NAME = (7, 1)            # A7 — Наименование материала
CELL_MAT_DESIG = (7, 6)           # F7 — Обозначение материала (если есть)
CELL_MAT_QTY = (7, 7)             # G7 — Кол-во, шт
CELL_MAT_BLANK_SIZE = (7, 8)      # H7 — Размер заготовки
CELL_MAT_NORM = (7, 9)            # I7 — Норма расхода
CELL_MAT_CERT = (7, 10)           # J7 — Номер сертификата
CELL_MAT_HEAT = (7, 13)           # M7 — Номер партии/плавки

# МАРШРУТНО-ТЕХНОЛОГИЧЕСКОЕ ОПИСАНИЕ
ROW_OPS_HEADER = 9                # строка-заголовок таблицы
ROW_OPS_FIRST = 10                # первая строка с данными
ROW_OPS_LAST = 30                 # последняя строка в шаблоне (21 слот)
ROW_FOOTER_FIRST = 31             # первая строка подвала

# Колонки таблицы операций (start_col, end_col, label)
OPS_COL_SHOP = (1, 3)             # A:C — Участок
OPS_COL_NUMBER = (4, 5)           # D:E — № операции
OPS_COL_NAME = (6, 9)             # F:I — Наименование
OPS_COL_OPERATOR = (10, 12)       # J:L — Дата/подпись/ФИО исполнителя
OPS_COL_MASTER = (13, 15)         # M:O — Дата/подпись/ФИО мастера
OPS_COL_QC_PRES = (16, 18)        # P:R — Предъявлено ОТК
OPS_COL_QC_REJ = (19, 21)         # S:U — Отклонено ОТК
OPS_COL_QC_ACC = (22, 24)         # V:X — Принято ОТК
OPS_COL_QC_DATE = (25, 27)        # Y:AA — Дата/подпись/гриф ОТК
OPS_COL_NOTES = (28, 30)          # AB:AD — Особые отметки

# Штрих-код (картинка), якорь и размер в пикселях
BARCODE_ANCHOR = 'C1'             # на свободном месте между УЗГА-логотипом и заголовком
BARCODE_WIDTH_PX = 110
BARCODE_HEIGHT_PX = 38


class MTPExcelError(Exception):
    """Ошибка генерации МТП-xlsx."""


# ────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ────────────────────────────────────────────────────────────────────────

def _get_openpyxl():
    try:
        import openpyxl  # noqa: F401
        return True
    except ImportError as e:
        raise MTPExcelError(
            'Библиотека openpyxl не установлена.\n'
            'Установите её командой: pip install openpyxl'
        ) from e


def _generate_barcode_png(text: str) -> Optional[bytes]:
    """Возвращает PNG-байты штрих-кода Code128 или None при ошибке."""
    try:
        from modules.barcode_gen import generate_png
        return generate_png(text)
    except Exception:
        return None


def _set_value(ws, row: int, col: int, value):
    """Записывает значение в ячейку, корректно обрабатывая merged.

    Если ячейка — часть merged-диапазона, всё равно пишем в верх-лев,
    что соответствует визуальной ячейке."""
    cell = ws.cell(row=row, column=col)
    cell.value = value
    return cell


def _is_intermediate_check(op) -> bool:
    """Промежуточная контрольная операция (не последняя в маршруте)."""
    name = (op.name or '').lower().strip()
    return name.startswith('контроль') or name.startswith('контр')


def _is_wash(op) -> bool:
    """Промывочная операция."""
    name = (op.name or '').lower().strip()
    return name.startswith('промыв')


def _filter_collapse_intermediate(ops: list) -> list:
    """Свернуть промежуточные промывочные и контрольные операции:
    в МТП попадают все НЕ-промывочные / НЕ-контрольные операции, плюс
    последняя контрольная (финальная приёмка)."""
    if not ops:
        return ops
    # Найти последнюю контрольную (финальную)
    last_check_idx = None
    for i, op in enumerate(ops):
        if _is_intermediate_check(op):
            last_check_idx = i

    out = []
    for i, op in enumerate(ops):
        if _is_wash(op):
            continue
        if _is_intermediate_check(op) and i != last_check_idx:
            continue
        out.append(op)
    return out


def _apply_op_filters(
    ops: list,
    collapse_intermediate: bool,
    respect_include_in_mtp: bool = True,
) -> list:
    """Применяет к списку операций все фильтры МТП."""
    res = ops
    if respect_include_in_mtp:
        res = [o for o in res if getattr(o, 'include_in_mtp', True)]
    if collapse_intermediate:
        res = _filter_collapse_intermediate(res)
    return res


def _clone_row_format(ws, source_row: int, target_row: int):
    """Копирует стили и merge-диапазоны со строки ``source_row`` на
    ``target_row``. Не трогает другие строки.
    """
    # Стили ячеек
    for col in range(1, ws.max_column + 1):
        src = ws.cell(row=source_row, column=col)
        tgt = ws.cell(row=target_row, column=col)
        if src.has_style:
            tgt._style = copy(src._style)  # noqa: SLF001
    # Merge-диапазоны (только горизонтальные, в пределах одной строки)
    src_ranges = [
        mr for mr in list(ws.merged_cells.ranges)
        if mr.min_row == source_row and mr.max_row == source_row
    ]
    for mr in src_ranges:
        ws.merge_cells(
            start_row=target_row, start_column=mr.min_col,
            end_row=target_row, end_column=mr.max_col,
        )
    # Высота строки
    src_h = ws.row_dimensions[source_row].height
    if src_h:
        ws.row_dimensions[target_row].height = src_h


def _shift_footer_down(ws, extra: int):
    """Сдвигает подвал (rows 31..69) вниз на ``extra`` строк, чтобы
    освободить место для дополнительных строк операций.

    openpyxl сам по себе не корректно сдвигает merge-диапазоны при
    insert_rows для шапочно-привязанных ячеек, поэтому делаем вручную:
    1. Запоминаем содержимое и стили подвала.
    2. Запоминаем merge-диапазоны подвала.
    3. Очищаем подвал и удаляем эти merge.
    4. Дублируем шаблонную строку 30 на новые позиции 31..30+extra
       (в качестве дополнительных слотов операций).
    5. Перерисовываем подвал на новой позиции.
    """
    if extra <= 0:
        return ROW_FOOTER_FIRST

    # Граница подвала — оригинально rows 31..69 (max=69 по шаблону).
    footer_top = ROW_FOOTER_FIRST
    footer_bot = 69
    # Сохраняем содержимое + стили
    saved = {}  # (r, c) -> (value, style_dict)
    for r in range(footer_top, footer_bot + 1):
        for c in range(1, ws.max_column + 1):
            cell = ws.cell(row=r, column=c)
            if cell.value is not None or cell.has_style:
                saved[(r, c)] = (
                    cell.value,
                    copy(cell._style) if cell.has_style else None,  # noqa: SLF001
                )
    saved_heights = {r: ws.row_dimensions[r].height
                     for r in range(footer_top, footer_bot + 1)
                     if ws.row_dimensions[r].height}

    # Сохраняем merge подвала
    saved_merges = []
    for mr in list(ws.merged_cells.ranges):
        if mr.min_row >= footer_top and mr.max_row <= footer_bot:
            saved_merges.append((
                mr.min_row, mr.min_col, mr.max_row, mr.max_col
            ))
            ws.unmerge_cells(
                start_row=mr.min_row, start_column=mr.min_col,
                end_row=mr.max_row, end_column=mr.max_col,
            )

    # Очищаем содержимое подвала
    for r in range(footer_top, footer_bot + 1):
        for c in range(1, ws.max_column + 1):
            cell = ws.cell(row=r, column=c)
            cell.value = None
            cell._style = ws.cell(row=200, column=200)._style  # дефолт

    # Дублируем шаблонную строку операций (row 30 → 31..30+extra)
    template_row = ROW_OPS_LAST
    for i in range(extra):
        new_row = footer_top + i  # 31, 32, ...
        _clone_row_format(ws, template_row, new_row)

    # Перерисовываем подвал на новой позиции
    new_footer_top = footer_top + extra
    for (r, c), (val, style) in saved.items():
        new_r = r + extra
        cell = ws.cell(row=new_r, column=c)
        cell.value = val
        if style is not None:
            cell._style = style  # noqa: SLF001
    for r, h in saved_heights.items():
        ws.row_dimensions[r + extra].height = h
    for (r1, c1, r2, c2) in saved_merges:
        ws.merge_cells(
            start_row=r1 + extra, start_column=c1,
            end_row=r2 + extra, end_column=c2,
        )
    return new_footer_top


def _ensure_op_rows(ws, count: int):
    """Гарантирует, что в таблице операций есть ``count`` строк.
    Возвращает новую (или прежнюю) позицию первой строки подвала.
    """
    existing = ROW_FOOTER_FIRST - ROW_OPS_FIRST  # 21 слот
    if count <= existing:
        return ROW_FOOTER_FIRST
    extra = count - existing
    return _shift_footer_down(ws, extra)


# ────────────────────────────────────────────────────────────────────────
# Основная функция
# ────────────────────────────────────────────────────────────────────────

def generate_mtp_excel(
    session,
    *,
    tech_process_id: int,
    work_order_id: Optional[int] = None,
    out_path: Optional[Union[Path, str]] = None,
    collapse_intermediate: bool = True,
    respect_include_in_mtp: bool = True,
) -> bytes:
    """Собирает .xlsx с маршрутно-технологическим процессом по форме УЗГА.

    :param tech_process_id:        ID ТП (обязательный).
    :param work_order_id:          ID наряда (необязательный — без него
                                   распечатается «черновик» без штрих-кода).
    :param out_path:               путь для сохранения; если None — только bytes.
    :param collapse_intermediate:  свернуть промежуточные контрольные и
                                   промывочные операции (оставить только
                                   финальную контрольную); по умолчанию True.
    :param respect_include_in_mtp: учитывать поле ``Operation.include_in_mtp``
                                   из редактора ТП (по умолчанию True).

    Возвращает байты файла.
    """
    _get_openpyxl()
    import openpyxl
    from openpyxl.drawing.image import Image as XLImage

    if not TEMPLATE_PATH.exists():
        raise MTPExcelError(
            f'Шаблон УЗГА не найден: {TEMPLATE_PATH}.\n'
            'Положите Ваш бланк УЗГА в resources/MTP_УЗГА_template.xlsx'
        )

    from database.models import (
        TechProcess, WorkOrder, Operation, Equipment,
    )

    tp = session.get(TechProcess, tech_process_id)
    if tp is None:
        raise MTPExcelError(f'ТП id={tech_process_id} не найден.')

    wo = None
    if work_order_id is not None:
        wo = session.get(WorkOrder, work_order_id)
        if wo is None:
            raise MTPExcelError(f'Наряд id={work_order_id} не найден.')

    product = tp.product

    # ── Загружаем операции с переходами ──────────────────────────────
    ops_q = (session.query(Operation)
             .filter(Operation.tech_process_id == tp.id)
             .filter(Operation.is_deleted == False)  # noqa: E712
             .order_by(Operation.sort_order, Operation.number))
    ops = list(ops_q.all())
    ops = _apply_op_filters(ops, collapse_intermediate,
                            respect_include_in_mtp)

    # ── Открываем шаблон ─────────────────────────────────────────────
    wb = openpyxl.load_workbook(str(TEMPLATE_PATH))
    ws = wb.active

    # ── Заполняем шапку ──────────────────────────────────────────────
    title_text = 'Маршрутно-технологический паспорт'
    if wo:
        title_text = f'{title_text}\n№ МТП {wo.number}'
    else:
        title_text = f'{title_text}\n№ МТП'
    _set_value(ws, *CELL_TITLE_F1, title_text)

    if wo:
        _set_value(ws, *CELL_FACTORY_NO, str(wo.id))
        _set_value(ws, *CELL_WO_NUMBER, wo.number)

    # Информация о проекте / изделии
    _set_value(ws, *CELL_PROJECT_NAME,
               getattr(product, 'group_name', None) or '')
    _set_value(ws, *CELL_PRODUCT_NO,
               product.designation if product else '')
    _set_value(ws, *CELL_DSE_DESIG,
               product.designation if product else '')
    _set_value(ws, *CELL_DSE_NAME,
               product.name if product else '')
    _set_value(ws, *CELL_TP_NUMBER, tp.number)
    if wo:
        _set_value(ws, *CELL_ORDER_CODE, wo.customer_order or '')

    # ── Комплектование (материал) ────────────────────────────────────
    # Берём материал из связи product → material, если она есть.
    mat_name = ''
    mat_desig = ''
    blank_size = ''
    if product and getattr(product, 'material_id', None):
        try:
            from database.models import Material
            material = session.get(Material, product.material_id)
            if material:
                mat_name = material.name or ''
                mat_desig = material.designation or ''
        except Exception:
            pass
    blank_size = (getattr(product, 'blank_dimensions', None) or '')

    _set_value(ws, *CELL_MAT_NAME, mat_name)
    _set_value(ws, *CELL_MAT_DESIG, mat_desig)
    if wo:
        _set_value(ws, *CELL_MAT_QTY, wo.qty_total)
    _set_value(ws, *CELL_MAT_BLANK_SIZE, blank_size)
    # Норму расхода и сертификат пока оставляем пустыми (заполняет мастер)

    # ── Операции (маршрутно-технологическое описание) ────────────────
    # Если операций больше, чем мест в шаблоне — расширяем
    new_footer_row = _ensure_op_rows(ws, len(ops))

    for idx, op in enumerate(ops):
        row = ROW_OPS_FIRST + idx

        # Участок (operation.shop или название цеха)
        shop = (getattr(op, 'shop', None) or '').strip()
        _set_value(ws, row, OPS_COL_SHOP[0], shop or '')

        # № операции
        _set_value(ws, row, OPS_COL_NUMBER[0], op.number or '')

        # Наименование операции (с указанием оборудования)
        op_text = op.name or ''
        if op.equipment_id:
            try:
                eq = session.get(Equipment, op.equipment_id)
                if eq:
                    eq_label = eq.name or ''
                    if eq.model:
                        eq_label = f'{eq_label} ({eq.model})'
                    if eq_label:
                        op_text = f'{op_text}\n{eq_label}'
            except Exception:
                pass
        _set_value(ws, row, OPS_COL_NAME[0], op_text)

        # Остальные колонки оставляем пустыми — заполняет цех

    # ── Штрих-код в шапке ────────────────────────────────────────────
    if wo and wo.barcode:
        png = _generate_barcode_png(wo.barcode)
        if png:
            try:
                buf = io.BytesIO(png)
                img = XLImage(buf)
                img.width = BARCODE_WIDTH_PX
                img.height = BARCODE_HEIGHT_PX
                ws.add_image(img, BARCODE_ANCHOR)
            except Exception:
                # fallback — текст рядом с заголовком
                pass

    # ── Сохраняем ────────────────────────────────────────────────────
    buf_out = io.BytesIO()
    wb.save(buf_out)
    data = buf_out.getvalue()
    if out_path is not None:
        Path(out_path).write_bytes(data)
    return data
