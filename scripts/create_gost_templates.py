"""Generate 7 GOST .docx templates for ktd_docx."""
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

OUT_DIR = Path(__file__).parent.parent / 'resources' / 'templates' / 'ktd_docx'
OUT_DIR.mkdir(parents=True, exist_ok=True)

def _add_bordered_table(doc, headers, placeholder_rows, col_widths=None):
    """Add a table with header row + placeholder data rows."""
    table = doc.add_table(rows=1 + len(placeholder_rows), cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for run in cell.paragraphs[0].runs:
            run.font.bold = True
            run.font.size = Pt(9)
    for r, row_data in enumerate(placeholder_rows, start=1):
        for c, val in enumerate(row_data):
            table.rows[r].cells[c].text = val
            for run in table.rows[r].cells[c].paragraphs[0].runs:
                run.font.size = Pt(9)
    return table

# ═══════════════════════════════════════════════════════════════
# 1. title_page.docx — Титульный лист (ГОСТ 3.1105-84 форма 1)
# ═══════════════════════════════════════════════════════════════
def create_title_page():
    doc = Document()
    style = doc.styles['Normal']
    style.font.size = Pt(12)

    for _ in range(6):
        doc.add_paragraph('')

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('{{company}}')
    run.font.size = Pt(14)
    run.font.bold = True

    doc.add_paragraph('')

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('ТЕХНОЛОГИЧЕСКИЙ ПРОЦЕСС')
    run.font.size = Pt(16)
    run.font.bold = True

    doc.add_paragraph('')

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('{{tp_number}}')
    run.font.size = Pt(14)

    doc.add_paragraph('')
    doc.add_paragraph('')

    fields = [
        ('Обозначение изделия:', '{{designation}}'),
        ('Наименование изделия:', '{{name}}'),
        ('Материал:', '{{material}}'),
        ('Вид технологии:', '{{technology_type}}'),
        ('Масса изделия, кг:', '{{mass}}'),
    ]
    for label, placeholder in fields:
        p = doc.add_paragraph()
        run = p.add_run(f'{label}  {placeholder}')
        run.font.size = Pt(12)

    doc.add_paragraph('')
    doc.add_paragraph('')

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.add_run('Дата: {{date}}').font.size = Pt(11)

    doc.add_paragraph('')

    sig_fields = [
        ('Разработал:', '{{author}}'),
        ('Проверил:', '{{checker}}'),
        ('Нормировал:', '{{normer}}'),
        ('Утвердил:', '{{approver}}'),
    ]
    for label, placeholder in sig_fields:
        p = doc.add_paragraph()
        run = p.add_run(f'{label}  {placeholder}')
        run.font.size = Pt(11)

    doc.save(str(OUT_DIR / 'title_page.docx'))
    print('Created title_page.docx')

# ═══════════════════════════════════════════════════════════════
# 2. route_card.docx — Маршрутная карта (ГОСТ 3.1118-82 форма 1)
# ═══════════════════════════════════════════════════════════════
def create_route_card():
    doc = Document()
    style = doc.styles['Normal']
    style.font.size = Pt(10)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('МАРШРУТНАЯ КАРТА (ГОСТ 3.1118-82)')
    run.font.size = Pt(14)
    run.font.bold = True

    doc.add_paragraph('')

    info_fields = [
        'Обозначение: {{designation}}',
        'Изделие: {{name}}',
        'Материал: {{material}}',
        'ТП №: {{tp_number}}',
        'Дата: {{date}}',
    ]
    for f in info_fields:
        doc.add_paragraph(f)

    doc.add_paragraph('')

    headers = ["№ оп.", "Наименование операции", "Оборудование",
               "Профессия", "Разряд", "Тшт, мин", "Тпз, мин",
               "Тосн, мин", "Твсп, мин", "Цех"]
    placeholders = [
        ["{{op_number}}", "{{op_name}}", "{{op_equipment}}",
         "{{op_profession}}", "{{op_grade}}", "{{op_t_piece}}",
         "{{op_t_setup}}", "{{op_t_main}}", "{{op_t_auxiliary}}",
         "{{op_shop}}"],
    ]
    _add_bordered_table(doc, headers, placeholders)

    doc.add_paragraph('')
    p = doc.add_paragraph()
    p.add_run('Итого:  Тшт = {{total_t_piece}} мин   Тпз = {{total_t_setup}} мин').font.bold = True

    doc.add_paragraph('')
    sig_row = 'Разработал: {{author}}    Проверил: {{checker}}    Нормировал: {{normer}}'
    doc.add_paragraph(sig_row)

    doc.save(str(OUT_DIR / 'route_card.docx'))
    print('Created route_card.docx')

# ═══════════════════════════════════════════════════════════════
# 3. operation_card.docx — Операционная карта (ГОСТ 3.1404-86 форма 3)
# ═══════════════════════════════════════════════════════════════
def create_operation_card():
    doc = Document()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('ОПЕРАЦИОННАЯ КАРТА (ГОСТ 3.1118-82)')
    run.font.size = Pt(14)
    run.font.bold = True

    doc.add_paragraph('')

    info_fields = [
        'Деталь: {{designation}} — {{name}}',
        'ТП №: {{tp_number}}',
        'Операция: {{op_number}} — {{op_name}}',
        'Оборудование: {{op_equipment}}',
        'Профессия: {{op_profession}}   Разряд: {{op_grade}}',
        'Тпз: {{op_t_setup}} мин   Тшт: {{op_t_piece}} мин',
    ]
    for f in info_fields:
        doc.add_paragraph(f)

    doc.add_paragraph('')

    headers = ["№", "Содержание перехода", "D, мм", "L, мм",
               "t, мм", "S", "n, об/мин", "i"]
    placeholders = [
        ["{{tr_number}}", "{{tr_text}}", "{{tr_diameter}}",
         "{{tr_length}}", "{{tr_depth}}", "{{tr_feed}}",
         "{{tr_rpm}}", "{{tr_passes}}"],
    ]
    _add_bordered_table(doc, headers, placeholders)

    doc.save(str(OUT_DIR / 'operation_card.docx'))
    print('Created operation_card.docx')

# ═══════════════════════════════════════════════════════════════
# 4. tooling_list.docx — Ведомость оснастки (ГОСТ 3.1122-84)
# ═══════════════════════════════════════════════════════════════
def create_tooling_list():
    doc = Document()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('ВЕДОМОСТЬ ОСНАСТКИ (ГОСТ 3.1122-84)')
    run.font.size = Pt(14)
    run.font.bold = True

    doc.add_paragraph('')
    doc.add_paragraph('Обозначение: {{designation}}     Изделие: {{name}}     ТП №: {{tp_number}}')
    doc.add_paragraph('')

    headers = ["Оп.", "Поз.", "Наименование", "Обозначение", "Кол.", "Тип", "Примечание"]
    placeholders = [
        ["{{tool_op_number}}", "{{tool_pos}}", "{{tool_name}}",
         "{{tool_designation}}", "{{tool_qty}}", "{{tool_type}}", "{{tool_note}}"],
    ]
    _add_bordered_table(doc, headers, placeholders)

    doc.save(str(OUT_DIR / 'tooling_list.docx'))
    print('Created tooling_list.docx')

# ═══════════════════════════════════════════════════════════════
# 5. material_list.docx — Ведомость материалов (ГОСТ 3.1123-84)
# ═══════════════════════════════════════════════════════════════
def create_material_list():
    doc = Document()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('ВЕДОМОСТЬ МАТЕРИАЛОВ (ГОСТ 3.1123-84)')
    run.font.size = Pt(14)
    run.font.bold = True

    doc.add_paragraph('')
    doc.add_paragraph('Обозначение: {{designation}}     Изделие: {{name}}     ТП №: {{tp_number}}')
    doc.add_paragraph('')

    headers = ["Поз.", "Наименование материала", "Марка/ГОСТ",
               "Норма, кг", "Отходы, %", "Стоимость/дет.", "КИМ"]
    placeholders = [
        ["{{mat_pos}}", "{{mat_name}}", "{{mat_grade}}",
         "{{mat_norm}}", "{{mat_waste}}", "{{mat_cost}}", "{{mat_kim}}"],
    ]
    _add_bordered_table(doc, headers, placeholders)

    doc.save(str(OUT_DIR / 'material_list.docx'))
    print('Created material_list.docx')

# ═══════════════════════════════════════════════════════════════
# 6. sketch_card.docx — Карта эскизов (ГОСТ 3.1105-84)
# ═══════════════════════════════════════════════════════════════
def create_sketch_card():
    doc = Document()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('КАРТА ЭСКИЗОВ (КЭ)')
    run.font.size = Pt(14)
    run.font.bold = True

    doc.add_paragraph('')
    doc.add_paragraph('Обозначение: {{designation}}     Изделие: {{name}}     ТП №: {{tp_number}}')
    doc.add_paragraph('')

    headers = ["Оп.", "Эскиз (файл)", "Тип", "Подпись", "Дата"]
    placeholders = [
        ["{{sketch_op}}", "{{sketch_file}}", "{{sketch_type}}",
         "{{sketch_author}}", "{{sketch_date}}"],
    ]
    _add_bordered_table(doc, headers, placeholders)

    doc.save(str(OUT_DIR / 'sketch_card.docx'))
    print('Created sketch_card.docx')

# ═══════════════════════════════════════════════════════════════
# 7. control_card.docx — Контрольная карта (ГОСТ 3.1502-85)
# ═══════════════════════════════════════════════════════════════
def create_control_card():
    doc = Document()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('КОНТРОЛЬНАЯ КАРТА (ГОСТ 3.1502-85)')
    run.font.size = Pt(14)
    run.font.bold = True

    doc.add_paragraph('')
    doc.add_paragraph('Обозначение: {{designation}}     Изделие: {{name}}     ТП №: {{tp_number}}')
    doc.add_paragraph('Дата: {{date}}')
    doc.add_paragraph('')

    headers = ["№", "Контролируемый параметр", "Средство измерения",
               "Допуск", "Периодичность", "Исполнитель"]
    placeholders = [
        ["{{ctrl_number}}", "{{ctrl_param}}", "{{ctrl_instrument}}",
         "{{ctrl_tolerance}}", "{{ctrl_frequency}}", "{{ctrl_executor}}"],
    ]
    _add_bordered_table(doc, headers, placeholders)

    doc.add_paragraph('')
    doc.add_paragraph('Контролёр: {{checker}}    Дата: {{date}}')

    doc.save(str(OUT_DIR / 'control_card.docx'))
    print('Created control_card.docx')


if __name__ == '__main__':
    create_title_page()
    create_route_card()
    create_operation_card()
    create_tooling_list()
    create_material_list()
    create_sketch_card()
    create_control_card()
    print(f'\nAll 7 templates created in {OUT_DIR}')
