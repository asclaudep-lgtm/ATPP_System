"""
Модуль генерации технологической документации
"""
from pathlib import Path
from typing import List
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side
from docx import Document
from docx.shared import Pt, Cm
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from database.models import TechProcess, Operation, Transition
from config import TEMPLATES_DIR, EXPORT_DIR, product_export_dir


import logging
_logger = logging.getLogger(__name__)
class DocumentGenerator:
    """Класс для генерации технологической документации."""

    # Base URL for QR codes pointing to web SPA
    QR_BASE_URL = 'http://localhost:8000'

    def __init__(self, db_session):
        self.session = db_session

    @staticmethod
    def _qr_code_url(tp_id: int, base_url: str = None) -> str:
        """Generate a Google Chart API QR code URL for a TP.

        Returns a URL that renders a QR code image. The QR code points to
        the web SPA showing the TP detail.
        """
        base = base_url or DocumentGenerator.QR_BASE_URL
        target = f'{base}/?page=tps&tp={tp_id}'
        return (
            f'https://chart.googleapis.com/chart'
            f'?chs=150x150&cht=qr&chl={target}&choe=UTF-8'
        )

    @staticmethod
    def _add_qr_to_sheet(ws, row: int, col: str, tp_id: int,
                          base_url: str = None):
        """Insert a QR code image into an openpyxl worksheet.

        Uses Google Chart API — requires internet access at generation time.
        For offline use, install ``qrcode`` and ``Pillow``.
        """
        try:
            import tempfile
            import urllib.request

            qr_url = DocumentGenerator._qr_code_url(tp_id, base_url)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                urllib.request.urlretrieve(qr_url, f.name)
                from openpyxl.drawing.image import Image as XlImage
                img = XlImage(f.name)
                img.width = 80
                img.height = 80
                ws.add_image(img, f'{col}{row}')
        except Exception:
            pass  # QR code is non-critical — skip if offline

    @staticmethod
    def _mtp_operations(tp: TechProcess) -> list:
        """Операции ТП, выводимые в МК / МСК (include_in_mtp=True)."""
        return [
            op for op in sorted(tp.operations, key=lambda o: (o.sort_order or 0))
            if bool(getattr(op, 'include_in_mtp', True))
        ]

    @staticmethod
    def _mk_basename(tp: TechProcess) -> str:
        """Имя файла МК с номером ТП и вариантом исполнения (без расширения).

        Раньше файл именовался только по обозначению детали, поэтому МК для
        исходного ТП и его варианта могли затереть друг друга. Теперь
        включаем номер ТП и (при наличии) вариант исполнения.
        """
        parts = [tp.product.designation]
        num = (tp.number or '').strip()
        if num and num != tp.product.designation:
            parts.append(num)
        variant = (getattr(tp, 'execution_variant', None) or '').strip()
        if variant:
            parts.append(f'исп.{variant}')
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        # пробелы оставляем — они допустимы; запрещённые символы санитизируются
        # дальше в product_export_dir() при необходимости через путь
        raw = '_'.join(p for p in parts if p)
        for ch in '\\/:*?"<>|':
            raw = raw.replace(ch, '_')
        return f"МК_{raw}_{ts}"
    
    def generate_route_card(
        self,
        tech_process_id: int,
        output_format: str = "xlsx"
    ) -> Path:
        """
        Сгенерировать маршрутную карту (ГОСТ 3.1109-82)
        
        Args:
            tech_process_id: ID технологического процесса
            output_format: Формат вывода (xlsx, pdf, docx)
            
        Returns:
            Путь к созданному файлу
        """
        tp = self.session.get(TechProcess, tech_process_id)
        
        if not tp:
            raise ValueError(f"ТП с ID {tech_process_id} не найден")
        
        if output_format == "xlsx":
            return self._generate_route_card_excel(tp)
        elif output_format == "docx":
            return self._generate_route_card_word(tp)
        elif output_format == "pdf":
            return self._generate_route_card_pdf(tp)
        else:
            raise ValueError(f"Неподдерживаемый формат: {output_format}")
    
    def _generate_route_card_excel(self, tp: TechProcess) -> Path:
        """Генерация маршрутной карты в Excel"""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Маршрутная карта"
        
        # Настройка ширины столбцов
        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 30
        ws.column_dimensions['C'].width = 25
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 10
        ws.column_dimensions['F'].width = 10
        
        # Заголовок
        ws['A1'] = "МАРШРУТНАЯ КАРТА"
        ws['A1'].font = Font(size=14, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:F1')

        # QR-код — ссылка на ТП в веб-клиенте
        self._add_qr_to_sheet(ws, 1, 'G', tp.id)

        # Информация о детали
        row = 3
        ws[f'A{row}'] = "Обозначение:"
        ws[f'B{row}'] = tp.product.designation
        ws[f'D{row}'] = "ТП №:"
        ws[f'E{row}'] = tp.number
        
        row += 1
        ws[f'A{row}'] = "Наименование:"
        ws[f'B{row}'] = tp.product.name
        ws.merge_cells(f'B{row}:F{row}')
        
        row += 1
        ws[f'A{row}'] = "Материал:"
        ws[f'B{row}'] = tp.product.material.name if tp.product.material else ""
        
        row += 2
        
        # Заголовки таблицы операций
        headers = ["№ оп.", "Наименование операции", "Оборудование", "Профессия", "Тшт, мин", "Тпз, мин"]
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
        
        # Операции
        row += 1
        for operation in self._mtp_operations(tp):
            ws.cell(row=row, column=1, value=operation.number)
            ws.cell(row=row, column=2, value=operation.name)
            ws.cell(row=row, column=3, value=operation.equipment.name if operation.equipment else "")
            
            profession_text = ""
            if operation.profession:
                profession_text = f"{operation.profession.name}"
                if operation.grade:
                    profession_text += f" р.{operation.grade}"
            ws.cell(row=row, column=4, value=profession_text)
            
            ws.cell(row=row, column=5, value=operation.t_piece)
            ws.cell(row=row, column=6, value=operation.t_setup)
            
            # Границы
            for col in range(1, 7):
                ws.cell(row=row, column=col).border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
            
            row += 1
        
        # Подписи
        row += 2
        ws[f'A{row}'] = f"Разработал: {tp.author.full_name if tp.author else ''}"
        ws[f'D{row}'] = f"Дата: {datetime.now().strftime('%d.%m.%Y')}"
        
        # Сохранение
        filename = f"{self._mk_basename(tp)}.xlsx"
        output_path = product_export_dir(tp.product) / filename
        wb.save(output_path)
        
        return output_path
    
    def _generate_route_card_word(self, tp: TechProcess) -> Path:
        """Генерация маршрутной карты в Word с использованием шаблона."""
        template_path = TEMPLATES_DIR / 'ktd_docx' / 'route_card_template.docx'

        if template_path.exists():
            return self._generate_from_template(tp, template_path, 'MK')

        # Fallback: legacy программная генерация
        doc = Document()
        heading = doc.add_heading('МАРШРУТНАЯ КАРТА', level=1)
        heading.alignment = 1

        doc.add_paragraph(f"Обозначение: {tp.product.designation}")
        doc.add_paragraph(f"Наименование: {tp.product.name}")
        doc.add_paragraph(f"Материал: {tp.product.material.name if tp.product.material else ''}")
        doc.add_paragraph(f"ТП №: {tp.number}")
        doc.add_paragraph("")

        table = doc.add_table(rows=1, cols=6)
        table.style = 'Table Grid'
        headers = ["№ оп.", "Наименование операции", "Оборудование",
                   "Профессия", "Тшт, мин", "Тпз, мин"]
        for i, header in enumerate(headers):
            table.rows[0].cells[i].text = header
            table.rows[0].cells[i].paragraphs[0].runs[0].font.bold = True

        for operation in self._mtp_operations(tp):
            row = table.add_row()
            row.cells[0].text = operation.number
            row.cells[1].text = operation.name
            row.cells[2].text = operation.equipment.name if operation.equipment else ""
            profession_text = ""
            if operation.profession:
                profession_text = f"{operation.profession.name}"
                if operation.grade:
                    profession_text += f" р.{operation.grade}"
            row.cells[3].text = profession_text
            row.cells[4].text = str(operation.t_piece)
            row.cells[5].text = str(operation.t_setup)

        doc.add_paragraph("")
        doc.add_paragraph(f"Разработал: {tp.author.full_name if tp.author else ''}")
        doc.add_paragraph(f"Дата: {datetime.now().strftime('%d.%m.%Y')}")

        filename = f"{self._mk_basename(tp)}.docx"
        output_path = product_export_dir(tp.product) / filename
        doc.save(output_path)
        return output_path

    def _generate_from_template(self, tp: TechProcess, template_path: Path,
                                doc_type: str = 'MK') -> Path:
        """Заполнить шаблон .docx данными ТП (титульный лист или МК)."""
        doc = Document(str(template_path))

        product = tp.product
        material = product.material
        author = tp.author
        now = datetime.now()

        replacements = {
            '{{company}}': 'АО «УЗГА»',
            '{{designation}}': product.designation or '—',
            '{{name}}': product.name or '—',
            '{{material}}': f'{material.name} {material.grade}'
                            if material else '—',
            '{{hardness}}': '',
            '{{mass}}': str(product.mass) if product.mass else '—',
            '{{tp_number}}': tp.number or '—',
            '{{technology_type}}': tp.technology_type.value
                                   if hasattr(tp.technology_type, 'value')
                                   else str(tp.technology_type or ''),
            '{{date}}': now.strftime('%d.%m.%Y'),
            '{{author}}': author.full_name if author else '___________',
            '{{checker}}': '___________',
            '{{normer}}': '___________',
            '{{approver}}': '___________',
        }

        self._replace_in_doc(doc, replacements)

        # Для МК: заполнить таблицу операций
        if doc_type == 'MK':
            self._fill_operations_table(doc, tp)

        tag = 'MK' if doc_type == 'MK' else 'title'
        suffix = 'route_card' if doc_type == 'MK' else 'title_page'
        filename = f'{suffix}_{tp.number or "TP"}_{now.strftime("%Y%m%d_%H%M")}.docx'
        output_path = product_export_dir(tp.product) / filename
        doc.save(str(output_path))
        return output_path

    def _replace_in_doc(self, doc, replacements: dict):
        """Заменить плейсхолдеры во всех параграфах и таблицах документа."""
        for paragraph in doc.paragraphs:
            for key, value in replacements.items():
                if key in paragraph.text:
                    for run in paragraph.runs:
                        if key in run.text:
                            run.text = run.text.replace(key, value)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for key, value in replacements.items():
                            if key in paragraph.text:
                                for run in paragraph.runs:
                                    if key in run.text:
                                        run.text = run.text.replace(key, value)

    def _fill_operations_table(self, doc, tp: TechProcess):
        """Заполнить таблицу операций в шаблоне МК."""
        operations = self._mtp_operations(tp)
        if not operations:
            return

        total_piece = 0.0
        total_setup = 0.0

        # Найти таблицу с заголовком "№ оп."
        target_table = None
        for table in doc.tables:
            for row in table.rows:
                first_cell_text = row.cells[0].text if row.cells else ''
                if '№ оп.' in first_cell_text:
                    target_table = table
                    break
            if target_table:
                break

        if target_table is None:
            return

        # Удалить строки-плейсхолдеры (содержащие {{op_number}})
        rows_to_remove = []
        for i, row in enumerate(target_table.rows):
            first_cell_text = row.cells[0].text if row.cells else ''
            if '{{op_number}}' in first_cell_text:
                rows_to_remove.append(i)
        for idx in reversed(rows_to_remove):
            tr = target_table.rows[idx]._tr
            target_table._tbl.remove(tr)

        # Добавить строки с данными операций
        for op in operations:
            row = target_table.add_row()
            row.cells[0].text = op.number or ''
            row.cells[1].text = op.name or ''
            row.cells[2].text = op.equipment.name if op.equipment else ''
            row.cells[3].text = op.profession.name if op.profession else ''
            row.cells[4].text = str(op.grade) if op.grade else ''
            row.cells[5].text = str(op.t_piece or 0)
            row.cells[6].text = str(op.t_setup or 0)
            row.cells[7].text = str(op.t_main or 0)
            row.cells[8].text = str(op.t_auxiliary or 0)
            row.cells[9].text = op.shop or ''
            total_piece += op.t_piece or 0
            total_setup += op.t_setup or 0

        # Заменить итоги
        totals_replacements = {
            '{{total_t_piece}}': str(round(total_piece, 2)),
            '{{total_t_setup}}': str(round(total_setup, 2)),
        }
        self._replace_in_doc(doc, totals_replacements)

    def generate_title_page(self, tp_id: int) -> Path:
        """Сгенерировать титульный лист ТП."""
        tp = self.session.get(TechProcess, tp_id)
        if tp is None:
            raise ValueError(f'TechProcess {tp_id} not found')

        template_path = TEMPLATES_DIR / 'ktd_docx' / 'title_page_template.docx'
        if not template_path.exists():
            # Fallback: создать простой титульный лист
            return self._generate_title_page_simple(tp)

        return self._generate_from_template(tp, template_path, 'title')

    def _generate_title_page_simple(self, tp: TechProcess) -> Path:
        """Запасной генератор титульного листа без шаблона."""
        doc = Document()
        for _ in range(8):
            doc.add_paragraph('')

        p = doc.add_paragraph()
        p.alignment = 1
        run = p.add_run('ТЕХНОЛОГИЧЕСКИЙ ПРОЦЕСС')
        run.font.size = Pt(16)
        run.font.bold = True

        p = doc.add_paragraph()
        p.alignment = 1
        run = p.add_run(tp.number or '')
        run.font.size = Pt(14)

        doc.add_paragraph('')
        doc.add_paragraph(f'Обозначение: {tp.product.designation}')
        doc.add_paragraph(f'Изделие: {tp.product.name}')
        doc.add_paragraph(f'Материал: {tp.product.material.name if tp.product.material else "—"}')
        doc.add_paragraph(f'Дата: {datetime.now().strftime("%d.%m.%Y")}')

        filename = f'title_page_{tp.number or "TP"}.docx'
        output_path = product_export_dir(tp.product) / filename
        doc.save(str(output_path))
        return output_path
    
    def _generate_route_card_pdf(self, tp: TechProcess) -> Path:
        """Генерация маршрутной карты в PDF"""
        filename = f"{self._mk_basename(tp)}.pdf"
        output_path = product_export_dir(tp.product) / filename
        
        c = canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4
        
        # Заголовок
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2, height - 50, "МАРШРУТНАЯ КАРТА")
        
        # Информация о детали
        c.setFont("Helvetica", 10)
        y = height - 100
        c.drawString(50, y, f"Обозначение: {tp.product.designation}")
        y -= 20
        c.drawString(50, y, f"Наименование: {tp.product.name}")
        y -= 20
        c.drawString(50, y, f"Материал: {tp.product.material.name if tp.product.material else ''}")
        y -= 20
        c.drawString(50, y, f"ТП №: {tp.number}")
        
        # Таблица операций
        y -= 40
        c.setFont("Helvetica-Bold", 9)
        c.drawString(50, y, "№ оп.")
        c.drawString(100, y, "Наименование операции")
        c.drawString(300, y, "Оборудование")
        c.drawString(450, y, "Тшт, мин")
        
        c.setFont("Helvetica", 9)
        y -= 20
        
        for operation in self._mtp_operations(tp):
            if y < 100:  # Новая страница
                c.showPage()
                y = height - 50
            
            c.drawString(50, y, operation.number)
            c.drawString(100, y, operation.name[:30])
            c.drawString(300, y, operation.equipment.name[:20] if operation.equipment else "")
            c.drawString(450, y, str(operation.t_piece))
            y -= 15
        
        # Подписи
        y -= 30
        c.drawString(50, y, f"Разработал: {tp.author.full_name if tp.author else ''}")
        c.drawString(350, y, f"Дата: {datetime.now().strftime('%d.%m.%Y')}")
        
        c.save()
        
        return output_path
    
    def generate_operation_card(
        self,
        operation_id: int,
        output_format: str = "xlsx"
    ) -> Path:
        """Сгенерировать операционную карту (ГОСТ 3.1118-82)."""
        op = self.session.get(Operation, operation_id)
        if not op:
            raise ValueError(f"Операция с ID {operation_id} не найдена")
        tp = op.tech_process
        out_dir = product_export_dir(tp)

        if output_format == "xlsx":
            return self._generate_ok_excel(op, tp, out_dir)
        elif output_format == "pdf":
            return self._generate_ok_pdf(op, tp, out_dir)
        else:
            raise ValueError(f"Неподдерживаемый формат: {output_format}")

    def _generate_ok_excel(self, op: Operation, tp: TechProcess,
                           out_dir: Path) -> Path:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"ОК {op.number}"
        for col, w in zip('ABCDEFGH', [8, 30, 20, 20, 12, 12, 12, 12]):
            ws.column_dimensions[col].width = w

        ws['A1'] = "ОПЕРАЦИОННАЯ КАРТА (ГОСТ 3.1118-82)"
        ws['A1'].font = Font(size=14, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:H1')

        row = 3
        ws[f'A{row}'] = "Обозначение:"; ws[f'B{row}'] = tp.product.designation
        ws[f'D{row}'] = "ТП №:"; ws[f'E{row}'] = tp.number; row += 1
        ws[f'A{row}'] = "Наименование:"; ws[f'B{row}'] = tp.product.name; row += 1
        ws[f'A{row}'] = "Операция:"; ws[f'B{row}'] = f"{op.number} — {op.name}"
        ws[f'D{row}'] = "Оборудование:"
        ws[f'E{row}'] = op.equipment.name if op.equipment else ""
        ws.merge_cells(f'B{row}:C{row}'); ws.merge_cells(f'E{row}:H{row}'); row += 1
        ws[f'A{row}'] = "Профессия:"
        ws[f'B{row}'] = op.profession.name if op.profession else ""
        ws[f'D{row}'] = "Разряд:"; ws[f'E{row}'] = str(op.grade or '')
        ws[f'F{row}'] = "Тпз:"; ws[f'G{row}'] = f'{op.t_setup or 0:.1f}'
        ws[f'H{row}'] = "Тшт:"; ws[f'I{row}'] = f'{op.t_piece or 0:.1f}'
        row += 2

        headers = ["№", "Содержание перехода", "D, мм", "L, мм",
                   "t, мм", "S", "n, об/мин", "i"]
        for col, h in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=h)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center', vertical='center',
                                       wrap_text=True)
            cell.border = Border(left=Side(style='thin'),
                                 right=Side(style='thin'),
                                 top=Side(style='thin'),
                                 bottom=Side(style='thin'))
        row += 1

        transitions = sorted(
            [t for t in op.transitions
             if not getattr(t, 'is_deleted', False)],
            key=lambda t: (t.sort_order or 0),
        )
        for tr in transitions:
            ws.cell(row=row, column=1, value=tr.number or '').alignment = \
                Alignment(horizontal='center')
            ws.cell(row=row, column=2, value=tr.text or '')
            ws.cell(row=row, column=3, value=tr.diameter or '')
            ws.cell(row=row, column=4, value=tr.length or '')
            ws.cell(row=row, column=5, value=tr.depth or '')
            ws.cell(row=row, column=6, value=tr.feed or '')
            ws.cell(row=row, column=7, value=tr.rpm or '')
            ws.cell(row=row, column=8, value=tr.passes or 1)
            for c in range(1, 9):
                ws.cell(row=row, column=c).border = Border(
                    left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin'))
            row += 1

        fname = self._mk_basename(tp) + f'_OK_{op.number}.xlsx'
        out_path = out_dir / fname
        wb.save(str(out_path))
        return out_path

    def _generate_ok_pdf(self, op: Operation, tp: TechProcess,
                         out_dir: Path) -> Path:
        from reportlab.lib.units import mm
        c = canvas.Canvas(str(out_dir / f'{self._mk_basename(tp)}_OK_{op.number}.pdf'),
                          pagesize=A4)
        w, h = A4
        c.setFont("Helvetica-Bold", 14)
        c.drawString(30, h - 30, f"ОПЕРАЦИОННАЯ КАРТА — {op.number} {op.name}")
        c.setFont("Helvetica", 10)
        y = h - 60
        c.drawString(30, y, f"Деталь: {tp.product.designation} — {tp.product.name}")
        y -= 16
        c.drawString(30, y, f"Оборудование: {op.equipment.name if op.equipment else ''}")
        y -= 16
        c.drawString(30, y,
                     f"Тпз={op.t_setup or 0:.1f} мин  Тшт={op.t_piece or 0:.1f} мин")
        y -= 30
        c.drawString(30, y, "Переходы:")
        y -= 16
        for tr in sorted(
            [t for t in op.transitions
             if not getattr(t, 'is_deleted', False)],
            key=lambda t: (t.sort_order or 0),
        ):
            c.drawString(45, y, f"{tr.number}. {tr.text or ''}")
            y -= 14
            if y < 40:
                c.showPage()
                y = h - 40
        c.save()
        return out_dir / f'{self._mk_basename(tp)}_OK_{op.number}.pdf'

    def generate_material_specification(
        self,
        tech_process_id: int,
        output_format: str = "xlsx"
    ) -> Path:
        """Сгенерировать материальную спецификацию."""
        tp = self.session.get(TechProcess, tech_process_id)
        if not tp:
            raise ValueError(f"ТП с ID {tech_process_id} не найден")
        out_dir = product_export_dir(tp)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Материальная спецификация"
        for col, w in zip('ABCDEFG', [10, 25, 15, 12, 12, 15, 15]):
            ws.column_dimensions[col].width = w

        ws['A1'] = "МАТЕРИАЛЬНАЯ СПЕЦИФИКАЦИЯ"
        ws['A1'].font = Font(size=14, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:G1')

        row = 3
        ws[f'A{row}'] = "Обозначение:"; ws[f'B{row}'] = tp.product.designation; row += 1
        ws[f'A{row}'] = "Наименование:"; ws[f'B{row}'] = tp.product.name; row += 1
        ws[f'A{row}'] = "ТП №:"; ws[f'B{row}'] = tp.number; row += 2

        headers = ["Поз.", "Наименование материала", "Марка/ГОСТ",
                   "Норма, кг", "Отходы, %", "Стоимость/дет.", "КИМ"]
        for col, h in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=h)
            cell.font = Font(bold=True)
            cell.border = Border(left=Side(style='thin'),
                                 right=Side(style='thin'),
                                 top=Side(style='thin'),
                                 bottom=Side(style='thin'))
        row += 1

        for i, mn in enumerate(tp.material_norms):
            ws.cell(row=row, column=1, value=i + 1)
            mat = mn.material.name if hasattr(mn, 'material') and mn.material else ''
            ws.cell(row=row, column=2, value=mat)
            grade = ''
            if hasattr(mn, 'material') and mn.material:
                grade = f"{mn.material.grade or ''} {mn.material.gost or ''}"
            ws.cell(row=row, column=3, value=grade.strip())
            ws.cell(row=row, column=4, value=mn.norm_per_piece or 0)
            ws.cell(row=row, column=5, value=mn.waste_percent or 0)
            ws.cell(row=row, column=6, value=mn.cost_per_piece or 0)
            kim = 1.0 - (mn.waste_percent or 0) / 100.0
            ws.cell(row=row, column=7, value=round(kim, 3))
            for c in range(1, 8):
                ws.cell(row=row, column=c).border = Border(
                    left=Side(style='thin'), right=Side(style='thin'),
                    top=Side(style='thin'), bottom=Side(style='thin'))
            row += 1

        fname = self._mk_basename(tp) + '_material_spec.xlsx'
        out_path = out_dir / fname
        wb.save(str(out_path))
        return out_path

    # ──────────────────────────────────────────────────────────────
    # Operation cards — all operations in a TP
    # ──────────────────────────────────────────────────────────────

    def generate_all_operation_cards(
        self, tech_process_id: int, output_format: str = "xlsx"
    ) -> List[Path]:
        """Generate OK (ГОСТ 3.1118-82) for every operation in the TP."""
        tp = self.session.get(TechProcess, tech_process_id)
        if not tp:
            raise ValueError(f"ТП с ID {tech_process_id} не найден")
        out_dir = product_export_dir(tp)
        files: List[Path] = []
        ops = [o for o in tp.operations
               if not getattr(o, 'is_deleted', False)]
        for op in ops:
            if output_format == "xlsx":
                files.append(self._generate_ok_excel(op, tp, out_dir))
            elif output_format == "pdf":
                files.append(self._generate_ok_pdf(op, tp, out_dir))
        return files

    # ──────────────────────────────────────────────────────────────
    # Sketch card (Карта эскизов — КЭ)
    # ──────────────────────────────────────────────────────────────

    def generate_sketch_card(
        self, tech_process_id: int, output_format: str = "xlsx"
    ) -> Path:
        """Generate sketch card listing all sketches per operation."""
        tp = self.session.get(TechProcess, tech_process_id)
        if not tp:
            raise ValueError(f"ТП с ID {tech_process_id} не найден")
        out_dir = product_export_dir(tp)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Карта эскизов"
        for col, w in zip('ABCDEF', [8, 30, 12, 30, 20]):
            ws.column_dimensions[col].width = w

        ws['A1'] = "КАРТА ЭСКИЗОВ (КЭ)"
        ws['A1'].font = Font(size=14, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:F1')

        row = 3
        ws[f'A{row}'] = "Обозначение:"; ws[f'B{row}'] = tp.product.designation
        ws[f'D{row}'] = "ТП №:"; ws[f'E{row}'] = tp.number; row += 1
        ws[f'A{row}'] = "Наименование:"; ws[f'B{row}'] = tp.product.name
        row += 2

        headers = ["Оп.", "Эскиз (файл)", "Тип", "Подпись", "Дата"]
        for col, h in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=h)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
            cell.border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'))
        row += 1

        ops = sorted(
            [o for o in tp.operations
             if not getattr(o, 'is_deleted', False)],
            key=lambda o: (o.sort_order or 0),
        )
        for op in ops:
            sketches = [sk for sk in (op.sketches or [])
                        if not getattr(sk, 'is_deleted', False)]
            if sketches:
                for sk in sketches:
                    ws.cell(row=row, column=1, value=op.number or '').alignment = \
                        Alignment(horizontal='center')
                    ws.cell(row=row, column=2,
                            value=sk.original_filename or sk.stored_path or '')
                    ws.cell(row=row, column=3,
                            value=sk.file_type or '')
                    ws.cell(row=row, column=4,
                            value=sk.title or '')
                    ws.cell(row=row, column=5,
                            value=sk.created_at.strftime('%Y-%m-%d')
                            if sk.created_at else '')
                    for c in range(1, 6):
                        ws.cell(row=row, column=c).border = Border(
                            left=Side(style='thin'), right=Side(style='thin'),
                            top=Side(style='thin'), bottom=Side(style='thin'))
                    row += 1
            else:
                ws.cell(row=row, column=1, value=op.number or '').alignment = \
                    Alignment(horizontal='center')
                ws.cell(row=row, column=2, value="— эскизов нет —")
                for c in range(1, 6):
                    ws.cell(row=row, column=c).border = Border(
                        left=Side(style='thin'), right=Side(style='thin'),
                        top=Side(style='thin'), bottom=Side(style='thin'))
                row += 1

        fname = self._mk_basename(tp) + '_sketch_card.xlsx'
        out_path = out_dir / fname
        wb.save(str(out_path))
        return out_path

    # ──────────────────────────────────────────────────────────────
    # Tooling list (Ведомость оснастки — ВО)
    # ──────────────────────────────────────────────────────────────

    def generate_tooling_list(
        self, tech_process_id: int, output_format: str = "xlsx"
    ) -> Path:
        """Generate tooling list (ВО) for a TP — tools + tooling items per operation."""
        tp = self.session.get(TechProcess, tech_process_id)
        if not tp:
            raise ValueError(f"ТП с ID {tech_process_id} не найден")
        out_dir = product_export_dir(tp)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Ведомость оснастки"
        for col, w in zip('ABCDEFG', [6, 8, 30, 30, 12, 15, 25]):
            ws.column_dimensions[col].width = w

        ws['A1'] = "ВЕДОМОСТЬ ОСНАСТКИ (ВО)"
        ws['A1'].font = Font(size=14, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:G1')

        row = 3
        ws[f'A{row}'] = "Обозначение:"; ws[f'B{row}'] = tp.product.designation
        ws[f'D{row}'] = "ТП №:"; ws[f'E{row}'] = tp.number; row += 1
        ws[f'A{row}'] = "Наименование:"; ws[f'B{row}'] = tp.product.name
        row += 2

        headers = ["Оп.", "Поз.", "Наименование", "Обозначение",
                   "Кол.", "Тип", "Примечание"]
        for col, h in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=h)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center', wrap_text=True)
            cell.border = Border(
                left=Side(style='thin'), right=Side(style='thin'),
                top=Side(style='thin'), bottom=Side(style='thin'))
        row += 1

        ops = sorted(
            [o for o in tp.operations
             if not getattr(o, 'is_deleted', False)],
            key=lambda o: (o.sort_order or 0),
        )
        pos = 0
        for op in ops:
            # Tools (OperationTool)
            for ot in (op.tools or []):
                pos += 1
                tool = ot.tool
                ws.cell(row=row, column=1, value=op.number or '')
                ws.cell(row=row, column=2, value=pos)
                ws.cell(row=row, column=3, value=tool.name if tool else '')
                ws.cell(row=row, column=4,
                        value=tool.designation if tool else '')
                ws.cell(row=row, column=5, value=ot.quantity or 1)
                ws.cell(row=row, column=6, value=tool.tool_type if tool else '')
                ws.cell(row=row, column=7, value='')
                for c in range(1, 8):
                    ws.cell(row=row, column=c).border = Border(
                        left=Side(style='thin'), right=Side(style='thin'),
                        top=Side(style='thin'), bottom=Side(style='thin'))
                row += 1

            # Tooling items (OperationTooling) — query directly (no relationship on Operation)
            from database.models import OperationTooling, ToolingItem
            op_toolings = (self.session.query(OperationTooling, ToolingItem)
                           .join(ToolingItem,
                                 OperationTooling.tooling_item_id == ToolingItem.id)
                           .filter(OperationTooling.operation_id == op.id)
                           .all())
            for ot_item, ti in op_toolings:
                pos += 1
                ws.cell(row=row, column=1, value=op.number or '')
                ws.cell(row=row, column=2, value=pos)
                ws.cell(row=row, column=3, value=ti.name)
                ws.cell(row=row, column=4, value=ti.inventory_no)
                ws.cell(row=row, column=5, value=1)
                ws.cell(row=row, column=6, value='Оснастка')
                ws.cell(row=row, column=7, value=ot_item.notes or '')
                for c in range(1, 8):
                    ws.cell(row=row, column=c).border = Border(
                        left=Side(style='thin'), right=Side(style='thin'),
                        top=Side(style='thin'), bottom=Side(style='thin'))
                row += 1

        if pos == 0:
            ws.cell(row=row, column=1, value='')
            ws.cell(row=row, column=2, value='')
            ws.cell(row=row, column=3, value="— оснастки нет —")
            ws.merge_cells(f'C{row}:G{row}')

        fname = self._mk_basename(tp) + '_tooling_list.xlsx'
        out_path = out_dir / fname
        wb.save(str(out_path))
        return out_path

    # ──────────────────────────────────────────────────────────────
    # Material list (Ведомость материалов — ВМ) — delegates
    # ──────────────────────────────────────────────────────────────

    def generate_material_list(
        self, tech_process_id: int, output_format: str = "xlsx"
    ) -> Path:
        """Alias for generate_material_specification (ВМ = material list)."""
        return self.generate_material_specification(tech_process_id, output_format)

    # ──────────────────────────────────────────────────────────────
    # Full document pack — MK + OK + КЭ + ВО + ВМ + ZIP
    # ──────────────────────────────────────────────────────────────

    def generate_document_pack(self, tech_process_id: int) -> List[Path]:
        """Generate complete document pack: title page, MK, OK, sketch card,
        tooling list, material list.  Returns list of file paths.
        """
        import zipfile
        tp = self.session.get(TechProcess, tech_process_id)
        if not tp:
            raise ValueError(f"ТП с ID {tech_process_id} не найден")

        out_dir = product_export_dir(tp)
        files: List[Path] = []

        # 0. Title page (титульный лист)
        try:
            files.append(self.generate_title_page(tech_process_id))
        except Exception:
            _logger.exception("Unhandled error")

        # 1. Route card (MK)
        files.append(self._generate_route_card_excel(tp))

        # 2. Operation cards (OK) — all non-deleted operations
        for op in tp.operations:
            if not getattr(op, 'is_deleted', False):
                files.append(self._generate_ok_excel(op, tp, out_dir))

        # 3. Sketch card (KЭ)
        try:
            files.append(self.generate_sketch_card(tech_process_id))
        except Exception:
            _logger.exception("Unhandled error")

        # 4. Tooling list (ВО)
        try:
            files.append(self.generate_tooling_list(tech_process_id))
        except Exception:
            _logger.exception("Unhandled error")

        # 5. Material list (ВМ)
        if tp.material_norms:
            try:
                files.append(self.generate_material_specification(
                    tech_process_id))
            except Exception:
                _logger.exception("Unhandled error")

        # 6. ZIP archive
        zip_name = self._mk_basename(tp) + '_pack.zip'
        zip_path = out_dir / zip_name
        with zipfile.ZipFile(str(zip_path), 'w',
                             compression=zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(str(f), f.name)
        files.append(zip_path)

        return files
