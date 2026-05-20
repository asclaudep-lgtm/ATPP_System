"""
Document form registry — equivalent of SprutTP blankmd5.ini.

Each form is a named entry with GOST standard reference, supported
output formats, and a generator function. The registry is the single
source of truth for all document types available in the system.

Architecture modelled after SprutTP:
  blankmd5.ini  →  DOC_FORM_REGISTRY (this file)
  .sbk/.dog     →  Generator functions in doc_generator.py / report_generator.py
  dox3.dll      →  python-docx / openpyxl / reportlab
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class DocCategory(Enum):
    ROUTE = "route"         # Маршрутные карты
    OPERATION = "operation"  # Операционные карты
    TITLE = "title"          # Титульные листы
    MATERIAL = "material"    # Ведомости материалов
    TOOLING = "tooling"      # Ведомости оснастки
    SKETCH = "sketch"        # Карты эскизов
    CONTROL = "control"      # Контрольные карты
    REPORT = "report"        # Ведомости и отчёты
    PACK = "pack"            # Комплекты


@dataclass
class DocForm:
    """A document form definition (like one entry in SprutTP blankmd5.ini)."""
    form_id: str                          # e.g. "MK_3.1118-82_f1"
    name: str                             # Display name
    gost: str                             # GOST standard reference
    category: DocCategory                 # Form category
    formats: List[str] = field(default_factory=lambda: ["xlsx"])
    description: str = ""
    generator: Optional[Callable] = None  # Called as gen(session, tp_id, fmt) -> Path


# ═══════════════════════════════════════════════════════════════
# Registry — all available document forms
# ═══════════════════════════════════════════════════════════════

DOC_FORM_REGISTRY: List[DocForm] = []


def _reg(
    form_id: str, name: str, gost: str, category: DocCategory,
    formats: list = None, description: str = "",
) -> DocForm:
    """Register a document form."""
    f = DocForm(
        form_id=form_id, name=name, gost=gost, category=category,
        formats=formats or ["xlsx"], description=description,
    )
    DOC_FORM_REGISTRY.append(f)
    return f


def register_all():
    """Populate the registry with all available forms.

    Called once at module import. Generator functions are resolved
    lazily when the form is generated (to avoid circular imports).
    """
    DOC_FORM_REGISTRY.clear()

    # ── Маршрутные карты ──
    _reg("MK_3.1118-82_f1", "Маршрутная карта (МК)",
         "ГОСТ 3.1118-82 форма 1", DocCategory.ROUTE,
         ["xlsx", "docx", "pdf"],
         "Основной документ ТП. Содержит перечень операций с оборудованием и нормами.")

    _reg("MSK", "Маршрутно-сопроводительная карта (МСК)",
         "ГОСТ 3.1118-82 (сопроводительная)", DocCategory.ROUTE,
         ["xlsx"],
         "Сопроводительная карта для цеховой логистики. Содержит отметки ОТК.")

    _reg("MTP", "Маршрутно-технологический паспорт (МТП)",
         "Шаблон УЗГА", DocCategory.ROUTE,
         ["xlsx"],
         "Паспорт по шаблону УЗГА. Маршрут + эскизы + материалы + комплектующие.")

    # ── Операционные карты ──
    _reg("OK_3.1404-86_f3", "Операционная карта (ОК)",
         "ГОСТ 3.1404-86 форма 3", DocCategory.OPERATION,
         ["xlsx", "docx", "pdf"],
         "Карта на каждую операцию. Содержит переходы с режимами резания.")

    # ── Титульные листы ──
    _reg("TITUL_3.1105-84_f1", "Титульный лист ТП",
         "ГОСТ 3.1105-84 форма 1", DocCategory.TITLE,
         ["xlsx", "docx", "pdf"],
         "Титульный лист комплекта технологической документации.")

    # ── Ведомости материалов ──
    _reg("VM_3.1123-84_f1", "Ведомость материалов (ВМ)",
         "ГОСТ 3.1123-84 форма 1", DocCategory.MATERIAL,
         ["xlsx", "docx"],
         "Нормы расхода материалов на изделие с КИМ.")

    # ── Ведомости оснастки ──
    _reg("VO_3.1122-84_f2", "Ведомость оснастки (ВО)",
         "ГОСТ 3.1122-84 форма 2", DocCategory.TOOLING,
         ["xlsx", "docx"],
         "Перечень инструмента и оснастки по операциям.")

    # ── Карты эскизов ──
    _reg("KE_3.1105-84_f7", "Карта эскизов (КЭ)",
         "ГОСТ 3.1105-84 форма 7", DocCategory.SKETCH,
         ["xlsx", "docx"],
         "Сводная карта эскизов по операциям и переходам.")

    # ── Контрольные карты ──
    _reg("KK_3.1502-85_f2", "Контрольная карта (КК)",
         "ГОСТ 3.1502-85 форма 2", DocCategory.CONTROL,
         ["xlsx", "docx"],
         "Перечень контролируемых параметров со средствами измерения.")

    # ── Ведомости и отчёты ──
    _reg("VNV", "Ведомость норм времени (ВНВ)",
         "Ведомость УЗГА", DocCategory.REPORT,
         ["xlsx"],
         "Сводная ведомость норм времени по операциям на партию.")

    _reg("KALK", "Калькуляция себестоимости",
         "Калькуляция УЗГА", DocCategory.REPORT,
         ["xlsx"],
         "Расчёт себестоимости изготовления: материалы, зарплата, накладные.")

    # ── Комплект ──
    _reg("PACK", "Полный комплект документов (ZIP)",
         "Комплект ТД", DocCategory.PACK,
         ["xlsx"],
         "ZIP-архив: титульный лист + МК + ОК + ВО + ВМ + КЭ + КК.")

    return DOC_FORM_REGISTRY


# ═══════════════════════════════════════════════════════════════
# Generator resolver — connects forms to their generator functions
# ═══════════════════════════════════════════════════════════════

def generate_form(session, form_id: str, tp_id: int, fmt: str = "xlsx",
                  **kwargs):
    """Generate a document form by its form_id.

    Returns:
        Path to the generated file, or list of Paths for multi-file forms.
    """
    from modules.doc_generator import DocumentGenerator
    from modules.report_generator import ReportGenerator

    gen = DocumentGenerator(session)
    rgen = ReportGenerator(session)

    dispatch = {
        # Route cards
        "MK_3.1118-82_f1": lambda: gen.generate_route_card(tp_id, fmt),
        "MSK": lambda: rgen.generate_route_map(tp_id, kwargs.get('quantity', 1)),
        "MTP": lambda: rgen.generate_mtp(
            tp_id,
            project_name=kwargs.get('project_name', ''),
            kit_number=kwargs.get('kit_number', ''),
            order_number=kwargs.get('order_number', ''),
        ),
        # Operation cards
        "OK_3.1404-86_f3": lambda: gen.generate_all_operation_cards(tp_id, fmt),
        # Title
        "TITUL_3.1105-84_f1": lambda: gen.generate_title_page(tp_id, fmt),
        # Material
        "VM_3.1123-84_f1": lambda: gen.generate_material_specification(tp_id, fmt),
        # Tooling
        "VO_3.1122-84_f2": lambda: gen.generate_tooling_list(tp_id, fmt),
        # Sketch
        "KE_3.1105-84_f7": lambda: gen.generate_sketch_card(tp_id, fmt),
        # Control
        "KK_3.1502-85_f2": lambda: gen.generate_control_card(tp_id, fmt),
        # Reports
        "VNV": lambda: rgen.generate_time_norms(tp_id, kwargs.get('quantity', 1)),
        "KALK": lambda: rgen.generate_cost_report(tp_id),
        # Pack
        "PACK": lambda: gen.generate_document_pack(tp_id),
    }

    generator = dispatch.get(form_id)
    if generator is None:
        raise ValueError(f"Unknown form_id: {form_id}")
    return generator()


# ═══════════════════════════════════════════════════════════════
# Initialize registry on import
# ═══════════════════════════════════════════════════════════════

register_all()
