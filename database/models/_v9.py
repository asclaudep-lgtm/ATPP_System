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

# ==================== v9: БРАК-ЖУРНАЛ ====================

class ScrapReason(enum.Enum):
    """Причина брака."""
    MATERIAL = "Дефект материала"
    OPERATOR = "Ошибка оператора"
    EQUIPMENT = "Неисправность оборудования"
    TOOL = "Износ/поломка инструмента"
    DRAWING = "Ошибка в КД"
    SETUP = "Ошибка наладки"
    OTHER = "Прочее"


class ScrapDecision(enum.Enum):
    """Решение ОТК по партии с браком."""
    PENDING = "На рассмотрении"
    REWORK = "На доработку"
    SCRAP = "В брак"
    ACCEPT_AS_IS = "Принять как есть"


class ScrapRecord(Base):
    """Запись о браке детали/партии в производстве.

    Дополняет / расширяет ``ProductionIssue`` (для кейса «брак»):
    обязательно привязана к ``RouteStep`` или ``WorkOrderItem`` +
    ``Operation``, фиксирует количество, причину, решение и виновного.
    Фотофиксация — через ``IssuePhoto`` либо собственное хранилище
    ``data/scrap/<id>/`` (см. ``modules/scrap_journal.py``).
    """
    __tablename__ = 'scrap_records'

    id = Column(Integer, primary_key=True)
    work_order_id = Column(Integer, ForeignKey('work_orders.id'),
                           nullable=False, index=True)
    work_order_item_id = Column(Integer, ForeignKey('work_order_items.id'),
                                nullable=True)
    operation_id = Column(Integer, ForeignKey('operations.id'),
                          nullable=True, index=True)
    route_step_id = Column(Integer, ForeignKey('route_steps.id'),
                           nullable=True)

    qty_scrap = Column(Integer, nullable=False, default=1)
    reason = Column(SQLEnum(ScrapReason),
                    default=ScrapReason.OTHER, nullable=False)
    decision = Column(SQLEnum(ScrapDecision),
                      default=ScrapDecision.PENDING, nullable=False)

    description = Column(Text)  # что произошло
    resolution = Column(Text)   # решение ОТК

    fault_operator_id = Column(Integer, ForeignKey('users.id'),
                               nullable=True)
    reported_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    reported_at = Column(DateTime, default=datetime.now, index=True)
    decided_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    decided_at = Column(DateTime, nullable=True)

    work_order = relationship('WorkOrder', foreign_keys=[work_order_id])
    work_order_item = relationship('WorkOrderItem',
                                   foreign_keys=[work_order_item_id])
    operation = relationship('Operation', foreign_keys=[operation_id])
    fault_operator = relationship('User', foreign_keys=[fault_operator_id])
    reporter = relationship('User', foreign_keys=[reported_by])
    decider = relationship('User', foreign_keys=[decided_by])


class ScrapPhoto(Base):
    """Фотография к записи о браке."""
    __tablename__ = 'scrap_photos'

    id = Column(Integer, primary_key=True)
    scrap_id = Column(Integer, ForeignKey('scrap_records.id'),
                      nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    caption = Column(String(255))
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.now)

    scrap = relationship('ScrapRecord', backref='photos',
                         foreign_keys=[scrap_id])
    uploader = relationship('User', foreign_keys=[uploaded_by])


# ==================== v9: ОСНАСТКА ====================

class ToolingStatus(enum.Enum):
    """Состояние единицы оснастки."""
    AVAILABLE = "Доступна"
    ISSUED = "Выдана"
    REPAIR = "В ремонте"
    WRITE_OFF = "Списана"
    LOST = "Утеряна"


class ToolingItem(Base):
    """Единица оснастки (приспособление / штамп / кондуктор / форма).

    Отличается от ``Tool`` (которая — инструмент, в т.ч. расходник):
    оснастка — это многоразовая дорогая единица, по которой нужен учёт
    выдач/возвратов и износа.
    """
    __tablename__ = 'tooling_items'

    id = Column(Integer, primary_key=True)
    inventory_no = Column(String(40), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    location = Column(String(200))  # склад/полка/шкаф
    status = Column(SQLEnum(ToolingStatus),
                    default=ToolingStatus.AVAILABLE, nullable=False)
    purchase_date = Column(Date, nullable=True)
    cost = Column(Float, nullable=True)
    # Износ (0..100% — субъективная оценка, обновляется при возврате).
    wear_percent = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class OperationTooling(Base):
    """Связь «операция → требуемая оснастка».

    Позволяет сказать: «для операции 015 нужны вот эти оснастки».
    """
    __tablename__ = 'operation_tooling'
    __table_args__ = (
        UniqueConstraint('operation_id', 'tooling_item_id',
                         name='uq_op_tooling'),
    )

    id = Column(Integer, primary_key=True)
    operation_id = Column(Integer, ForeignKey('operations.id'),
                          nullable=False, index=True)
    tooling_item_id = Column(Integer, ForeignKey('tooling_items.id'),
                             nullable=False, index=True)
    notes = Column(String(255))


class ToolingIssue(Base):
    """Запись выдачи / возврата оснастки.

    Незакрытая запись (returned_at IS NULL) — оснастка на руках.
    """
    __tablename__ = 'tooling_issues'

    id = Column(Integer, primary_key=True)
    tooling_item_id = Column(Integer, ForeignKey('tooling_items.id'),
                             nullable=False, index=True)
    work_order_id = Column(Integer, ForeignKey('work_orders.id'),
                           nullable=True)
    operation_id = Column(Integer, ForeignKey('operations.id'),
                          nullable=True)
    issued_to = Column(Integer, ForeignKey('users.id'), nullable=False)
    issued_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    issued_at = Column(DateTime, default=datetime.now, index=True)
    returned_at = Column(DateTime, nullable=True)
    return_wear_percent = Column(Integer, nullable=True)
    notes = Column(Text)

    tooling = relationship('ToolingItem', foreign_keys=[tooling_item_id])
    work_order = relationship('WorkOrder', foreign_keys=[work_order_id])
    operation = relationship('Operation', foreign_keys=[operation_id])
    recipient = relationship('User', foreign_keys=[issued_to])
    issuer = relationship('User', foreign_keys=[issued_by])


# ==================== v9: ТРАССИРУЕМОСТЬ МАТЕРИАЛА ====================

class MaterialBatch(Base):
    """Партия поступления материала.

    Уникальный ``lot_no`` — идентификатор партии у поставщика
    (выгрузка / плавка / рулон), к которой можно прикрепить сертификат.
    """
    __tablename__ = 'material_batches'

    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey('materials.id'),
                         nullable=False, index=True)
    lot_no = Column(String(80), nullable=False, index=True)
    received_date = Column(Date, default=lambda: datetime.now(datetime.UTC))
    supplier = Column(String(200))
    cert_path = Column(String(500))  # путь к pdf-сертификату

    qty_received = Column(Float, nullable=False, default=0)
    qty_reserved = Column(Float, nullable=False, default=0)
    qty_consumed = Column(Float, nullable=False, default=0)
    unit = Column(String(20), default='кг')

    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    material = relationship('Material')


class MaterialReservation(Base):
    """Резерв партии материала под наряд."""
    __tablename__ = 'material_reservations'

    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey('material_batches.id'),
                      nullable=False, index=True)
    work_order_id = Column(Integer, ForeignKey('work_orders.id'),
                           nullable=False, index=True)
    qty = Column(Float, nullable=False)
    reserved_at = Column(DateTime, default=datetime.now)
    reserved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    released_at = Column(DateTime, nullable=True)  # резерв снят
    notes = Column(Text)

    batch = relationship('MaterialBatch', foreign_keys=[batch_id])
    work_order = relationship('WorkOrder', foreign_keys=[work_order_id])


class MaterialIssue(Base):
    """Фактическое списание материала из партии под наряд."""
    __tablename__ = 'material_issues'

    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey('material_batches.id'),
                      nullable=False, index=True)
    work_order_id = Column(Integer, ForeignKey('work_orders.id'),
                           nullable=False, index=True)
    qty = Column(Float, nullable=False)
    issued_at = Column(DateTime, default=datetime.now)
    issued_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    notes = Column(Text)

    batch = relationship('MaterialBatch', foreign_keys=[batch_id])
    work_order = relationship('WorkOrder', foreign_keys=[work_order_id])


# ==================== v9: ECN (Извещения об изменениях) ====================

class ECNStatus(enum.Enum):
    """Статус извещения об изменении."""
    DRAFT = "Черновик"
    UNDER_REVIEW = "На согласовании"
    APPROVED = "Согласовано"
    REJECTED = "Отклонено"
    APPLIED = "Применено"
    CANCELED = "Отменено"


class ECN(Base):
    """Извещение об изменении (Engineering Change Notice).

    Формальный запрос «изменить ТП по ДСЕ XXX потому что Y».
    """
    __tablename__ = 'ecns'

    id = Column(Integer, primary_key=True)
    number = Column(String(40), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    reason = Column(Text, nullable=False)
    proposed_change = Column(Text)

    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    tech_process_id = Column(Integer, ForeignKey('tech_processes.id'),
                             nullable=True)

    status = Column(SQLEnum(ECNStatus),
                    default=ECNStatus.DRAFT, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    closed_at = Column(DateTime, nullable=True)

    product = relationship('Product', foreign_keys=[product_id])
    tech_process = relationship('TechProcess', foreign_keys=[tech_process_id])
    author = relationship('User', foreign_keys=[created_by])


class ECNApproval(Base):
    """Подпись согласующего на ECN."""
    __tablename__ = 'ecn_approvals'

    id = Column(Integer, primary_key=True)
    ecn_id = Column(Integer, ForeignKey('ecns.id'),
                    nullable=False, index=True)
    role = Column(String(50), nullable=False)  # SignerRole.value
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    decision = Column(String(20))  # APPROVED / REJECTED / PENDING
    decided_at = Column(DateTime, nullable=True)
    comment = Column(Text)

    ecn = relationship('ECN', backref='approvals')
    user = relationship('User', foreign_keys=[user_id])


# ==================== v9: МЕТРОЛОГИЯ ====================

class InstrumentStatus(enum.Enum):
    """Статус измерительного прибора."""
    ACTIVE = "В эксплуатации"
    OUT_FOR_CAL = "На поверке"
    EXPIRED = "Просрочена поверка"
    REPAIR = "В ремонте"
    WRITE_OFF = "Списан"


class Instrument(Base):
    """Измерительный прибор / средство измерения.

    Включает СИ (штангенциркули, микрометры), а также калибры,
    индикаторы — всё, что подлежит периодической поверке.
    """
    __tablename__ = 'instruments'

    id = Column(Integer, primary_key=True)
    inventory_no = Column(String(40), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    type = Column(String(80))  # тип СИ
    range_str = Column(String(80))  # диапазон, например "0-150 мм"
    accuracy = Column(String(80))  # класс точности / погрешность
    location = Column(String(200))
    status = Column(SQLEnum(InstrumentStatus),
                    default=InstrumentStatus.ACTIVE, nullable=False)

    last_cal_date = Column(Date, nullable=True)
    next_cal_date = Column(Date, nullable=True, index=True)
    cal_interval_months = Column(Integer, default=12)

    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


class Calibration(Base):
    """Поверка / калибровка инструмента."""
    __tablename__ = 'calibrations'

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey('instruments.id'),
                           nullable=False, index=True)
    performed_at = Column(Date, nullable=False)
    next_due = Column(Date, nullable=True)
    organization = Column(String(200))   # кто поверял
    certificate_no = Column(String(80))
    cert_path = Column(String(500))      # pdf-скан
    result = Column(String(40))          # «годен» / «не годен»
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    instrument = relationship('Instrument', backref='calibrations',
                              foreign_keys=[instrument_id])


# ==================== v10: IOT — ТЕЛЕМЕТРИЯ СТАНКОВ ====================

class MachineStatus(Base):
    """Актуальный статус станка из IoT/MQTT."""
    __tablename__ = 'machine_status'

    id = Column(Integer, primary_key=True)
    equipment_id = Column(Integer, ForeignKey('equipment.id'),
                          nullable=False, index=True)
    status = Column(String(40), nullable=False, default='offline')
    # running / idle / offline / alarm
    program_number = Column(String(80))          # Текущая УП (CNC)
    spindle_speed = Column(Float)                 # об/мин
    feed_rate = Column(Float)                     # мм/мин
    power_consumption = Column(Float)             # kW
    active_operation_id = Column(Integer,
                                  ForeignKey('operations.id'),
                                  nullable=True)
    work_order_item_id = Column(Integer,
                                 ForeignKey('work_order_items.id'),
                                 nullable=True)

    recorded_at = Column(DateTime, default=datetime.now, index=True)
    reported_at = Column(DateTime, nullable=True)       # MQTT publish time
    is_simulated = Column(Boolean, default=False)       # True = from simulator

    equipment = relationship("Equipment", foreign_keys=[equipment_id])
    active_operation = relationship("Operation",
                                     foreign_keys=[active_operation_id])
    work_order_item = relationship("WorkOrderItem",
                                    foreign_keys=[work_order_item_id])


class MachineStatusSummary(Base):
    """Денормализованный latest status на станок (быстрый lookup)."""
    __tablename__ = 'machine_status_summary'

    id = Column(Integer, primary_key=True)
    equipment_id = Column(Integer, ForeignKey('equipment.id'),
                          nullable=False, unique=True, index=True)
    status = Column(String(40), nullable=False, default='offline')
    last_update = Column(DateTime, default=datetime.now)
    uptime_today_min = Column(Float, default=0)

    equipment = relationship("Equipment", foreign_keys=[equipment_id])


