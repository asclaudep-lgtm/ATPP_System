"""Генерация штрих-кодов Code128 и ярлыков для печати.

Используется библиотека ``python-barcode`` + Pillow.
Модуль не требует Pillow для базового SVG-вывода — только для PNG.

Если зависимости не установлены, ``generate_png`` / ``generate_svg`` бросают
понятное исключение, которое UI ловит и показывает пользователю.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional


class BarcodeError(Exception):
    """Ошибка генерации штрих-кода."""


def _get_code128():
    try:
        from barcode import Code128
        return Code128
    except ImportError as e:
        raise BarcodeError(
            'Библиотека python-barcode не установлена.\n'
            'Установите её командой: pip install python-barcode Pillow'
        ) from e


def _get_image_writer():
    try:
        from barcode.writer import ImageWriter
        return ImageWriter
    except ImportError as e:
        raise BarcodeError(
            'Pillow не установлен — нельзя сохранить PNG.\n'
            'Установите: pip install Pillow'
        ) from e


def _get_svg_writer():
    try:
        from barcode.writer import SVGWriter
        return SVGWriter
    except ImportError as e:
        raise BarcodeError('python-barcode не установлен.') from e


def generate_png(text: str, out_path: Optional[Path | str] = None) -> bytes:
    """Сохраняет штрих-код в PNG. Возвращает байты PNG.

    ``out_path`` без расширения — библиотека сама добавит ``.png``.
    Если ``out_path is None`` — рисует в память.
    """
    Code128 = _get_code128()
    ImageWriter = _get_image_writer()
    bc = Code128(text, writer=ImageWriter())

    if out_path is None:
        buf = io.BytesIO()
        bc.write(buf)
        return buf.getvalue()

    out = Path(out_path)
    if out.suffix.lower() == '.png':
        out = out.with_suffix('')
    str_path = str(out)
    bc.save(str_path)  # сохранит как str_path + .png
    return Path(str_path + '.png').read_bytes()


def generate_svg(text: str, out_path: Optional[Path | str] = None) -> bytes:
    """Возвращает штрих-код в SVG."""
    Code128 = _get_code128()
    SVGWriter = _get_svg_writer()
    bc = Code128(text, writer=SVGWriter())

    if out_path is None:
        buf = io.BytesIO()
        bc.write(buf)
        return buf.getvalue()

    out = Path(out_path)
    if out.suffix.lower() == '.svg':
        out = out.with_suffix('')
    str_path = str(out)
    bc.save(str_path)
    return Path(str_path + '.svg').read_bytes()


def label_text(item) -> str:
    """Текст подписи под штрих-кодом (для печати ярлыка партии).

    ``item`` — WorkOrderItem; ожидается, что у него подгружены work_order и
    work_order.product.
    """
    wo = getattr(item, 'work_order', None)
    product = getattr(wo, 'product', None) if wo else None
    parts = [item.serial]
    if wo:
        parts.append(f'Наряд {wo.number}')
    if product:
        parts.append(f'{product.designation} {product.name}')
    parts.append(f'Кол-во: {item.qty} шт.')
    return '\n'.join(parts)


# ──────────────────────────────────────────────────────────────────────────
# Печать ярлыков пачкой (PDF, A4, сетка)
# ──────────────────────────────────────────────────────────────────────────

# Сетка ярлыков на A4: 3 колонки × 4 строки = 12 ярлыков на лист.
_LABELS_GRID_COLS = 3
_LABELS_GRID_ROWS = 4
_LABELS_PER_PAGE = _LABELS_GRID_COLS * _LABELS_GRID_ROWS


def _find_cyrillic_font_path():
    """Возвращает путь к TTF-шрифту с кириллицей или None."""
    candidates = [
        # Linux DejaVu
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        # macOS
        '/System/Library/Fonts/Helvetica.ttc',
        # Windows
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/Arial.ttf',
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def generate_labels_pdf(session, work_order_id: int) -> bytes:
    """Генерирует PDF-файл с ярлыками всех партий заданного наряда.

    Формат: A4 портретно, 3×4 ярлыка на лист (12 шт.). Каждый ярлык
    содержит штрих-код Code128, серийник партии, номер наряда, наименование
    детали и количество.

    Возвращает байты готового PDF. Бросает ``BarcodeError`` при отсутствии
    зависимостей (``reportlab``) или партий.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError as e:
        raise BarcodeError(
            'Библиотека reportlab не установлена.\n'
            'Установите её командой: pip install reportlab'
        ) from e

    # Импорт моделей выполняем здесь, чтобы избежать циклов на старте
    from database.models import WorkOrder, WorkOrderItem  # noqa: F401

    wo = session.get(WorkOrder, work_order_id)
    if wo is None:
        raise BarcodeError(f'Наряд id={work_order_id} не найден.')
    items = list(wo.items)
    if not items:
        raise BarcodeError(
            f'Наряд {wo.number} не содержит ни одной партии.\n'
            'Сначала зарегистрируйте наряд (разбейте на партии).')

    # Регистрируем кириллический шрифт, если нашли
    font_path = _find_cyrillic_font_path()
    label_font = 'Helvetica'
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont('LabelSans', font_path))
            label_font = 'LabelSans'
        except Exception:
            pass

    # Геометрия страницы / ярлыка
    page_w, page_h = A4
    margin_x = 8 * mm
    margin_y = 8 * mm
    grid_w = page_w - 2 * margin_x
    grid_h = page_h - 2 * margin_y
    cell_w = grid_w / _LABELS_GRID_COLS
    cell_h = grid_h / _LABELS_GRID_ROWS

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f'Ярлыки наряда {wo.number}')
    c.setAuthor('ATPP System')

    product = wo.product
    product_name = ''
    if product:
        product_name = f'{product.designation or ""} {product.name or ""}'.strip()

    for idx, item in enumerate(items):
        slot = idx % _LABELS_PER_PAGE
        if idx > 0 and slot == 0:
            c.showPage()
        col = slot % _LABELS_GRID_COLS
        row = slot // _LABELS_GRID_COLS
        # ReportLab origin = нижний левый угол
        x0 = margin_x + col * cell_w
        y0 = page_h - margin_y - (row + 1) * cell_h

        # Рамка
        c.setLineWidth(0.4)
        c.rect(x0 + 1, y0 + 1, cell_w - 2, cell_h - 2, stroke=1, fill=0)

        # Шапка
        text_top = y0 + cell_h - 5 * mm
        c.setFont(label_font, 9)
        c.drawString(x0 + 4 * mm, text_top, f'Наряд: {wo.number}')
        c.setFont(label_font, 8)
        c.drawString(x0 + 4 * mm, text_top - 4 * mm,
                     (product_name[:40] or '—'))

        # Штрих-код (PNG) посредине
        try:
            png_bytes = generate_png(item.barcode)
            from reportlab.lib.utils import ImageReader
            img = ImageReader(io.BytesIO(png_bytes))
            iw, ih = img.getSize()
            target_w = cell_w - 10 * mm
            scale = target_w / iw
            target_h = ih * scale
            # Если высота больше отведённой — уменьшаем
            max_h = cell_h - 28 * mm
            if target_h > max_h:
                scale = max_h / ih
                target_w = iw * scale
                target_h = ih * scale
            img_x = x0 + (cell_w - target_w) / 2
            img_y = y0 + 12 * mm
            c.drawImage(img, img_x, img_y, target_w, target_h)
        except BarcodeError:
            c.setFont(label_font, 8)
            c.drawString(x0 + 4 * mm, y0 + cell_h / 2,
                         f'(ошибка генерации штрих-кода: {item.barcode})')

        # Подвал — серийник и количество
        c.setFont(label_font, 9)
        c.drawString(x0 + 4 * mm, y0 + 8 * mm,
                     f'Партия: {item.serial}')
        c.setFont(label_font, 8)
        c.drawString(x0 + 4 * mm, y0 + 4 * mm,
                     f'Кол-во: {item.qty} шт. · {item.barcode}')

    c.showPage()
    c.save()
    return buf.getvalue()
