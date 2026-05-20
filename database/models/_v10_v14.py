"""Auto-generated sub-module."""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship

from database.models._core import Base

# ==================== v10: WEB — REFRESH TOKENS ====================

class RefreshToken(Base):
    """JWT refresh token для веб-клиента."""
    __tablename__ = 'refresh_tokens'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'),
                     nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship('User', foreign_keys=[user_id])


# ==================== v14: PDO — ПРОИЗВОДСТВЕННЫЕ ЗАКАЗЫ ====================


class PDOStatus(enum.Enum):
    """Статусы заказа ПДО — реальный процесс УЗГА."""
    NEW = "Новый"
    OMTS_REVIEW = "ОМТС: проработка"
    TECH_DEPT = "Тех.отдел: проверка"
    FEASIBLE = "Возможно изготовить"
    NOT_FEASIBLE = "Невозможно изготовить"
    DEPUTY_APPROVAL = "Зам.Тех.Дир: утверждение"
    APPROVED = "Утверждён"
    WITH_TECHNOLOGIST = "У технолога"
    MTP_SIGNED = "МТП подписан"
    READY_FOR_SHOP = "Готов к передаче в цех"
    IN_SHOP = "В цехе"
    QC = "ОТК"
    CLOSED = "Закрыт"
    CANCELLED = "Отменён"


class ProductionOrder(Base):
    """Заказ на производство — единица планирования ПДО."""
    __tablename__ = 'production_orders'

    id = Column(Integer, primary_key=True)
    number = Column(String(40), unique=True, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    tech_process_id = Column(Integer, ForeignKey('tech_processes.id'),
                              nullable=True)

    qty = Column(Integer, nullable=False, default=1)
    due_date = Column(Date, nullable=True)
    priority = Column(Integer, default=3)

    customer = Column(String(200))
    customer_order_no = Column(String(80))

    # v14: реальный процесс УЗГА
    aircraft_type = Column(String(80))
    work_scope = Column(Text)

    status = Column(SQLEnum(PDOStatus), default=PDOStatus.NEW,
                     nullable=False, index=True)

    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.now)

    technologist_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    tp_required = Column(Boolean, default=False)
    mtp_signed_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    mtp_signed_at = Column(DateTime, nullable=True)

    omts_memo_no = Column(String(40))
    deputy_memo_no = Column(String(40))

    released_to_shop = Column(String(100))
    released_at = Column(DateTime, nullable=True)
    released_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    qty_done = Column(Integer, default=0)
    qty_scrap = Column(Integer, default=0)
    closed_at = Column(DateTime, nullable=True)

    work_order_id = Column(Integer, ForeignKey('work_orders.id'),
                            nullable=True)

    notes = Column(Text)

    product = relationship("Product", foreign_keys=[product_id])
    tech_process = relationship("TechProcess",
                                 foreign_keys=[tech_process_id])
    creator = relationship("User", foreign_keys=[created_by])
    technologist = relationship("User", foreign_keys=[technologist_id])
    mtp_signer = relationship("User", foreign_keys=[mtp_signed_by])
    releaser = relationship("User", foreign_keys=[released_by])
    work_order = relationship("WorkOrder", foreign_keys=[work_order_id])


class PDOHandoff(Base):
    """Акт приёма-передачи между отделами."""
    __tablename__ = 'pdo_handoffs'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('production_orders.id'),
                       nullable=False, index=True)
    from_dept = Column(String(60), nullable=False)
    to_dept = Column(String(60), nullable=False)
    doc_package = Column(Text)

    transferred_by = Column(Integer, ForeignKey('users.id'))
    accepted_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    status = Column(String(30), default='Передан')
    comment = Column(String(500))
    created_at = Column(DateTime, default=datetime.now)
    accepted_at = Column(DateTime, nullable=True)

    order = relationship("ProductionOrder", foreign_keys=[order_id])


class MTPSignoff(Base):
    """Подпись технолога под МТП."""
    __tablename__ = 'mtp_signoffs'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('production_orders.id'),
                       nullable=False, index=True)
    tech_process_id = Column(Integer, ForeignKey('tech_processes.id'),
                              nullable=False)
    signed_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    signed_at = Column(DateTime, default=datetime.now)
    comment = Column(String(500))

    order = relationship("ProductionOrder", foreign_keys=[order_id])
    tech_process = relationship("TechProcess",
                                 foreign_keys=[tech_process_id])
    signer = relationship("User", foreign_keys=[signed_by])


class NomenclatureItem(Base):
    """Позиция номенклатуры к изготовлению в заказе ПДО.

    Каждая позиция — отдельная деталь/сборка. Тех.отдел по каждой
    позиции проверяет КД, материал и возможность изготовления.
    """
    __tablename__ = 'pdo_nomenclature'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('production_orders.id'),
                       nullable=False, index=True)
    designation = Column(String(100), nullable=False)
    name = Column(String(200))
    qty = Column(Integer, nullable=False, default=1)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)

    # Тех.отдел
    kd_ready = Column(Boolean, default=False)
    material_name = Column(String(200))
    tech_feasible = Column(Boolean, nullable=True)  # None=не проверено
    tech_notes = Column(Text)

    # ОМТС
    material_batch_id = Column(Integer, ForeignKey('material_batches.id'),
                                nullable=True)
    material_ordered = Column(Boolean, default=False)

    sort_order = Column(Integer, default=0)

    order = relationship("ProductionOrder", foreign_keys=[order_id])
    product = relationship("Product", foreign_keys=[product_id])


class ServiceMemo(Base):
    """Служебная записка — У (указание) или П (приказ).

    Выпускается ОМТС (проработка) или Зам.Тех.Дир (на изготовление).
    """
    __tablename__ = 'pdo_memos'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('production_orders.id'),
                       nullable=False, index=True)
    memo_type = Column(String(1), nullable=False)  # 'У' или 'П'
    memo_number = Column(String(40))
    from_dept = Column(String(60))
    issued_by = Column(Integer, ForeignKey('users.id'))
    issued_at = Column(DateTime, default=datetime.now)
    content = Column(Text)
    pdf_path = Column(String(500))

    order = relationship("ProductionOrder", foreign_keys=[order_id])


# ==================== v15: APS — SHIFT CALENDARS ====================


class ShiftType(enum.Enum):
    DAY = "Дневная"
    NIGHT = "Ночная"
    WEEKEND = "Выходной"
    HOLIDAY = "Праздник"


class ShiftSlot(Base):
    """Временной слот смены для оборудования."""
    __tablename__ = 'shift_slots'

    id = Column(Integer, primary_key=True)
    equipment_id = Column(Integer, ForeignKey('equipment.id'),
                          nullable=True, index=True)
    workshop = Column(String(100), nullable=True)
    shift_type = Column(SQLEnum(ShiftType), default=ShiftType.DAY,
                        nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Mon..6=Sun
    start_time = Column(String(5), nullable=False, default='08:00')
    end_time = Column(String(5), nullable=False, default='17:00')
    lunch_start = Column(String(5), nullable=True)
    lunch_end = Column(String(5), nullable=True)
    max_hours = Column(Float, default=8.0)
    is_active = Column(Boolean, default=True)

    equipment = relationship("Equipment", foreign_keys=[equipment_id])


class CalendarException(Base):
    """Исключение календаря — выходной, праздник, ремонт."""
    __tablename__ = 'calendar_exceptions'

    id = Column(Integer, primary_key=True)
    equipment_id = Column(Integer, ForeignKey('equipment.id'),
                          nullable=True, index=True)
    exception_date = Column(Date, nullable=False)
    reason = Column(String(200))
    is_working = Column(Boolean, default=False)
    start_time = Column(String(5), nullable=True)
    end_time = Column(String(5), nullable=True)

    equipment = relationship("Equipment", foreign_keys=[equipment_id])


class SetupMatrix(Base):
    """Матрица времени переналадок между типами изделий."""
    __tablename__ = 'setup_matrix'

    id = Column(Integer, primary_key=True)
    equipment_id = Column(Integer, ForeignKey('equipment.id'),
                          nullable=True, index=True)
    from_group = Column(String(100), nullable=False)
    to_group = Column(String(100), nullable=False)
    setup_minutes = Column(Float, default=15.0)

    equipment = relationship("Equipment", foreign_keys=[equipment_id])

    __table_args__ = (
        UniqueConstraint('equipment_id', 'from_group', 'to_group',
                         name='uq_setup_matrix'),
    )
