"""Виджеты приложения"""
from .tp_editor import TPEditorWidget
from .material_norms_widget import MaterialNormsWidget
from .cost_calc_widget import CostCalcWidget
from .bom_widget import BOMWidget
from .iot_dashboard_widget import IoTDashboardWidget
from .machine_detail_widget import MachineDetailWidget
from .ai_assistant_panel import AIAssistantPanel
from .bom_graph_widget import BOMGraphWidget
from .nesting_widget import NestingWidget

__all__ = ['TPEditorWidget', 'MaterialNormsWidget', 'CostCalcWidget',
           'BOMWidget', 'IoTDashboardWidget', 'MachineDetailWidget',
           'AIAssistantPanel', 'BOMGraphWidget', 'NestingWidget']
