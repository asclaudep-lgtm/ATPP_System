"""Auto-generated sub-module."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Date,
    ForeignKey, Boolean, Enum as SQLEnum, UniqueConstraint, Index, JSON,
)
from sqlalchemy.orm import relationship
import enum
from database.models._core import Base

# ==================== ПРОИЗВОДСТВО (MES-lite) ====================

class WorkOrderStatus(enum.Enum):
    """Статусы наряда (производственного задания)."""
    RELEASED = "Передан в производство"
    REGISTERED = "Зарегистрирован"
    IN_PROGRESS = "В работе"
    ON_HOLD = "Приостановлен"
    DONE = "Завершён"
    CANCELED = "Отменён"


class WorkOrderItemStatus(enum.Enum):
    """Статусы партии."""
    WAITING = "Ожидает"
    IN_PROGRESS = "В работе"
    MOVED = "Передана дальше"
    DONE = "Готова"
    SCRAP = "Брак"


class RouteStepStatus(enum.Enum):
    """Статусы маршрутной точки."""
    PENDING = "Ожидает"
    IN_PROGRESS = "Выполняется"
    DONE = "Выполнена"
    REWORK = "Доработка"
    SKIPPED = "Пропущена"


class IssueKind(enum.Enum):
    """Тип проблемы в производстве."""
    NO_MATERIAL = "Нет материала"
    NO_TOOL = "Нет инструмента"
    KD_QUESTION = "Вопрос по КД"
    EQUIPMENT = "Проблема с оборудованием"
    QC = "Вопрос ОТК"
    OTHER = "Прочее"


class IssueSeverity(enum.Enum):
    """Серьёзность проблемы."""
    LOW = "Низкая"
    MEDIUM = "Средняя"
    HIGH = "Высокая"
    BLOCKER = "Блокирующая"


class IssueStatus(enum.Enum):
    """Статус обработки проблемы."""
    OPEN = "Открыта"
    ACKNOWLEDGED = "Принята"
    RESOLVED = "Решена"
    CANCELED = "Отменена"


class Workshop(Base):
    """Производственный участок (цех / мастер)."""
    __tablename__ = 'workshops'

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    master_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    notes = Column(Text)

    master = relationship('User', foreign_keys=[master_user_id])


class WorkOrder(Base):
    """Наряд / производственное задание."""
    __tablename__ = 'work_orders'

    id = Column(Integer, primary_key=True)
    number = Column(String(30), unique=True, nullable=False)

    # v7: один штрих-код на МТП. Печатается в шапке маршрутного листа.
    # nullable=True, потому что миграция со старых нарядов без кода
    # генерирует код при первом обращении.
    barcode = Column(String(40), unique=True, nullable=True)

    tech_process_id = Column(Integer, ForeignKey('tech_processes.id'),
                             nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)

    qty_total = Column(Integer, nullable=False, default=1)
    qty_done = Column(Integer, default=0)
    qty_scrap = Column(Integer, default=0)

    customer_order = Column(String(100))
    priority = Column(Integer, default=0)
    due_date = Column(Date)

    status = Column(SQLEnum(WorkOrderStatus),
                    default=WorkOrderStatus.RELEASED, nullable=False)

    created_at = Column(DateTime, default=datetime.now)
    released_by = Column(Integer, ForeignKey('users.id'))
    released_at = Column(DateTime, default=datetime.now)
    registered_by = Column(Integer, ForeignKey('users.id'))
    registered_at = Column(DateTime)
    closed_at = Column(DateTime)

    notes = Column(Text)

    # v8: Soft delete (Корзина для нарядов).
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime)
    deleted_by = Column(Integer, ForeignKey('users.id'))

    tech_process = relationship('TechProcess', foreign_keys=[tech_process_id])
    product = relationship('Product', foreign_keys=[product_id])
    released_by_user = relationship('User', foreign_keys=[released_by])
    registered_by_user = relationship('User', foreign_keys=[registered_by])
    items = relationship('WorkOrderItem', back_populates='work_order',
                         cascade='all, delete-orphan',
                         order_by='WorkOrderItem.id')
    issues = relationship('ProductionIssue', back_populates='work_order',
                          cascade='all, delete-orphan')


class WorkOrderItem(Base):
    """Партия в составе наряда (одна или несколько)."""
    __tablename__ = 'work_order_items'

    id = Column(Integer, primary_key=True)
    work_order_id = Column(Integer, ForeignKey('work_orders.id'),
                           nullable=False)

    barcode = Column(String(40), unique=True, nullable=False)
    serial = Column(String(40), nullable=False)

    qty = Column(Integer, nullable=False, default=1)
    qty_good = Column(Integer, default=0)
    qty_scrap = Column(Integer, default=0)

    current_workshop_id = Column(Integer, ForeignKey('workshops.id'),
                                 nullable=True)
    current_operation_id = Column(Integer, ForeignKey('operations.id'),
                                  nullable=True)

    status = Column(SQLEnum(WorkOrderItemStatus),
                    default=WorkOrderItemStatus.WAITING, nullable=False)

    # Optimistic lock — защищает от одновременных перемещений с разных ПК.
    version = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __mapper_args__ = {
        'version_id_col': version,
    }

    work_order = relationship('WorkOrder', back_populates='items')
    current_workshop = relationship('Workshop',
                                    foreign_keys=[current_workshop_id])
    current_operation = relationship('Operation',
                                     foreign_keys=[current_operation_id])
    route_steps = relationship('RouteStep', back_populates='item',
                               cascade='all, delete-orphan',
                               order_by='RouteStep.seq')


class RouteStep(Base):
    """Шаг маршрута (одна операция для одной партии)."""
    __tablename__ = 'route_steps'

    id = Column(Integer, primary_key=True)
    work_order_item_id = Column(Integer, ForeignKey('work_order_items.id'),
                                nullable=False)
    operation_id = Column(Integer, ForeignKey('operations.id'),
                          nullable=False)
    workshop_id = Column(Integer, ForeignKey('workshops.id'), nullable=True)

    seq = Column(Integer, nullable=False)

    status = Column(SQLEnum(RouteStepStatus),
                    default=RouteStepStatus.PENDING, nullable=False)

    started_at = Column(DateTime)
    finished_at = Column(DateTime)

    worker_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    qty_good = Column(Integer, default=0)
    qty_scrap = Column(Integer, default=0)
    note = Column(Text)

    item = relationship('WorkOrderItem', back_populates='route_steps')
    operation = relationship('Operation', foreign_keys=[operation_id])
    workshop = relationship('Workshop', foreign_keys=[workshop_id])
    worker = relationship('User', foreign_keys=[worker_user_id])


class ProductionEvent(Base):
    """Универсальный журнал событий производства."""
    __tablename__ = 'production_events'

    id = Column(Integer, primary_key=True)
    at = Column(DateTime, default=datetime.now, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)

    work_order_id = Column(Integer, ForeignKey('work_orders.id'),
                           nullable=True, index=True)
    work_order_item_id = Column(Integer, ForeignKey('work_order_items.id'),
                                nullable=True, index=True)
    workshop_id = Column(Integer, ForeignKey('workshops.id'), nullable=True)
    operation_id = Column(Integer, ForeignKey('operations.id'), nullable=True)

    event_type = Column(String(40), nullable=False, index=True)
    payload = Column(JSON)  # произвольный JSON

    user = relationship('User', foreign_keys=[user_id])
    work_order = relationship('WorkOrder', foreign_keys=[work_order_id])
    work_order_item = relationship('WorkOrderItem',
                                   foreign_keys=[work_order_item_id])
    workshop = relationship('Workshop', foreign_keys=[workshop_id])
    operation = relationship('Operation', foreign_keys=[operation_id])


class ProductionIssue(Base):
    """Проблема, поднятая мастером в производстве."""
    __tablename__ = 'production_issues'

    id = Column(Integer, primary_key=True)
    kind = Column(SQLEnum(IssueKind), nullable=False)
    severity = Column(SQLEnum(IssueSeverity),
                      default=IssueSeverity.MEDIUM, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)

    work_order_id = Column(Integer, ForeignKey('work_orders.id'),
                           nullable=False)
    work_order_item_id = Column(Integer, ForeignKey('work_order_items.id'),
                                nullable=True)
    workshop_id = Column(Integer, ForeignKey('workshops.id'), nullable=True)
    operation_id = Column(Integer, ForeignKey('operations.id'), nullable=True)

    status = Column(SQLEnum(IssueStatus),
                    default=IssueStatus.OPEN, nullable=False)

    opened_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    opened_at = Column(DateTime, default=datetime.now)
    assignee_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    resolved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    resolved_at = Column(DateTime)
    resolution = Column(Text)

    blocks_production = Column(Boolean, default=False)

    work_order = relationship('WorkOrder', back_populates='issues')
    work_order_item = relationship('WorkOrderItem',
                                   foreign_keys=[work_order_item_id])
    workshop = relationship('Workshop', foreign_keys=[workshop_id])
    operation = relationship('Operation', foreign_keys=[operation_id])
    opened_by_user = relationship('User', foreign_keys=[opened_by])
    assignee = relationship('User', foreign_keys=[assignee_id])
    resolved_by_user = relationship('User', foreign_keys=[resolved_by])


class IssuePhoto(Base):
    """Фотография, прикреплённая к проблеме (A5).

    Файл хранится локально в ``data/issues/<issue_id>/<uuid>.<ext>``,
    бэкап автоматически подбирает каталог ``data/``.
    """
    __tablename__ = 'issue_photos'

    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, ForeignKey('production_issues.id'),
                      nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    caption = Column(String(255))
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.now)

    issue = relationship('ProductionIssue', backref='photos',
                         foreign_keys=[issue_id])
    uploader = relationship('User', foreign_keys=[uploaded_by])


class Notification(Base):
    """In-app уведомление пользователю (A6).

    Тип ``kind`` — текстовая метка, например ``ISSUE_ASSIGNED``,
    ``ISSUE_RESOLVED``. Поле ``related_issue_id`` опционально связывает
    уведомление с конкретной проблемой, чтобы можно было перейти к ней
    одним кликом.
    """
    __tablename__ = 'notifications'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'),
                     nullable=False, index=True)
    kind = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text)
    related_issue_id = Column(Integer, ForeignKey('production_issues.id'),
                              nullable=True)
    related_work_order_id = Column(Integer, ForeignKey('work_orders.id'),
                                   nullable=True)
    created_at = Column(DateTime, default=datetime.now, index=True)
    read_at = Column(DateTime, nullable=True)

    user = relationship('User', foreign_keys=[user_id])
    issue = relationship('ProductionIssue', foreign_keys=[related_issue_id])


class UserSession(Base):
    """Лог входов/выходов пользователей (C13).

    Запись создаётся при успешной аутентификации; при выходе из приложения
    или закрытии главного окна — обновляется ``ended_at``. Это
    отдельный лог от audit-журнала.
    """
    __tablename__ = 'user_sessions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'),
                     nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.now, index=True)
    ended_at = Column(DateTime, nullable=True)
    ip_address = Column(String(64), nullable=True)
    hostname = Column(String(120), nullable=True)
    app_version = Column(String(40), nullable=True)

    user = relationship('User', foreign_keys=[user_id])


class UserBookmark(Base):
    """«Недавно открытые» / «Избранное» (D18).

    ``target_type`` — например ``'tech_process'``, ``'product'``,
    ``'work_order'``. ``target_id`` — id соответствующей записи.
    Уникальная пара (user, target_type, target_id) — каждый объект
    встречается у пользователя один раз.
    """
    __tablename__ = 'user_bookmarks'
    __table_args__ = (
        UniqueConstraint('user_id', 'target_type', 'target_id',
                         name='uq_user_bookmark'),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'),
                     nullable=False, index=True)
    target_type = Column(String(40), nullable=False)
    target_id = Column(Integer, nullable=False)
    title = Column(String(255))
    is_favorite = Column(Boolean, default=False)
    last_opened_at = Column(DateTime, default=datetime.now, index=True)
    open_count = Column(Integer, default=1)

    user = relationship('User', foreign_keys=[user_id])


