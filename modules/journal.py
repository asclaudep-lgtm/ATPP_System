"""
Единый журнал регистрации ТП и МТП.

Замещает два бумажных журнала:
- «Журнал регистрации ТП» (УЗГА.02101.NNNNN)
- «Журнал регистрации МТП» (УЗГА.02101.NNNNN)

API:
    next_number(session, prefix='УЗГА.02101.', pad=5) -> str
    register_product(session, product, user_id, **overrides) -> RegistrationJournal
    register_tp(session, tp, user_id, in_tp=True, in_mtp=True, **overrides) -> RegistrationJournal
    exclude_entry(session, entry_id, user_id, reason)
    restore_entry(session, entry_id, user_id)
    list_entries(session, only_active=True, in_tp=None, in_mtp=None) -> List[RegistrationJournal]
    export_to_excel(session, entries, layout, out_path) -> Path
"""
from __future__ import annotations

import re
from datetime import datetime, date
from pathlib import Path
from typing import Iterable, List, Optional

from sqlalchemy import func

from database.models import (
    RegistrationJournal, Product, TechProcess
)

import logging
_logger = logging.getLogger(__name__)


# ---------- Назначение номеров ----------

DEFAULT_PREFIX = 'УЗГА.02101.'
DEFAULT_PAD = 5


def _extract_seq(value: Optional[str], prefix: str) -> Optional[int]:
    """Извлечь числовой счётчик из 'УЗГА.02101.00012' → 12."""
    if not value:
        return None
    m = re.match(re.escape(prefix) + r'(\d+)\b', value)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def next_number(session, prefix: str = DEFAULT_PREFIX,
                pad: int = DEFAULT_PAD) -> str:
    """Следующий свободный номер вида '<prefix><NNNNN>'.

    Берём максимум из tp_number / mtp_number в журнале и из
    TechProcess.number — чтобы новые номера никогда не пересекались
    с уже введёнными вручную.
    """
    candidates = []

    # из журнала
    rows = (session.query(
        RegistrationJournal.tp_number,
        RegistrationJournal.mtp_number,
    ).all())
    for tp_num, mtp_num in rows:
        for v in (tp_num, mtp_num):
            n = _extract_seq(v, prefix)
            if n is not None:
                candidates.append(n)

    # из таблицы ТП — на случай ручной нумерации
    tp_rows = session.query(TechProcess.number).all()
    for (n,) in tp_rows:
        x = _extract_seq(n, prefix)
        if x is not None:
            candidates.append(x)

    next_seq = (max(candidates) if candidates else 0) + 1
    return f'{prefix}{next_seq:0{pad}d}'


def next_entry_no(session) -> int:
    """Следующий № п/п (только среди активных записей)."""
    n = (session.query(func.coalesce(func.max(RegistrationJournal.entry_no), 0))
         .scalar()) or 0
    return int(n) + 1


# ---------- Регистрация ----------

def _resolve_user_name(session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    from database.models import User
    u = session.get(User, user_id)
    if u is None:
        return None
    return u.full_name or u.username


def register_product(session, product, user_id: Optional[int] = None,
                     *, executor: Optional[str] = None,
                     project: Optional[str] = None,
                     product_type: Optional[str] = None,
                     notes: Optional[str] = None,
                     in_tp: bool = True,
                     in_mtp: bool = True,
                     tp_number: Optional[str] = None,
                     mtp_number: Optional[str] = None,
                     auto_number: bool = True
                     ) -> RegistrationJournal:
    """Зарегистрировать изделие в журнале.

    Если auto_number=True и не указан tp_number/mtp_number — берётся
    next_number() (общий для ТП и МТП).
    """
    if auto_number:
        if not tp_number:
            tp_number = next_number(session)
        if not mtp_number:
            mtp_number = tp_number
    executor = executor or _resolve_user_name(session, user_id) or ''

    entry = RegistrationJournal(
        entry_no=next_entry_no(session),
        tp_number=tp_number,
        mtp_number=mtp_number,
        product_id=product.id if product is not None else None,
        product_designation=getattr(product, 'designation', None),
        product_name=getattr(product, 'name', None),
        product_type=product_type,
        project=project,
        executor=executor,
        notes=notes,
        date_registered=date.today(),
        in_tp_journal=in_tp,
        in_mtp_journal=in_mtp,
        created_by=user_id,
    )
    session.add(entry)
    session.flush()
    return entry


def register_tp(session, tp, user_id: Optional[int] = None,
                *, executor: Optional[str] = None,
                project: Optional[str] = None,
                product_type: Optional[str] = None,
                notes: Optional[str] = None,
                in_tp: bool = True,
                in_mtp: bool = True,
                tp_number: Optional[str] = None,
                mtp_number: Optional[str] = None,
                auto_number: bool = True
                ) -> RegistrationJournal:
    """Зарегистрировать ТП (или его вариант) в журнале.

    Если у этого же изделия уже есть регистрационная запись и
    auto_number=False с пустыми номерами — будет создана отдельная
    запись (например, для нового execution_variant).
    """
    if auto_number:
        if not tp_number:
            tp_number = tp.number or next_number(session)
        if not mtp_number:
            mtp_number = tp_number
    product = tp.product
    executor = executor or _resolve_user_name(session, user_id) or ''

    entry = RegistrationJournal(
        entry_no=next_entry_no(session),
        tp_number=tp_number,
        mtp_number=mtp_number,
        product_id=product.id if product is not None else None,
        tech_process_id=tp.id,
        product_designation=getattr(product, 'designation', None),
        product_name=getattr(product, 'name', None),
        product_type=product_type,
        project=project,
        executor=executor,
        notes=notes,
        date_registered=date.today(),
        date_developed=date.today(),
        in_tp_journal=in_tp,
        in_mtp_journal=in_mtp,
        created_by=user_id,
    )
    session.add(entry)
    session.flush()
    return entry


# ---------- Исключение / восстановление ----------

def exclude_entry(session, entry_id: int, user_id: Optional[int],
                  reason: Optional[str] = None) -> bool:
    e = session.get(RegistrationJournal, entry_id)
    if e is None:
        return False
    e.excluded = True
    e.excluded_reason = reason
    e.excluded_at = datetime.now()
    e.excluded_by_user_id = user_id
    return True


def restore_entry(session, entry_id: int, user_id: Optional[int]) -> bool:
    e = session.get(RegistrationJournal, entry_id)
    if e is None:
        return False
    e.excluded = False
    e.excluded_reason = None
    e.excluded_at = None
    e.excluded_by_user_id = None
    return True


# ---------- Чтение ----------

def list_entries(session, *, only_active: bool = True,
                 in_tp: Optional[bool] = None,
                 in_mtp: Optional[bool] = None,
                 search: Optional[str] = None
                 ) -> List[RegistrationJournal]:
    q = session.query(RegistrationJournal)
    if only_active:
        q = q.filter((RegistrationJournal.excluded == False) |
                     (RegistrationJournal.excluded.is_(None)))
    if in_tp is True:
        q = q.filter(RegistrationJournal.in_tp_journal == True)
    if in_mtp is True:
        q = q.filter(RegistrationJournal.in_mtp_journal == True)
    if search:
        like = f'%{search}%'
        q = q.filter(
            (RegistrationJournal.tp_number.ilike(like)) |
            (RegistrationJournal.mtp_number.ilike(like)) |
            (RegistrationJournal.product_designation.ilike(like)) |
            (RegistrationJournal.product_name.ilike(like)) |
            (RegistrationJournal.executor.ilike(like)) |
            (RegistrationJournal.project.ilike(like))
        )
    return q.order_by(RegistrationJournal.entry_no.asc().nullslast(),
                      RegistrationJournal.id.asc()).all()


# ---------- Экспорт в Excel ----------

def export_to_excel(session, entries: Iterable[RegistrationJournal],
                    layout: str = 'unified',
                    out_path: Optional[Path] = None) -> Path:
    """Экспорт журнала в xlsx.

    layout:
        'tp'       — формат ТП-журнала (МСП -УЗГА.02101.00001-19999)
        'mtp'      — формат МТП-журнала (с датой регистрации МТП)
        'unified'  — все колонки разом (для архива)
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from config import EXPORT_DIR

    if out_path is None:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = EXPORT_DIR / f'Журнал_регистрации_{layout}_{ts}.xlsx'

    wb = Workbook()
    ws = wb.active

    if layout == 'tp':
        ws.title = 'МСП -УЗГА.02101.00001-19999'
        headers = [
            '№ п/п',
            'Номер технологического процесса',
            'Обозначение документа (номер чертежа)',
            'Наименование',
            'Проект',
            'Исполнитель',
            'Дата разработки ТП',
            'Примечание',
        ]
        getter = lambda e: [
            e.entry_no,
            e.tp_number or '',
            e.product_designation or '',
            e.product_name or '',
            e.project or '',
            e.executor or '',
            (e.date_developed.strftime('%d.%m.%Y')
             if e.date_developed else ''),
            e.notes or '',
        ]
        widths = [6, 26, 36, 28, 30, 22, 16, 30]
    elif layout == 'mtp':
        ws.title = 'МСП -УЗГА.02101.00001-19999'
        headers = [
            '№ п/п',
            'Дата регистрации МТП',
            'Номер МТП',
            'Номер изделия (тип самолета, номер машины)',
            'Номер технологического процесса',
            'Обозначение документа (номер чертежа)',
            'Исполнитель',
        ]
        getter = lambda e: [
            e.entry_no,
            (e.date_registered.strftime('%d.%m.%Y')
             if e.date_registered else ''),
            e.mtp_number or '',
            e.product_type or '',
            e.tp_number or '',
            e.product_designation or '',
            e.executor or '',
        ]
        widths = [6, 18, 26, 32, 28, 36, 22]
    else:
        ws.title = 'Журнал регистрации'
        headers = [
            '№ п/п',
            'Номер ТП',
            'Номер МТП',
            'Дата регистрации',
            'Дата разработки',
            'Обозначение чертежа',
            'Наименование',
            'Тип изделия',
            'Проект',
            'Исполнитель',
            'В журнале ТП',
            'В журнале МТП',
            'Исключено',
            'Причина исключения',
            'Примечание',
        ]
        getter = lambda e: [
            e.entry_no,
            e.tp_number or '',
            e.mtp_number or '',
            (e.date_registered.strftime('%d.%m.%Y')
             if e.date_registered else ''),
            (e.date_developed.strftime('%d.%m.%Y')
             if e.date_developed else ''),
            e.product_designation or '',
            e.product_name or '',
            e.product_type or '',
            e.project or '',
            e.executor or '',
            'да' if e.in_tp_journal else 'нет',
            'да' if e.in_mtp_journal else 'нет',
            'да' if e.excluded else '',
            e.excluded_reason or '',
            e.notes or '',
        ]
        widths = [6, 22, 22, 16, 16, 32, 26, 26, 24, 22, 12, 12, 10, 24, 30]

    # Шапка
    ws.append(headers)
    bold = Font(bold=True)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    fill = PatternFill('solid', fgColor='DCE6F1')
    border = Border(*(Side(style='thin', color='999999'),) * 4)
    for col_i, _ in enumerate(headers, 1):
        c = ws.cell(1, col_i)
        c.font = bold
        c.alignment = center
        c.fill = fill
        c.border = border

    # Данные
    for e in entries:
        row = getter(e)
        ws.append(row)
        last = ws.max_row
        for col_i in range(1, len(headers) + 1):
            cell = ws.cell(last, col_i)
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            cell.border = border
        # Подсветка исключённых
        if e.excluded:
            grey = PatternFill('solid', fgColor='F2F2F2')
            italic = Font(italic=True, color='888888')
            for col_i in range(1, len(headers) + 1):
                ws.cell(last, col_i).fill = grey
                ws.cell(last, col_i).font = italic

    # Ширины
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.row_dimensions[1].height = 38
    ws.freeze_panes = 'A2'

    # Print settings
    try:
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
    except Exception:
        _logger.exception("Unhandled error")

    wb.save(out_path)
    return out_path


# ---------- Импорт из существующих xlsx-журналов ----------

def _pick_journal_sheet(wb, layout: str):
    """Выбрать рабочий лист по заголовкам.

    Для layout='mtp' ищем лист, где в первой строке встречается
    «Дата регистрации МТП» (обычно "МСП -УЗГА.02101...").
    Для layout='tp' ищем лист с «Номер технологического процесса»
    но БЕЗ «Дата регистрации МТП».
    Если ничего не нашли — возвращаем wb.active.
    """
    target_mtp = 'дата регистрации мтп'
    target_tp = 'номер технологического процесса'

    best = None
    for ws in wb.worksheets:
        headers = []
        for c in range(1, min(ws.max_column, 12) + 1):
            v = ws.cell(1, c).value
            if v is not None:
                headers.append(str(v).strip().lower())
        joined = ' | '.join(headers)
        if layout == 'mtp':
            if target_mtp in joined:
                return ws
        else:  # 'tp'
            if target_tp in joined and target_mtp not in joined:
                return ws
            if 'номер технологического паспорта' in joined:
                # КП-журнал тоже ТП-формат
                best = best or ws
    return best or wb.active



def import_from_xlsx(session, path: Path,
                     layout: str = 'tp',
                     header_row: int = 1,
                     data_start_row: int = 2,
                     skip_existing: bool = True) -> dict:
    """Импорт исторических записей из бумажного журнала (xlsx).

    layout:
        'tp'   — формат МСП -УЗГА.02101.00001-19999 (журнал ТП)
                 cols: №, Номер ТП, Обозначение, Наименование,
                       Проект, Исполнитель, Дата разработки, Примечание
        'mtp'  — формат МТП-журнала
                 cols: №, Дата регистрации МТП, Номер МТП,
                       Номер изделия (тип), Номер ТП,
                       Обозначение, Исполнитель

    Возвращает {'added': N, 'skipped': N}. Дубликаты определяются по
    (tp_number, mtp_number) — существующая комбинация пропускается.
    """
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    # Подбираем нужный лист по заголовкам, потому что у бумажных
    # журналов в одном xlsx часто несколько вкладок (МТП и КП).
    ws = _pick_journal_sheet(wb, layout)

    added = 0
    skipped = 0

    # Текущий максимум entry_no — чтобы продолжить с него
    base_no = (session.query(func.coalesce(func.max(RegistrationJournal.entry_no), 0))
               .scalar()) or 0

    for r in range(data_start_row, ws.max_row + 1):
        row = [ws.cell(r, c).value for c in range(1, 11)]
        if all(v is None or (isinstance(v, str) and not v.strip())
               for v in row):
            continue

        if layout == 'tp':
            (_n, tp_num, doc, name, project,
             executor, date_dev, notes, *_rest) = row + [None] * 8
            mtp_num = tp_num  # в ТП-журнале МТП-номер не указан, ставим равным
            product_type = None
        elif layout == 'mtp':
            (_n, date_reg, mtp_num, prod_type, tp_num,
             doc, executor, *_rest) = row + [None] * 7
            project = None
            name = None
            notes = None
            date_dev = None
            product_type = prod_type if prod_type else None
            # имитация date_developed
            if not isinstance(date_reg, datetime):
                date_reg = None
        else:
            raise ValueError(f'Unknown layout: {layout}')

        # пропустить если оба номера пустые
        if not tp_num and not mtp_num:
            continue

        if skip_existing:
            from sqlalchemy import or_, false
            conds = []
            if tp_num:
                conds.append(RegistrationJournal.tp_number == str(tp_num).strip())
            if mtp_num:
                conds.append(RegistrationJournal.mtp_number == str(mtp_num).strip())
            cond = or_(*conds) if conds else false()
            exists = (session.query(RegistrationJournal)
                      .filter(cond).first())
            if exists:
                skipped += 1
                continue

        base_no += 1
        e = RegistrationJournal(
            entry_no=base_no,
            tp_number=str(tp_num).strip() if tp_num else None,
            mtp_number=str(mtp_num).strip() if mtp_num else None,
            product_designation=(str(doc).strip() if doc else None),
            product_name=(str(name).strip() if name else None),
            product_type=product_type,
            project=(str(project).strip() if project else None),
            executor=(str(executor).strip() if executor else None),
            notes=(str(notes).strip() if notes else None),
            # Все исторические записи попадают в оба журнала: в одном
            # их учитывали как ТП, в другом — как МТП.
            in_tp_journal=True,
            in_mtp_journal=True,
        )
        # дата
        if layout == 'mtp' and isinstance(date_reg, datetime):
            e.date_registered = date_reg.date()
        if isinstance(date_dev, datetime):
            e.date_developed = date_dev.date()
        session.add(e)
        added += 1

    return {'added': added, 'skipped': skipped}
