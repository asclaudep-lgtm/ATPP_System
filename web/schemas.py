"""Pydantic-схемы для API."""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str = ""
    password: str = ""
    api_key: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    designation: str
    name: str
    group_id: Optional[int] = None
    material_id: Optional[int] = None
    mass: Optional[float] = None
    dimensions: Optional[str] = None
    accuracy_class: Optional[str] = None
    roughness: Optional[str] = None
    created_at: Optional[datetime] = None


class ProductListOut(BaseModel):
    items: List[ProductOut]
    total: int


class TechProcessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    product_id: int
    status: str
    version: Optional[str] = None
    technology_type: Optional[str] = None
    execution_variant: Optional[str] = None
    created_at: Optional[datetime] = None


class TPListOut(BaseModel):
    items: List[TechProcessOut]
    total: int


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    status: str
    product_id: Optional[int] = None
    qty_total: int
    qty_done: int
    qty_scrap: int
    due_date: Optional[str] = None
    created_at: Optional[datetime] = None


class WOListOut(BaseModel):
    items: List[WorkOrderOut]
    total: int


class ApprovalAction(BaseModel):
    tp_id: int
    action: str  # "approve" / "reject" / "send_for_rework"
    comment: Optional[str] = None


class DashboardStats(BaseModel):
    total_products: int
    total_tech_processes: int
    total_work_orders: int
    active_work_orders: int
    total_users: int
    pdo_total: int = 0
    pdo_active: int = 0
    pdo_overdue: int = 0
