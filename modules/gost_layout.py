"""
GOST document layout engine — proper formatting per ESKD standards.

Produces documents compliant with:
  GOST 3.1103-82 — Main stamp
  GOST 3.1118-82 — Route card (MK)
  GOST 3.1404-86 — Operation card (OK)
  GOST 3.1105-84 — Title page
"""
from datetime import datetime

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Cm, Mm, Pt

# ═══════ Page setup ═══════

def gost_page_setup(doc, landscape=True):
    section = doc.sections[0]
    if landscape:
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width = Mm(297)
        section.page_height = Mm(210)
    else:
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = Mm(210)
        section.page_height = Mm(297)
    section.left_margin = Mm(20)
    section.right_margin = Mm(5)
    section.top_margin = Mm(5)
    section.bottom_margin = Mm(5)


# ═══════ Main stamp (GOST 3.1103-82) ═══════

def add_gost_stamp(doc, tp):
    stamp = doc.add_table(rows=4, cols=10)
    stamp.alignment = WD_TABLE_ALIGNMENT.RIGHT
    stamp.style = 'Table Grid'

    # Row 1
    r = stamp.rows[0]
    _cell(r.cells[0], tp.number or '', Pt(7))
    _cell(r.cells[1], '', Pt(7))

    # Row 2
    r = stamp.rows[1]
    author = tp.author.full_name if tp.author else '___________'
    ds = datetime.now().strftime('%d.%m.%Y')
    _cell(r.cells[0], 'Paspa6.', Pt(6))
    _cell(r.cells[1], author, Pt(6))
    _cell(r.cells[2], ds, Pt(6))
    _cell(r.cells[3], 'IIpoB.', Pt(6))
    _cell(r.cells[4], '___________', Pt(6))
    _cell(r.cells[5], ds, Pt(6))

    # Row 3
    r = stamp.rows[2]
    _cell(r.cells[0], 'H.KoHTp.', Pt(6))
    _cell(r.cells[1], '___________', Pt(6))
    _cell(r.cells[2], ds, Pt(6))
    _cell(r.cells[3], 'YTB.', Pt(6))
    _cell(r.cells[4], '___________', Pt(6))
    _cell(r.cells[5], ds, Pt(6))

    # Row 4
    r = stamp.rows[3]
    _cell(r.cells[0], 'GOCT', Pt(6))
    r.cells[1].merge(r.cells[3])
    _cell(r.cells[1], '3.1118-82', Pt(6))
    r.cells[4].merge(r.cells[9])
    _cell(r.cells[4], 'JIucT 1 / JIucTOB 1', Pt(6))

    doc.add_paragraph('')
    return stamp


# ═══════ Route Card MK (GOST 3.1118-82 Form 1) ═══════

def build_route_card_docx(tp, operations):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(9)
    gost_page_setup(doc, landscape=True)

    # Title
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('MAPLLIPYTHAR KAPTA')
    r.font.size = Pt(14)
    r.font.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run('GOCT 3.1118-82  OopMa 1').font.size = Pt(9)

    # Info header
    info = doc.add_table(rows=2, cols=6)
    info.style = 'Table Grid'
    info.alignment = WD_TABLE_ALIGNMENT.CENTER

    labels = ['O6o3Ha4eHue', 'HauMeHoBaHue', 'MaTepuaJI', 'TII No', 'TeXHOJIOrUU', 'Macca, Kr']
    values = [
        tp.product.designation or '—',
        tp.product.name or '—',
        f'{tp.product.material.name} {tp.product.material.grade}' if tp.product.material else '—',
        tp.number or '—',
        tp.technology_type.value if hasattr(tp.technology_type, 'value') else str(tp.technology_type or ''),
        str(tp.product.mass) if tp.product.mass else '—',
    ]
    for j in range(6):
        _cell(info.rows[0].cells[j], labels[j], Pt(7), True)
        _cell(info.rows[1].cells[j], values[j], Pt(8))

    doc.add_paragraph('')

    # Operations table
    ops = operations or []
    n = max(len(ops), 1)
    table = doc.add_table(rows=1 + n, cols=12)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ['Ne on.', 'Kod', 'HauMeHoBaHue onepauuu', 'Llex', 'Y4.', 'PM',
               'O6opygoBaHue', 'IIpoeccu', 'Pa3p9g', 'Tn3', 'TLIT', 'To']
    for i, h in enumerate(headers):
        c = table.rows[0].cells[i]
        _cell(c, h, Pt(6), True)
        _shade(c, 'D9D9D9')

    for ri, op in enumerate(ops, start=1):
        row = table.rows[ri]
        _cell(row.cells[0], op.number or '', Pt(7))
        _cell(row.cells[1], getattr(op, 'op_type_code', '') or '', Pt(7))
        _cell(row.cells[2], op.name or '', Pt(7))
        _cell(row.cells[3], getattr(op, 'shop', '') or '', Pt(7))
        _cell(row.cells[4], '', Pt(7))
        _cell(row.cells[5], '', Pt(7))
        equip = op.equipment.name if op.equipment else ''
        _cell(row.cells[6], equip, Pt(7))
        prof = op.profession.name if op.profession else ''
        if op.grade:
            prof += f' p.{op.grade}'
        _cell(row.cells[7], prof, Pt(7))
        _cell(row.cells[8], str(op.grade) if op.grade else '', Pt(7))
        _cell(row.cells[9], _fmt(op.t_setup), Pt(7))
        _cell(row.cells[10], _fmt(op.t_piece), Pt(7))
        _cell(row.cells[11], _fmt(op.t_main), Pt(7))

    # Column widths
    widths = [Cm(1.0), Cm(0.8), Cm(3.5), Cm(0.8), Cm(0.8), Cm(0.8),
              Cm(2.5), Cm(2.0), Cm(0.8), Cm(1.0), Cm(1.0), Cm(1.0)]
    for row in table.rows:
        for i, w in enumerate(widths):
            if i < len(row.cells):
                row.cells[i].width = w

    doc.add_paragraph('')
    add_gost_stamp(doc, tp)
    return doc


# ═══════ Operation Card OK (GOST 3.1404-86 Form 3) ═══════

def build_operation_card_docx(tp, op, transitions):
    doc = Document()
    gost_page_setup(doc, landscape=True)

    # Title
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('OIIEPALIUOHHAR KAPTA')
    r.font.size = Pt(14)
    r.font.bold = True

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run('GOCT 3.1404-86  OopMa 3').font.size = Pt(9)

    # Info block
    info = doc.add_table(rows=2, cols=6)
    info.style = 'Table Grid'
    _cell(info.rows[0].cells[0], 'O6o3Ha4eHue', Pt(7), True)
    _cell(info.rows[1].cells[0], tp.product.designation or '—', Pt(8))
    _cell(info.rows[0].cells[1], 'TII No', Pt(7), True)
    _cell(info.rows[1].cells[1], tp.number or '—', Pt(8))
    _cell(info.rows[0].cells[2], 'Onepauu9', Pt(7), True)
    _cell(info.rows[1].cells[2], f'{op.number} — {op.name}', Pt(8))
    _cell(info.rows[0].cells[3], 'O6opygoBaHue', Pt(7), True)
    _cell(info.rows[1].cells[3], op.equipment.name if op.equipment else '—', Pt(8))
    _cell(info.rows[0].cells[4], 'Tn3, MuH', Pt(7), True)
    _cell(info.rows[1].cells[4], _fmt(op.t_setup), Pt(8))
    _cell(info.rows[0].cells[5], 'TLIT, MuH', Pt(7), True)
    _cell(info.rows[1].cells[5], _fmt(op.t_piece), Pt(8))

    doc.add_paragraph('')

    # Transitions table
    trs = transitions or []
    n = max(len(trs), 1)
    table = doc.add_table(rows=1 + n, cols=8)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    hdrs = ['Ne', 'CogepxaHue nepexoga', 'D, MM', 'L, MM', 't, MM', 'S', 'n, o6/MuH', 'i']
    for i, h in enumerate(hdrs):
        _cell(table.rows[0].cells[i], h, Pt(6), True)
        _shade(table.rows[0].cells[i], 'D9D9D9')

    for ri, tr in enumerate(trs, start=1):
        row = table.rows[ri]
        _cell(row.cells[0], tr.number or '', Pt(7))
        _cell(row.cells[1], tr.text or '', Pt(7))
        _cell(row.cells[2], str(tr.diameter or ''), Pt(7))
        _cell(row.cells[3], str(tr.length or ''), Pt(7))
        _cell(row.cells[4], str(tr.depth or ''), Pt(7))
        _cell(row.cells[5], str(tr.feed or ''), Pt(7))
        _cell(row.cells[6], str(tr.rpm or ''), Pt(7))
        _cell(row.cells[7], str(tr.passes or 1), Pt(7))

    widths = [Cm(1.0), Cm(8.0), Cm(1.5), Cm(1.5), Cm(1.5), Cm(1.5), Cm(2.0), Cm(1.0)]
    for row in table.rows:
        for i, w in enumerate(widths):
            if i < len(row.cells):
                row.cells[i].width = w

    doc.add_paragraph('')
    add_gost_stamp(doc, tp)
    return doc


# ═══════ Title page (GOST 3.1105-84 Form 1) ═══════

def build_title_page_docx(tp):
    doc = Document()
    gost_page_setup(doc, landscape=False)

    for _ in range(4):
        doc.add_paragraph('')

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run('AO <<Y3GA>>').font.size = Pt(14)

    doc.add_paragraph('')

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('TEXHOJIOrUUECKUU IIpOLLECC')
    r.font.size = Pt(16)
    r.font.bold = True

    doc.add_paragraph('')
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(tp.number or '').font.size = Pt(14)

    doc.add_paragraph('')
    doc.add_paragraph('')

    fields = [
        ('O6o3Ha4eHue u3geJIu9:', tp.product.designation),
        ('HauMeHoBaHue u3geJIu9:', tp.product.name),
        ('MaTepuaJI:', f'{tp.product.material.name} {tp.product.material.grade}' if tp.product.material else '—'),
        ('Macca u3geJIu9:', f'{tp.product.mass} Kr' if tp.product.mass else '—'),
        ('Bug TexHOJIOrUU:', tp.technology_type.value if hasattr(tp.technology_type, 'value') else str(tp.technology_type or '')),
    ]
    table = doc.add_table(rows=len(fields), cols=2)
    table.style = 'Table Grid'
    for i, (label, value) in enumerate(fields):
        _cell(table.rows[i].cells[0], label, Pt(11), True)
        _cell(table.rows[i].cells[1], str(value), Pt(11))

    for row in table.rows:
        row.cells[0].width = Cm(5.0)
        row.cells[1].width = Cm(11.0)

    doc.add_paragraph('')
    doc.add_paragraph('')

    sigs = doc.add_table(rows=4, cols=3)
    sigs.style = 'Table Grid'
    author = tp.author.full_name if tp.author else '___________'
    ds = datetime.now().strftime('%d.%m.%Y')
    sig_data = [
        ('Pa3pa6oTaJI:', author, ds),
        ('IIpoBepuJI:', '___________', ''),
        ('HopMupoBaJI:', '___________', ''),
        ('YTBepguJI:', '___________', ''),
    ]
    for i, (role, name, date) in enumerate(sig_data):
        _cell(sigs.rows[i].cells[0], role, Pt(10), True)
        _cell(sigs.rows[i].cells[1], name, Pt(10))
        _cell(sigs.rows[i].cells[2], date, Pt(10))
    for row in sigs.rows:
        row.cells[0].width = Cm(4.0)
        row.cells[1].width = Cm(8.0)
        row.cells[2].width = Cm(4.0)

    return doc


# ═══════ Other documents ═══════

def build_material_spec_docx(tp):
    doc = Document()
    gost_page_setup(doc, landscape=True)
    _doc_title(doc, 'BEDOMOCTb MATEPUAJIOB', 'GOCT 3.1123-84  OopMa 1')
    _doc_info(doc, tp)

    norms = tp.material_norms or []
    n = max(len(norms), 1)
    table = doc.add_table(rows=1 + n, cols=7)
    table.style = 'Table Grid'
    for i, h in enumerate(['IIo3.', 'HauMeHoBaHue', 'MapKa/GOCT', 'HopMa, Kr', 'OTxogbl, %', 'CTouM./geT.', 'KUM']):
        _cell(table.rows[0].cells[i], h, Pt(7), True)
        _shade(table.rows[0].cells[i], 'D9D9D9')

    for ri, mn in enumerate(norms, start=1):
        row = table.rows[ri]
        _cell(row.cells[0], str(ri), Pt(7))
        mat = mn.material.name if hasattr(mn, 'material') and mn.material else ''
        _cell(row.cells[1], mat, Pt(7))
        grade = f'{mn.material.grade or ""} {mn.material.gost or ""}' if hasattr(mn, 'material') and mn.material else ''
        _cell(row.cells[2], grade.strip(), Pt(7))
        _cell(row.cells[3], _fmt(mn.norm_per_piece), Pt(7))
        _cell(row.cells[4], str(mn.waste_percent or 0), Pt(7))
        _cell(row.cells[5], _fmt(mn.cost_per_piece), Pt(7))
        kim = 1.0 - (mn.waste_percent or 0) / 100.0
        _cell(row.cells[6], str(round(kim, 3)), Pt(7))

    doc.add_paragraph('')
    add_gost_stamp(doc, tp)
    return doc


def build_tooling_list_docx(tp):
    doc = Document()
    gost_page_setup(doc, landscape=True)
    _doc_title(doc, 'BEDOMOCTb OCHACTKU', 'GOCT 3.1122-84  OopMa 2')
    _doc_info(doc, tp)

    items = []
    for op in sorted(tp.operations, key=lambda o: (o.sort_order or 0)):
        for ot in (op.tools or []):
            tool = ot.tool
            items.append((op.number or '', tool.name if tool else '', tool.designation if tool else '', ot.quantity or 1, tool.tool_type if tool else ''))

    n = max(len(items), 1)
    table = doc.add_table(rows=1 + n, cols=6)
    table.style = 'Table Grid'
    for i, h in enumerate(['On.', 'HauMeHoBaHue', 'O6o3Ha4eHue', 'KoJI.', 'Tun', 'IIpuMe4aHue']):
        _cell(table.rows[0].cells[i], h, Pt(7), True)
        _shade(table.rows[0].cells[i], 'D9D9D9')

    for ri, (op_num, name, des, qty, ttype) in enumerate(items, start=1):
        row = table.rows[ri]
        _cell(row.cells[0], op_num, Pt(7))
        _cell(row.cells[1], name, Pt(7))
        _cell(row.cells[2], des, Pt(7))
        _cell(row.cells[3], str(qty), Pt(7))
        _cell(row.cells[4], ttype, Pt(7))
        _cell(row.cells[5], '', Pt(7))

    doc.add_paragraph('')
    add_gost_stamp(doc, tp)
    return doc


def build_sketch_card_docx(tp):
    doc = Document()
    gost_page_setup(doc, landscape=True)
    _doc_title(doc, 'KAPTA 3CKU3OB', 'GOCT 3.1105-84  OopMa 7')
    _doc_info(doc, tp)

    items = []
    for op in sorted(tp.operations, key=lambda o: (o.sort_order or 0)):
        sketches = [sk for sk in (op.sketches or []) if not getattr(sk, 'is_deleted', False)]
        if sketches:
            for sk in sketches:
                items.append((op.number or '', sk.original_filename or sk.stored_path or '', sk.file_type or '', sk.title or '', sk.created_at.strftime('%Y-%m-%d') if sk.created_at else ''))
        else:
            items.append((op.number or '', '—', '', '', ''))

    n = max(len(items), 1)
    table = doc.add_table(rows=1 + n, cols=5)
    table.style = 'Table Grid'
    for i, h in enumerate(['On.', ' 3cKu3 (oauJI)', 'Tun', 'IIogIIucb', 'DaTa']):
        _cell(table.rows[0].cells[i], h, Pt(7), True)
        _shade(table.rows[0].cells[i], 'D9D9D9')

    for ri, (op_num, fname, ftype, title, date) in enumerate(items, start=1):
        row = table.rows[ri]
        _cell(row.cells[0], op_num, Pt(7))
        _cell(row.cells[1], fname, Pt(7))
        _cell(row.cells[2], ftype, Pt(7))
        _cell(row.cells[3], title, Pt(7))
        _cell(row.cells[4], date, Pt(7))

    doc.add_paragraph('')
    add_gost_stamp(doc, tp)
    return doc


def build_control_card_docx(tp):
    doc = Document()
    gost_page_setup(doc, landscape=True)
    _doc_title(doc, 'KOHTPOJIbHAR KAPTA', 'GOCT 3.1502-85  OopMa 2')
    _doc_info(doc, tp)

    items = []
    item_no = 0
    for op in sorted(tp.operations, key=lambda o: (o.sort_order or 0)):
        for tr in op.transitions:
            if getattr(tr, 'is_deleted', False):
                continue
            item_no += 1
            params = []
            if tr.diameter: params.append(f'D={tr.diameter}')
            if tr.length: params.append(f'L={tr.length}')
            if tr.depth: params.append(f't={tr.depth}')
            items.append((str(item_no), ', '.join(params) if params else (tr.text or ''), 'LLITaHreHlIupKyJIb', 'IIo 4epTexy', '100%', 'KoHTpoJIep OTK'))

    n = max(len(items), 1)
    table = doc.add_table(rows=1 + n, cols=6)
    table.style = 'Table Grid'
    for i, h in enumerate(['Ne', 'KoHTpoJIupyeMblu IIapaMeTp', 'CpegCTBO u3MepeHu9', 'DonycK', 'IIepuogu4HocTb', 'UCIIOJIHUTeJIb']):
        _cell(table.rows[0].cells[i], h, Pt(7), True)
        _shade(table.rows[0].cells[i], 'D9D9D9')

    for ri, row_data in enumerate(items, start=1):
        row = table.rows[ri]
        for ci, val in enumerate(row_data):
            _cell(row.cells[ci], val, Pt(7))

    doc.add_paragraph('')
    add_gost_stamp(doc, tp)
    return doc


# ═══════ Helpers ═══════

def _cell(cell, text, size=None, bold=False):
    """Set cell text with formatting. Returns the cell for chaining."""
    text = str(text) if text else ''
    p = cell.paragraphs[0]
    p.clear()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    if size:
        run.font.size = size
    run.font.bold = bold
    run.font.name = 'Times New Roman'
    return cell


def _shade(cell, color):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def _fmt(v):
    if v is None or v == 0:
        return ''
    return f'{float(v):.2f}'


def _doc_title(doc, title_text, gost_text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(title_text)
    r.font.size = Pt(14)
    r.font.bold = True
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(gost_text).font.size = Pt(9)


def _doc_info(doc, tp):
    p = doc.add_paragraph()
    p.add_run(f'O6o3Ha4eHue: {tp.product.designation}     ').font.size = Pt(9)
    p.add_run(f'U3geJIue: {tp.product.name}     ').font.size = Pt(9)
    p.add_run(f'TII No: {tp.number}').font.size = Pt(9)
    doc.add_paragraph('')
