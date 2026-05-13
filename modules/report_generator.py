"""
Генератор отчётов и ведомостей по шаблонам УЗГА
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime

import openpyxl
from openpyxl.styles import (
    Font, Alignment, Border, Side, PatternFill, GradientFill
)
from openpyxl.utils import get_column_letter

from database.models import (
    TechProcess, Operation, Transition, MaterialNorm, CostCalculation,
    Material, Equipment, Profession, Product
)
from config import EXPORT_DIR, TEMPLATES_DIR, product_export_dir


# Стиль тонкой рамки
_thin = Side(style='thin')
_BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
_BORDER_LR = Border(left=_thin, right=_thin)
_BORDER_BOT = Border(left=_thin, right=_thin, bottom=_thin)

_HEADER_FILL = PatternFill("solid", fgColor="BDD7EE")   # синеватый
_TITLE_FILL  = PatternFill("solid", fgColor="2F75B6")
_ROW_ALT     = PatternFill("solid", fgColor="EBF3FB")


def _cell(ws, row, col, value=None, bold=False, center=False, fill=None, border=True, wrap=False):
    c = ws.cell(row=row, column=col, value=value)
    if bold:
        c.font = Font(bold=True, size=9)
    else:
        c.font = Font(size=9)
    if center:
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=wrap)
    else:
        c.alignment = Alignment(vertical='center', wrap_text=wrap)
    if fill:
        c.fill = fill
    if border:
        c.border = _BORDER
    return c


def _title_row(ws, row, text, ncols):
    """Строка-заголовок документа"""
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(bold=True, size=12, color='FFFFFF')
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.fill = _TITLE_FILL
    ws.row_dimensions[row].height = 22


def _auto_width(ws, col_widths):
    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _add_status_watermark(ws, status_value: str):
    """Добавить водяной знак по статусу ТП.

    Для DRAFT / REWORK / REVIEW — большая полупрозрачная (серая)
    надпись «ЧЕРНОВИК» / «НА ДОРАБОТКЕ» / «НА СОГЛАСОВАНИИ» поверх
    листа. Реализовано через openpyxl HeaderFooter и центральную
    «штамп-ячейку» (т.к. в xlsx нет настоящего слоя водяного знака).
    """
    txt_map = {
        'DRAFT': 'ЧЕРНОВИК',
        'REWORK': 'НА ДОРАБОТКЕ',
        'REVIEW': 'НА СОГЛАСОВАНИИ',
    }
    label = txt_map.get(str(status_value).upper())
    if not label:
        return
    # Печатный заголовок — водяной знак центром каждой страницы
    try:
        ws.oddHeader.center.text = label
        ws.oddHeader.center.size = 36
        ws.oddHeader.center.color = 'CCCCCC'
        ws.oddFooter.center.text = (
            f'НЕ УТВЕРЖДЕНО — {label} — '
            f'{datetime.now().strftime("%d.%m.%Y %H:%M")}'
        )
        ws.oddFooter.center.size = 10
        ws.oddFooter.center.color = 'AA0000'
    except Exception:
        pass


def _ensure_print_settings(ws):
    """Стандартные настройки печати: A4, поля 1.5см, fit-to-width."""
    try:
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_margins.left = 0.6
        ws.page_margins.right = 0.4
        ws.page_margins.top = 0.7
        ws.page_margins.bottom = 0.7
        ws.page_margins.header = 0.3
        ws.page_margins.footer = 0.3
    except Exception:
        pass


class ReportGenerator:
    """Генератор производственных ведомостей и отчётов"""

    def __init__(self, session):
        self.session = session

    # ─────────────────────────────────────────────────────────────────
    # 1. Маршрутно-сопроводительная карта
    # ─────────────────────────────────────────────────────────────────
    def generate_route_map(self, tp_id: int, quantity: int = 1) -> Path:
        """
        Маршрутно-сопроводительная карта (МСК)
        Колонки аналогичны шаблону «Маршрутно-сопроводительная карта.xls»
        """
        tp = self.session.query(TechProcess).get(tp_id)
        if not tp:
            raise ValueError(f'ТП {tp_id} не найден')

        prod = tp.product
        mat  = prod.material if prod else None

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'МСК'
        ws.page_setup.orientation = 'landscape'
        ws.page_setup.paperSize = 9  # A4

        cols = [
            'Обозначение ДСЕ', 'Наименование ДСЕ',
            'Материал', 'Марка',
            'Размер заготовки', 'Масса загот., кг',
            'Кол-во в изд.', 'Ед.изм',
            '№ оп.', 'Наименование операции',
            'Разряд', 'Тшт, ч',
            'Кол-во в партии', 'Кол-во в комп.',
            'Суммарная Тшт, ч',
        ]
        _auto_width(ws, [20, 25, 14, 14, 18, 13, 10, 7, 6, 28, 7, 10, 12, 12, 14])

        r = 1
        _title_row(ws, r, f'МАРШРУТНО-СОПРОВОДИТЕЛЬНАЯ КАРТА', len(cols))
        ws.row_dimensions[r].height = 22
        r += 1

        # Реквизиты
        info = [
            ('Изделие:', f"{prod.designation}  —  {prod.name}" if prod else ''),
            ('ТП №:', tp.number),
            ('Версия:', tp.version or '1.0'),
            ('Материал:', f"{mat.name} {mat.grade or ''}".strip() if mat else '—'),
            ('Количество:', str(quantity)),
        ]
        for label, val in info:
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
            ws.cell(row=r, column=1, value=label).font = Font(bold=True, size=9)
            ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=8)
            ws.cell(row=r, column=4, value=val).font = Font(size=9)
            r += 1
        r += 1

        # Шапка таблицы
        ws.row_dimensions[r].height = 32
        for ci, col in enumerate(cols, start=1):
            _cell(ws, r, ci, col, bold=True, center=True, fill=_HEADER_FILL, wrap=True)
        ws.freeze_panes = f'A{r+1}'
        r += 1

        # Данные (только операции, помеченные к выдаче в МТП)
        for op in [o for o in sorted(tp.operations, key=lambda o: o.sort_order)
                   if bool(getattr(o, 'include_in_mtp', True))]:
            tshт_h = round((op.t_piece or 0) / 60, 4)
            total_h = round(tshт_h * quantity, 4)

            is_alt = (r % 2 == 0)
            fill = _ROW_ALT if is_alt else None

            row_data = [
                prod.designation if prod else '',
                prod.name if prod else '',
                mat.name if mat else '',
                mat.grade if mat else '',
                prod.dimensions if prod else '',
                prod.mass if prod else '',
                quantity,
                'шт',
                op.number,
                op.name,
                op.grade or '',
                tshт_h,
                quantity,
                quantity,
                total_h,
            ]
            for ci, val in enumerate(row_data, start=1):
                _cell(ws, r, ci, val, fill=fill, center=(ci not in (2, 10)))
            r += 1

        # Итог
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        ws.cell(row=r, column=1, value='ИТОГО:').font = Font(bold=True, size=9)
        total_tshт = sum(
            (op.t_piece or 0) for op in tp.operations
            if bool(getattr(op, 'include_in_mtp', True))
        ) / 60
        _cell(ws, r, 12, round(total_tshт, 4), bold=True, center=True)
        _cell(ws, r, 15, round(total_tshт * quantity, 4), bold=True, center=True)

        # Подписи
        r += 2
        ws.cell(row=r, column=1, value=f'Разработал: ________________________  Дата: {datetime.now().strftime("%d.%m.%Y")}')
        r += 1
        ws.cell(row=r, column=1, value='Проверил:  ________________________')

        fname = f'МСК_{tp.number}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        path = product_export_dir(tp.product) / fname
        # Водяной знак / настройки печати
        try:
            for _ws in wb.worksheets:
                _ensure_print_settings(_ws)
                _add_status_watermark(_ws, getattr(tp.status, "name", str(tp.status)))
        except Exception:
            pass
        wb.save(path)
        return path

    # ─────────────────────────────────────────────────────────────────
    # 1b. Маршрутно-технологический паспорт (МТП) — по шаблону УЗГА
    # ─────────────────────────────────────────────────────────────────
    def generate_mtp(
        self,
        tp_id: int,
        project_name: str = '',
        kit_number: str = '',
        order_number: str = '',
        serial_number: str = '',
        order_task_number: str = '',
        template_path: Path | None = None,
    ) -> Path:
        """
        Маршрутно-технологический паспорт (МТП) по шаблону УЗГА.

        Заполняет переданный xlsx-шаблон данными из БД (без перекладки
        форматирования). Учитывает Operation.include_in_mtp — операции с
        этим флагом False пропускаются.

        Параметры project_name / kit_number / order_number / serial_number /
        order_task_number — внешние сведения, которых нет в модели; могут
        быть пусты.
        """
        tp = self.session.query(TechProcess).get(tp_id)
        if not tp:
            raise ValueError(f'ТП {tp_id} не найден')

        prod: Product | None = tp.product
        mat: Material | None = prod.material if prod else None

        # Норма расхода (если задана для ТП)
        mn: MaterialNorm | None = (
            self.session.query(MaterialNorm)
            .filter_by(tech_process_id=tp.id)
            .first()
        )
        # Если норма указана для другого материала — берём оттуда
        if mn and mn.material_id and (not mat or mn.material_id != mat.id):
            mat = self.session.query(Material).get(mn.material_id) or mat

        if template_path is None:
            template_path = TEMPLATES_DIR / 'mtp_template.xlsx'
        template_path = Path(template_path)
        if not template_path.exists():
            raise FileNotFoundError(
                f'Шаблон МТП не найден: {template_path}'
            )

        wb = openpyxl.load_workbook(template_path)
        ws = wb.active

        # ── Шапка (строка 4 — данные под заголовками строки 3) ──
        ws['A4'] = project_name or ''
        ws['F4'] = kit_number or ''
        ws['J4'] = (prod.designation if prod else '') or ''
        ws['Q4'] = (prod.name if prod else '') or ''
        ws['V4'] = tp.number or ''
        ws['AB4'] = order_number or ''

        # Заводской номер / порядковый номер; № наряд-задания (правая шапка)
        if serial_number:
            ws['S2'] = serial_number
        if order_task_number:
            ws['Z2'] = order_task_number

        # ── Комплектование (строка 7) ──
        # Категория материала (Пруток, Лист, …) — берём из blank_type изделия,
        # если задано; иначе оставляем пусто.
        ws['A7'] = (prod.blank_type if prod and prod.blank_type else '') or ''

        # Полное обозначение материала (например «Пруток Д16ч.Т.КР 30 ОСТ1 90395-91»)
        # В справочнике УЗГА name/grade/gost иногда дублируют друг друга —
        # склеиваем только уникальные непустые куски.
        material_designation = ''
        if mat:
            seen, parts = set(), []
            for raw in (mat.name, mat.grade, mat.gost):
                v = (raw or '').strip()
                if v and v not in seen:
                    seen.add(v)
                    parts.append(v)
            material_designation = ' '.join(parts)
        ws['F7'] = material_designation

        ws['G7'] = (
            prod.quantity_in_assembly
            if prod and prod.quantity_in_assembly
            else ''
        )

        blank_size = ''
        for candidate in (
            mn.blank_dimensions if mn else None,
            mn.blank_profile if mn else None,
            prod.blank_dimensions if prod else None,
            prod.dimensions if prod else None,
        ):
            v = (candidate or '').strip()
            # Не пишем сюда дубликат полного обозначения материала
            if v and v != material_designation:
                blank_size = v
                break
        ws['H7'] = blank_size

        norm_per_piece = mn.norm_per_piece if mn and mn.norm_per_piece else None
        ws['I7'] = norm_per_piece if norm_per_piece is not None else ''

        # ── Маршрутно-технологическое описание (строки 10..30, через одну) ──
        ops = [
            o for o in sorted(tp.operations, key=lambda o: o.sort_order or 0)
            if bool(getattr(o, 'include_in_mtp', True))
        ]

        # Двухстрочные слоты на странице 1: 10, 12, 14, …, 30 → 11 слотов
        page1_rows = list(range(10, 31, 2))
        # Двухстрочные слоты на странице 2: 37, 39, 41, …, 49 → 7 слотов
        page2_rows = list(range(37, 50, 2))
        slots = page1_rows + page2_rows

        for op, row in zip(ops, slots):
            ws.cell(row=row, column=1, value=op.shop or '001')          # A — Участок
            ws.cell(row=row, column=4, value=op.number or '')           # D — № операции
            ws.cell(row=row, column=6, value=op.name or '')             # F — Наименование

        # Если операций больше, чем слотов — складываем хвост в «Особые отметки»
        if len(ops) > len(slots):
            extra_lines = [
                f'{op.number or "?"}  {op.name or ""}'
                for op in ops[len(slots):]
            ]
            ws.cell(
                row=slots[-1], column=28,  # AB
                value='Доп.: ' + '; '.join(extra_lines)
            )

        # ── Подписи (строка 31..32) ──
        author_name = (tp.author.full_name if tp.author and tp.author.full_name
                       else (tp.author.username if tp.author else ''))
        ws['G31'] = author_name

        # ── Сохранение ──
        safe_num = (tp.number or f'tp{tp.id}').replace('/', '-')
        fname = f'МТП_{safe_num}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        path = product_export_dir(tp.product) / fname
        # Водяной знак / настройки печати
        try:
            for _ws in wb.worksheets:
                _ensure_print_settings(_ws)
                _add_status_watermark(_ws, getattr(tp.status, "name", str(tp.status)))
        except Exception:
            pass
        wb.save(path)
        return path

    # ─────────────────────────────────────────────────────────────────
    # 2. Ведомость норм времени
    # ─────────────────────────────────────────────────────────────────
    def generate_time_norms(self, tp_id: int, quantity: int = 1) -> Path:
        """
        Ведомость норм времени по ТП
        Аналог шаблона «Ведомость норм времени.xls»
        """
        tp = self.session.query(TechProcess).get(tp_id)
        if not tp:
            raise ValueError(f'ТП {tp_id} не найден')

        prod = tp.product

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Ведомость НВ'

        cols = [
            'Обозначение', 'Наименование', 'Кол-во',
            'Тшт, мин', 'Тпз, мин', 'Тшт сумм., мин', 'Тшт сумм., ч',
            'Оп. №', 'Наименование операции', 'Оборудование', 'Профессия', 'Разряд',
        ]
        _auto_width(ws, [20, 25, 8, 10, 10, 12, 10, 7, 28, 22, 20, 8])

        r = 1
        _title_row(ws, r, 'ВЕДОМОСТЬ НОРМ ВРЕМЕНИ', len(cols))
        r += 1

        info = [
            ('ТП №:', tp.number),
            ('Изделие:', f"{prod.designation}  {prod.name}" if prod else ''),
            ('Количество в заказе:', str(quantity)),
        ]
        for label, val in info:
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
            ws.cell(row=r, column=1, value=label).font = Font(bold=True, size=9)
            ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=8)
            ws.cell(row=r, column=4, value=val).font = Font(size=9)
            r += 1
        r += 1

        ws.row_dimensions[r].height = 32
        for ci, col in enumerate(cols, start=1):
            _cell(ws, r, ci, col, bold=True, center=True, fill=_HEADER_FILL, wrap=True)
        ws.freeze_panes = f'A{r+1}'
        r += 1

        desig = prod.designation if prod else ''
        name  = prod.name if prod else ''

        total_piece = 0.0
        total_setup = 0.0

        for op in sorted(tp.operations, key=lambda o: o.sort_order):
            tshт = op.t_piece or 0
            tpz  = op.t_setup or 0
            total_piece += tshт
            total_setup += tpz

            fill = _ROW_ALT if r % 2 == 0 else None
            row_data = [
                desig, name, quantity,
                round(tshт, 2), round(tpz, 2),
                round(tshт * quantity, 2),
                round(tshт * quantity / 60, 4),
                op.number, op.name,
                op.equipment.name if op.equipment else '',
                op.profession.name if op.profession else '',
                op.grade or '',
            ]
            for ci, val in enumerate(row_data, start=1):
                _cell(ws, r, ci, val, fill=fill, center=(ci not in (2, 9, 10, 11)))
            r += 1

        # Итог
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        ws.cell(row=r, column=1, value='ИТОГО:').font = Font(bold=True, size=9)
        _cell(ws, r, 4, round(total_piece, 2), bold=True, center=True)
        _cell(ws, r, 5, round(total_setup, 2), bold=True, center=True)
        _cell(ws, r, 6, round(total_piece * quantity, 2), bold=True, center=True)
        _cell(ws, r, 7, round(total_piece * quantity / 60, 4), bold=True, center=True)

        r += 2
        ws.cell(row=r, column=1, value=f'Дата: {datetime.now().strftime("%d.%m.%Y")}')

        fname = f'ВНВ_{tp.number}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        path = product_export_dir(tp.product) / fname
        # Водяной знак / настройки печати
        try:
            for _ws in wb.worksheets:
                _ensure_print_settings(_ws)
                _add_status_watermark(_ws, getattr(tp.status, "name", str(tp.status)))
        except Exception:
            pass
        wb.save(path)
        return path

    # ─────────────────────────────────────────────────────────────────
    # 3. Калькуляция себестоимости
    # ─────────────────────────────────────────────────────────────────
    def generate_cost_report(self, tp_id: int) -> Path:
        """
        Калькуляция себестоимости ДСЕ
        Аналог шаблона «Калькуляция себестоимости.xls»
        """
        tp = self.session.query(TechProcess).get(tp_id)
        if not tp:
            raise ValueError(f'ТП {tp_id} не найден')

        cost = (self.session.query(CostCalculation)
                .filter_by(tech_process_id=tp_id)
                .first())

        prod = tp.product

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Калькуляция'

        cols = [
            'Обозначение', 'Наименование', 'Ед.изм',
            'Материалы, руб', 'ЗП, руб', 'Соц. отч., руб',
            'Оборудование, руб', 'Цеховые расх., руб', 'Общезав. расх., руб',
            'Производ. с/с, руб', 'Полная с/с, руб', 'Цена (с рент.), руб', 'Прибыль, руб',
        ]
        _auto_width(ws, [22, 28, 7, 14, 12, 13, 14, 14, 15, 16, 14, 16, 12])

        r = 1
        _title_row(ws, r, 'КАЛЬКУЛЯЦИЯ СЕБЕСТОИМОСТИ', len(cols))
        r += 1

        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        ws.cell(row=r, column=1, value=f'ТП №: {tp.number}   Изделие: {prod.designation if prod else ""}   {prod.name if prod else ""}').font = Font(bold=True, size=9)
        ws.merge_cells(start_row=r, start_column=8, end_row=r, end_column=10)
        ws.cell(row=r, column=8, value=f'Дата: {datetime.now().strftime("%d.%m.%Y")}').font = Font(size=9)
        r += 2

        ws.row_dimensions[r].height = 36
        for ci, col in enumerate(cols, start=1):
            _cell(ws, r, ci, col, bold=True, center=True, fill=_HEADER_FILL, wrap=True)
        ws.freeze_panes = f'A{r+1}'
        r += 1

        desig = prod.designation if prod else ''
        name  = prod.name if prod else ''

        if cost:
            row_data = [
                desig, name, 'шт',
                round(cost.material_cost or 0, 2),
                round(cost.labor_cost or 0, 2),
                round(cost.social_contributions or 0, 2),
                round(cost.equipment_cost or 0, 2),
                round(cost.shop_overhead or 0, 2),
                round(cost.factory_overhead or 0, 2),
                round(cost.production_cost or 0, 2),
                round(cost.full_cost or 0, 2),
                round(cost.price or 0, 2),
                round(cost.profit or 0, 2),
            ]
        else:
            row_data = [desig, name, 'шт'] + [0.0] * 10

        for ci, val in enumerate(row_data, start=1):
            center = ci not in (2,)
            _cell(ws, r, ci, val, center=center)

        if cost:
            r += 2
            note_fill = PatternFill("solid", fgColor="FFF2CC")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
            n = ws.cell(row=r, column=1, value='Примечание: расчёт выполнен в системе АТПП')
            n.font = Font(italic=True, size=8)
            n.fill = note_fill

        r += 3
        ws.cell(row=r, column=1, value=f'Разработал: ____________________________   Дата: {datetime.now().strftime("%d.%m.%Y")}').font = Font(size=9)

        fname = f'Калькуляция_{tp.number}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        path = product_export_dir(tp.product) / fname
        # Водяной знак / настройки печати
        try:
            for _ws in wb.worksheets:
                _ensure_print_settings(_ws)
                _add_status_watermark(_ws, getattr(tp.status, "name", str(tp.status)))
        except Exception:
            pass
        wb.save(path)
        return path

    # ─────────────────────────────────────────────────────────────────
    # 4. Ведомость материалов
    # ─────────────────────────────────────────────────────────────────
    def generate_material_norms_report(self, tp_id: int, quantity: int = 1) -> Path:
        """
        Ведомость норм расхода материалов
        Аналог шаблона «Ведомость материалов.xls»
        """
        tp = self.session.query(TechProcess).get(tp_id)
        if not tp:
            raise ValueError(f'ТП {tp_id} не найден')

        norms = (self.session.query(MaterialNorm)
                 .filter_by(tech_process_id=tp_id)
                 .all())

        prod = tp.product

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Вед. материалов'

        cols = [
            'Обозначение', 'Наименование', 'Материал', 'Марка', 'ГОСТ/ТУ',
            'Профиль', 'Норма/шт, кг', 'Кол-во', 'Норма итого, кг',
            'Цена, руб/кг', 'Стоимость/шт, руб', 'Стоимость итого, руб',
            'Отходы, %', 'КИМ',
        ]
        _auto_width(ws, [20, 25, 16, 14, 14, 14, 12, 8, 14, 12, 16, 18, 10, 8])

        r = 1
        _title_row(ws, r, 'ВЕДОМОСТЬ НОРМ РАСХОДА МАТЕРИАЛОВ', len(cols))
        r += 1

        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
        ws.cell(row=r, column=1, value=f'ТП №: {tp.number}   {prod.designation if prod else ""} — {prod.name if prod else ""}').font = Font(bold=True, size=9)
        ws.merge_cells(start_row=r, start_column=10, end_row=r, end_column=12)
        ws.cell(row=r, column=10, value=f'Кол-во в заказе: {quantity} шт').font = Font(size=9)
        r += 2

        ws.row_dimensions[r].height = 36
        for ci, col in enumerate(cols, start=1):
            _cell(ws, r, ci, col, bold=True, center=True, fill=_HEADER_FILL, wrap=True)
        ws.freeze_panes = f'A{r+1}'
        r += 1

        desig = prod.designation if prod else ''
        name  = prod.name if prod else ''

        total_cost = 0.0
        for n in norms:
            mat = self.session.query(Material).get(n.material_id) if n.material_id else None
            mat_name = mat.name if mat else ''
            mat_grade = mat.grade if mat else ''
            mat_gost  = mat.gost if mat else ''
            norm_total = (n.norm_per_piece or 0) * quantity
            cost_total = (n.cost_per_piece or 0) * quantity
            total_cost += cost_total
            kim = round(1 - (n.waste_percent or 0) / 100, 3) if n.waste_percent else '—'

            fill = _ROW_ALT if r % 2 == 0 else None
            row_data = [
                desig, name, mat_name, mat_grade, mat_gost,
                n.blank_profile or '',
                round(n.norm_per_piece or 0, 4), quantity, round(norm_total, 4),
                round(mat.price_per_kg, 2) if mat and mat.price_per_kg else 0,
                round(n.cost_per_piece or 0, 2), round(cost_total, 2),
                round(n.waste_percent or 0, 1), kim,
            ]
            for ci, val in enumerate(row_data, start=1):
                _cell(ws, r, ci, val, fill=fill, center=(ci not in (2, 3)))
            r += 1

        if not norms:
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(cols))
            ws.cell(row=r, column=1, value='Нормы расхода материала не заданы').font = Font(italic=True, color='999999', size=9)
            r += 1

        # Итог
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=11)
        ws.cell(row=r, column=1, value='ИТОГО стоимость материалов:').font = Font(bold=True, size=9)
        _cell(ws, r, 12, round(total_cost, 2), bold=True, center=True)

        r += 2
        ws.cell(row=r, column=1, value=f'Дата: {datetime.now().strftime("%d.%m.%Y")}').font = Font(size=9)

        fname = f'ВМ_{tp.number}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        path = product_export_dir(tp.product) / fname
        # Водяной знак / настройки печати
        try:
            for _ws in wb.worksheets:
                _ensure_print_settings(_ws)
                _add_status_watermark(_ws, getattr(tp.status, "name", str(tp.status)))
        except Exception:
            pass
        wb.save(path)
        return path

    # ─────────────────────────────────────────────────────────────────
    # 6. Карта эскизов (КЭ) — ГОСТ 3.1408
    # ─────────────────────────────────────────────────────────────────
    def generate_sketch_card(self, tp_id: int) -> Path:
        """
        Карта эскизов: для каждой операции/перехода с прикреплёнными
        эскизами вставляем картинку (PDF — ссылкой на файл).

        Изображения ужимаются по размеру колонки (макс. ~480 px ширины,
        ~360 px высоты) с сохранением пропорций.
        """
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.utils import get_column_letter
        from PIL import Image as PILImage
        from database.models import Sketch
        from config import DATA_DIR

        tp = self.session.query(TechProcess).get(tp_id)
        if not tp:
            raise ValueError(f'ТП #{tp_id} не найден')

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Карта эскизов'
        ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.print_options.horizontalCentered = True

        # Колонки A=подпись/мета, B=изображение
        ws.column_dimensions['A'].width = 28
        ws.column_dimensions['B'].width = 75

        # ── Шапка ──
        ws.merge_cells('A1:B1')
        c = ws['A1']
        c.value = f'КАРТА ЭСКИЗОВ — {tp.product.designation} {tp.product.name}'
        c.font = Font(name='Arial', size=14, bold=True)
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 26

        ws.merge_cells('A2:B2')
        c = ws['A2']
        variant_part = f' (исп.: {tp.execution_variant})' if tp.execution_variant else ''
        c.value = (
            f'ТП {tp.number}{variant_part}   |   '
            f'Версия {tp.version or "1.0"}   |   '
            f'Дата формирования: {datetime.now().strftime("%d.%m.%Y %H:%M")}'
        )
        c.font = Font(name='Arial', size=10, italic=True)
        c.alignment = Alignment(horizontal='center')
        ws.row_dimensions[2].height = 18

        row = 4
        any_sketches = False
        max_w_px, max_h_px = 480, 360
        EMU_PER_PX = 9525  # (для openpyxl image width in pixels)

        operations = (
            self.session.query(Operation)
            .filter_by(tech_process_id=tp_id)
            .order_by(Operation.sort_order)
            .all()
        )

        def _resolve(stored: str) -> Path:
            p = Path(stored)
            return p if p.is_absolute() else (DATA_DIR / p)

        def _embed_image(img_path: Path, anchor_row: int) -> int:
            """Вставить картинку, отмасштабировать. Вернуть высоту строки в pt."""
            try:
                with PILImage.open(img_path) as pil:
                    pil = pil.convert('RGB')
                    w, h = pil.size
            except Exception:
                return 18
            scale = min(max_w_px / w, max_h_px / h, 1.0)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            xl_img = XLImage(str(img_path))
            xl_img.width = new_w
            xl_img.height = new_h
            ws.add_image(xl_img, f'B{anchor_row}')
            # высота строки в pt; 1 px ≈ 0.75 pt
            return max(60, int(new_h * 0.75) + 8)

        for op in operations:
            op_sketches = list(getattr(op, 'sketches', []) or [])
            tr_with_sk = []
            for tr in (op.transitions or []):
                tr_sk = list(getattr(tr, 'sketches', []) or [])
                if tr_sk:
                    tr_with_sk.append((tr, tr_sk))
            if not op_sketches and not tr_with_sk:
                continue

            any_sketches = True

            # Заголовок операции
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
            c = ws.cell(row=row, column=1, value=f'Операция {op.number} — {op.name}')
            c.font = Font(name='Arial', size=12, bold=True)
            c.fill = _HEADER_FILL
            c.alignment = Alignment(horizontal='left', vertical='center', indent=1)
            c.border = _BORDER
            ws.row_dimensions[row].height = 22
            row += 1

            # Эскизы операции
            for sk in op_sketches:
                row = self._render_sketch_row(
                    ws, row, sk, _resolve, _embed_image, level='op'
                )

            # Эскизы переходов
            for tr, tr_sketches in tr_with_sk:
                ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
                c = ws.cell(
                    row=row, column=1,
                    value=f'   Переход {tr.number}: {(tr.text or "")[:120]}'
                )
                c.font = Font(name='Arial', size=10, bold=True, italic=True)
                c.fill = PatternFill('solid', fgColor='F4F8FB')
                c.alignment = Alignment(horizontal='left', vertical='center', indent=1)
                c.border = _BORDER
                ws.row_dimensions[row].height = 18
                row += 1
                for sk in tr_sketches:
                    row = self._render_sketch_row(
                        ws, row, sk, _resolve, _embed_image, level='tr'
                    )

            row += 1   # пустая строка между операциями

        if not any_sketches:
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
            c = ws.cell(
                row=row, column=1,
                value='В этом ТП нет операций или переходов с прикреплёнными эскизами.'
            )
            c.font = Font(name='Arial', size=11, italic=True, color='888888')
            c.alignment = Alignment(horizontal='center', vertical='center')
            ws.row_dimensions[row].height = 30

        # Подвал
        row += 2
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        ws.cell(
            row=row, column=1,
            value=f'Разработал: {tp.author.full_name if tp.author else "____________________"}   '
                  f'Дата: {datetime.now().strftime("%d.%m.%Y")}'
        ).font = Font(name='Arial', size=10, italic=True)

        safe_num = (tp.number or f'tp{tp.id}').replace('/', '-')
        fname = f'КЭ_{safe_num}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        path = product_export_dir(tp.product) / fname
        # Водяной знак / настройки печати
        try:
            for _ws in wb.worksheets:
                _ensure_print_settings(_ws)
                _add_status_watermark(_ws, getattr(tp.status, "name", str(tp.status)))
        except Exception:
            pass
        wb.save(path)
        return path

    def _render_sketch_row(self, ws, row, sk, resolve_fn, embed_fn, level='op'):
        """Одна строка эскиза в карте: подпись слева, картинка справа."""
        from openpyxl.styles import Alignment, Font

        full = resolve_fn(sk.stored_path)
        title = (sk.title or sk.original_filename or full.name).strip()
        ftype = (sk.file_type or '').lower()

        # Левая ячейка — описание
        cap = (
            f'{title}\n'
            f'Файл: {sk.original_filename or full.name}\n'
            f'Тип: {ftype.upper() if ftype else "FILE"}'
        )
        cell = ws.cell(row=row, column=1, value=cap)
        cell.font = Font(name='Arial', size=10)
        cell.alignment = Alignment(
            horizontal='left', vertical='center', wrap_text=True, indent=1
        )
        cell.border = _BORDER

        # Правая ячейка — картинка / ссылка
        img_cell = ws.cell(row=row, column=2)
        img_cell.border = _BORDER
        img_cell.alignment = Alignment(horizontal='center', vertical='center')

        if ftype == 'image' and full.exists():
            try:
                h = embed_fn(full, row)
                ws.row_dimensions[row].height = max(h, 80)
            except Exception as e:
                img_cell.value = f'[не удалось вставить картинку: {e}]'
                ws.row_dimensions[row].height = 30
        elif ftype == 'pdf' and full.exists():
            # Пытаемся отрендерить первую страницу PDF в PNG (pymupdf без зависимостей)
            try:
                import pymupdf
                from openpyxl.drawing.image import Image as XLImage
                with pymupdf.open(str(full)) as doc:
                    if doc.page_count > 0:
                        page = doc.load_page(0)
                        # 144 dpi даёт читаемый эскиз без чрезмерного веса
                        pm = page.get_pixmap(dpi=144)
                        cache = full.parent / f'.preview_{full.stem}.png'
                        pm.save(str(cache))
                        h = embed_fn(cache, row)
                        ws.row_dimensions[row].height = max(h, 80)
                    else:
                        raise RuntimeError('Пустой PDF')
            except Exception:
                img_cell.value = f'PDF — см. файл-вложение: {full.name}'
                img_cell.font = Font(name='Arial', size=10, italic=True, color='2980b9')
                ws.row_dimensions[row].height = 30
        else:
            img_cell.value = '[файл не найден]'
            img_cell.font = Font(name='Arial', size=10, italic=True, color='c0392b')
            ws.row_dimensions[row].height = 24
        return row + 1

    # ─────────────────────────────────────────────────────────────────
    # 7. Открыть шаблон КТД в Word
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def open_ktd_template(template_path: str | Path) -> None:
        """Открыть шаблон КТД в ассоциированном приложении (Word)"""
        import subprocess, os
        path = Path(template_path)
        if path.exists():
            os.startfile(str(path))
        else:
            raise FileNotFoundError(f'Шаблон не найден: {path}')

    @staticmethod
    def list_ktd_templates() -> list[dict]:
        """Вернуть список доступных шаблонов КТД"""
        ktd_dir = Path(__file__).parent.parent / 'resources' / 'templates' / 'ktd'
        result = []
        if not ktd_dir.exists():
            return result

        GOST_NAMES = {
            '3.1105': 'Маршрутная карта (МК)',
            '3.1118': 'Операционная карта (ОК)',
            '3.1121': 'Карта типового операционного процесса (КТОП)',
            '3.1122': 'Карта кодирования информации (ККИ)',
            '3.1123': 'Карта нормирования (КН)',
            '3.1201': 'Карта наладки станка (КНС)',
            '3.1401': 'Ведомость технологической оснастки (ВТО)',
            '3.1402': 'Карта инструмента (КИ)',
            '3.1404': 'Операционная карта сборки (ОКС)',
            '3.1407': 'Карта типовых переходов (КТП)',
            '3.1408': 'Карта эскизов (КЭ)',
            '3.1502': 'Операционная карта ТК (ОКТК)',
        }

        for f in sorted(ktd_dir.iterdir()):
            if f.suffix.lower() in ('.dot', '.doc', '.docx'):
                gost_key = next(
                    (k for k in GOST_NAMES if k in f.name), None
                )
                doc_type = GOST_NAMES.get(gost_key, 'Форма КТД')
                result.append({
                    'name': f.name,
                    'path': str(f),
                    'gost': gost_key or '',
                    'doc_type': doc_type,
                    'size_kb': round(f.stat().st_size / 1024),
                })
        return result

    @staticmethod
    def list_report_templates() -> list[dict]:
        """Вернуть список шаблонов отчётов"""
        rep_dir = Path(__file__).parent.parent / 'resources' / 'templates' / 'reports'
        result = []
        if not rep_dir.exists():
            return result
        for f in sorted(rep_dir.iterdir()):
            if f.suffix.lower() in ('.xls', '.xlsx'):
                result.append({
                    'name': f.name,
                    'path': str(f),
                    'size_kb': round(f.stat().st_size / 1024),
                })
        return result
