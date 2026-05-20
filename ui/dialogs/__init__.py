"""Диалоги приложения"""
from .ai_assistant_dialog import AIAssistantDialog
from .bom_item_dialog import BOMItemDialog
from .cad_import_dialog import CadImportDialog
from .cutting_calc_dialog import CuttingCalcDialog
from .doc_dialog import DocGenerateDialog
from .ktd_browser_dialog import KTDBrowserDialog
from .onec_export_dialog import OneCExportDialog
from .onec_import_dialog import OneCImportDialog
from .operation_dialog import OperationDialog
from .product_dialog import ProductDialog
from .references_dialog import ReferencesDialog
from .tp_dialog import TPDialog
from .transition_dialog import TransitionDialog
from .users_dialog import UsersDialog

__all__ = [
    'ProductDialog', 'TPDialog', 'OperationDialog', 'TransitionDialog',
    'ReferencesDialog', 'DocGenerateDialog', 'UsersDialog', 'KTDBrowserDialog',
    'BOMItemDialog', 'OneCImportDialog', 'OneCExportDialog',
    'AIAssistantDialog', 'CadImportDialog', 'CuttingCalcDialog',
]
