"""ATPP database models — domain-split package.

Import style (unchanged):
    from database.models import Product, TechProcess, WorkOrder, ...

Sub-modules:
    _core        — User, Product, TechProcess, Operation, BOM, norms, workflow
    _production  — WorkOrder, RouteStep, ProductionEvent, Issue, Notification
    _v9          — Scrap, Tooling, MaterialTrace, ECN, Metrology, IoT
    _v10_v14     — RefreshToken, ProductionOrder, PDO models
"""

from database.models._core import *
from database.models._production import *
from database.models._v9 import *
from database.models._v10_v14 import *
