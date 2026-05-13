"""Генерация маршрутно-технологического процесса (МТП) в формате PDF.

Используется reportlab.  Шаблон-форма та же, что и в xlsx-версии
(``modules/mtp_excel.py``) — заголовок «Маршрутно-технологический паспорт»,
блоки «Изделие», «Комплектование», таблица операций, штрих-код.

В отличие от xlsx-варианта PDF удобен для электронного архива и подписей
(не редактируется без специальных средств).

Использование:

    from modules.mtp_pdf import generate_mtp_pdf, generate_mtp_pdf_batch

    data = generate_mtp_pdf(session,
                            tech_process_id=37,
                            work_order_id=12,
                            out_path='/tmp/mtp.pdf')

    big_data = generate_mtp_pdf_batch(session,
                                      work_order_ids=[12, 13, 14],
                                      out_path='/tmp/mtp_batch.pdf')
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable, Optional, Union, List

# Те же фильтры операций, что и в xlsx-генераторе.
from modules.mtp_excel import _apply_op_filters, _generate_barcode_png


FONT_DIR = Path(__file__).resolve().parent.parent / 'resources' / 'fonts'
FONT_REGULAR = FONT_DIR / 'DejaVuSans.ttf'
FONT_BOLD = FONT_DIR / 'DejaVuSans-Bold.ttf'

_FONTS_REGISTERED = False


class MTPPDFError(Exception):
    """Ошибка генерации МТП-PDF."""


def _ensure_fonts():
    """Регистрируем DejaVu Sans для поддержки кириллицы в reportlab."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if FONT_REGULAR.exists():
        pdfmetrics.registerFont(TTFont('MTP', str(FONT_REGULAR)))
    else:
        raise MTPPDFError(
            f'Не найден шрифт {FONT_REGULAR}.  '
            'Положите DejaVuSans.ttf в resources/fonts/.'
        )
    if FONT_BOLD.exists():
        pdfmetrics.registerFont(TTFont('MTP-Bold', str(FONT_BOLD)))
    else:
        pdfmetrics.registerFont(TTFont('MTP-Bold', str(FONT_REGULAR)))
    _FONTS_REGISTERED = True


def _load_data(session, tech_process_id: int,
               work_order_id: Optional[int] = None,
               collapse_intermediate: bool = True,
               respect_include_in_mtp: bool = True):
    """Загрузить из БД всё, что нужно для одного МТП-документа."""
    from database.models import (
        TechProcess, WorkOrder, Operation, Equipment, Material,
    )

    tp = session.query(TechProcess).get(tech_process_id)
    if tp is None:
        raise MTPPDFError(f'ТП id={tech_process_id} не найден.')

    wo = None
    if work_order_id is not None:
        wo = session.query(WorkOrder).get(work_order_id)
        if wo is None:
            raise MTPPDFError(f'Наряд id={work_order_id} не найден.')

    product = tp.product

    ops = (session.query(Operation)
           .filter(Operation.tech_process_id == tp.id)
           .filter(Operation.is_deleted == False)  # noqa: E712
           .order_by(Operation.sort_order, Operation.number)
           .all())
    ops = _apply_op_filters(ops, collapse_intermediate,
                            respect_include_in_mtp)

    # Материал
    mat_name = ''
    mat_desig = ''
    if product and getattr(product, 'material_id', None):
        try:
            mat = session.query(Material).get(product.material_id)
            if mat:
                mat_name = mat.name or ''
                mat_desig = mat.designation or ''
        except Exception:
            pass

    # Подготавливаем строки таблицы операций.
    op_rows: List[List[str]] = []
    for op in ops:
        eq_label = ''
        if op.equipment_id:
            try:
                eq = session.query(Equipment).get(op.equipment_id)
                if eq:
                    eq_label = eq.name or ''
                    if eq.model:
                        eq_label = f'{eq_label} ({eq.model})'
            except Exception:
                pass
        op_text = op.name or ''
        if eq_label:
            op_text = f'{op_text}\n{eq_label}'
        shop = (getattr(op, 'shop', None) or '').strip()
        op_rows.append([
            shop,
            str(op.number or ''),
            op_text,
        ])

    return {
        'tp': tp,
        'wo': wo,
        'product': product,
        'mat_name': mat_name,
        'mat_desig': mat_desig,
        'blank_size': getattr(product, 'blank_dimensions', None) or '',
        'op_rows': op_rows,
    }


def _build_document(data, story, styles):
    """Собрать один МТП-документ в существующий story."""
    from reportlab.platypus import (
        Paragraph, Spacer, Table, TableStyle, Image as RImage,
        PageBreak,
    )
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    tp = data['tp']
    wo = data['wo']
    product = data['product']

    # ── Заголовок ────────────────────────────────────────────────
    title = 'Маршрутно-технологический паспорт'
    if wo:
        title = f'{title}<br/>№ МТП {wo.number}'
    story.append(Paragraph(title, styles['mtp_title']))
    story.append(Spacer(1, 4 * mm))

    # ── Штрих-код (если есть наряд) ──────────────────────────────
    if wo and getattr(wo, 'barcode', None):
        try:
            png = _generate_barcode_png(wo.barcode)
            if png:
                img = RImage(io.BytesIO(png), width=55 * mm, height=14 * mm)
                story.append(img)
                story.append(Spacer(1, 2 * mm))
        except Exception:
            pass

    # ── Блок «Изделие» ───────────────────────────────────────────
    prod_rows = [
        ['Обозначение ДСЕ', product.designation if product else '—',
         'Номер ТП', tp.number or '—'],
        ['Наименование ДСЕ', product.name if product else '—',
         'Заказ', (wo.customer_order if wo else '—') or '—'],
        ['Вариант исполнения', tp.execution_variant or '—',
         '№ наряда', (wo.number if wo else '—')],
    ]
    if wo and getattr(wo, 'qty_total', None):
        prod_rows.append(['Количество, шт.', str(wo.qty_total),
                          '', ''])

    t = Table(prod_rows, colWidths=[38 * mm, 75 * mm, 32 * mm, 35 * mm])
    t.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'MTP', 9),
        ('FONT', (0, 0), (0, -1), 'MTP-Bold', 9),
        ('FONT', (2, 0), (2, -1), 'MTP-Bold', 9),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f4f4f4')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f4f4f4')),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 3 * mm))

    # ── Комплектование ───────────────────────────────────────────
    story.append(Paragraph('Комплектование', styles['mtp_h2']))
    mat_rows = [
        ['Наименование материала', data['mat_name'] or '—',
         'Обозначение', data['mat_desig'] or '—'],
        ['Размер заготовки', data['blank_size'] or '—',
         'Норма расхода', '—'],
    ]
    tm = Table(mat_rows, colWidths=[38 * mm, 75 * mm, 32 * mm, 35 * mm])
    tm.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'MTP', 9),
        ('FONT', (0, 0), (0, -1), 'MTP-Bold', 9),
        ('FONT', (2, 0), (2, -1), 'MTP-Bold', 9),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f4f4f4')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f4f4f4')),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(tm)
    story.append(Spacer(1, 3 * mm))

    # ── Таблица операций ─────────────────────────────────────────
    story.append(Paragraph(
        'Маршрутно-технологическое описание',
        styles['mtp_h2']
    ))

    ops_header = [['Уч-к', '№ опер.', 'Наименование операции / оборудование',
                   'Исп.', 'Мастер', 'ОТК']]
    ops_data = []
    for row in data['op_rows']:
        ops_data.append([
            Paragraph(row[0] or '', styles['mtp_cell']),
            Paragraph(row[1] or '', styles['mtp_cell_center']),
            Paragraph(row[2] or '', styles['mtp_cell']),
            '', '', '',
        ])
    if not ops_data:
        ops_data = [['—', '', 'Нет операций в МТП', '', '', '']]

    table = Table(
        ops_header + ops_data,
        colWidths=[18 * mm, 16 * mm, 80 * mm, 22 * mm, 22 * mm, 22 * mm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'MTP', 8),
        ('FONT', (0, 0), (-1, 0), 'MTP-Bold', 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9eef5')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(table)


def _build_styles():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    return {
        'mtp_title': ParagraphStyle(
            name='mtp_title', fontName='MTP-Bold', fontSize=14,
            alignment=TA_CENTER, leading=18, spaceAfter=4,
        ),
        'mtp_h2': ParagraphStyle(
            name='mtp_h2', fontName='MTP-Bold', fontSize=10,
            alignment=TA_LEFT, leading=12, spaceBefore=2, spaceAfter=2,
        ),
        'mtp_cell': ParagraphStyle(
            name='mtp_cell', fontName='MTP', fontSize=8,
            alignment=TA_LEFT, leading=10,
        ),
        'mtp_cell_center': ParagraphStyle(
            name='mtp_cell_center', fontName='MTP', fontSize=8,
            alignment=TA_CENTER, leading=10,
        ),
    }


def generate_mtp_pdf(
    session,
    *,
    tech_process_id: int,
    work_order_id: Optional[int] = None,
    out_path: Optional[Union[Path, str]] = None,
    collapse_intermediate: bool = True,
    respect_include_in_mtp: bool = True,
) -> bytes:
    """Собирает PDF с маршрутно-технологическим процессом.

    Аргументы и поведение совпадают с :func:`generate_mtp_excel`.
    Возвращает байты файла.
    """
    _ensure_fonts()
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate

    data = _load_data(session, tech_process_id, work_order_id,
                      collapse_intermediate, respect_include_in_mtp)
    styles = _build_styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=10, rightMargin=10,
        topMargin=10, bottomMargin=10,
        title=f'МТП {data["tp"].number or ""}',
    )
    story = []
    _build_document(data, story, styles)
    doc.build(story)
    out = buf.getvalue()
    if out_path is not None:
        Path(out_path).write_bytes(out)
    return out


def generate_mtp_pdf_batch(
    session,
    *,
    work_order_ids: Iterable[int],
    out_path: Optional[Union[Path, str]] = None,
    collapse_intermediate: bool = True,
    respect_include_in_mtp: bool = True,
) -> bytes:
    """Собирает один многостраничный PDF для пачки нарядов.

    На каждую запись наряда выпадает 1+ страница МТП.  Используется
    для печати «пачкой» из окна производства.
    """
    _ensure_fonts()
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, PageBreak

    from database.models import WorkOrder

    styles = _build_styles()
    story = []
    for i, wo_id in enumerate(work_order_ids):
        wo = session.query(WorkOrder).get(wo_id)
        if wo is None or wo.tech_process_id is None:
            continue
        try:
            data = _load_data(session, wo.tech_process_id, wo.id,
                              collapse_intermediate, respect_include_in_mtp)
        except MTPPDFError:
            continue
        if i > 0:
            story.append(PageBreak())
        _build_document(data, story, styles)

    if not story:
        raise MTPPDFError(
            'Нет нарядов для печати: проверьте выбор и наличие ТП.'
        )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=10, rightMargin=10,
        topMargin=10, bottomMargin=10,
        title='МТП — пачка',
    )
    doc.build(story)
    out = buf.getvalue()
    if out_path is not None:
        Path(out_path).write_bytes(out)
    return out
