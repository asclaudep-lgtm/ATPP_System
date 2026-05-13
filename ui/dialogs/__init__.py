"""Диалоги приложения"""
from .product_dialog import ProductDialog
from .tp_dialog import TPDialog
from .operation_dialog import OperationDialog
from .transition_dialog import TransitionDialog
from .references_dialog import ReferencesDialog
from .doc_dialog import DocGenerateDialog
from .users_dialog import UsersDialog
from .ktd_browser_dialog import KTDBrowserDialog
from .bom_item_dialog import BOMItemDialog
from .onec_import_dialog import OneCImportDialog
from .onec_export_dialog import OneCExportDialog
from .ai_assistant_dialog import AIAssistantDialog
from .cad_import_dialog import CadImportDialog
from .cutting_calc_dialog import CuttingCalcDialog

__all__ = [
    'ProductDialog', 'TPDialog', 'OperationDialog', 'TransitionDialog',
    'ReferencesDialog', 'DocGenerateDialog', 'UsersDialog', 'KTDBrowserDialog',
    'BOMItemDialog', 'OneCImportDialog', 'OneCExportDialog',
    'AIAssistantDialog', 'CadImportDialog', 'CuttingCalcDialog',
]
