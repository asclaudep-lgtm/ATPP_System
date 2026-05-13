"""
Модели базы данных SQLAlchemy
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Date,
    ForeignKey, Boolean, Enum as SQLEnum, UniqueConstraint, Index,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class TPStatus(enum.Enum):
    """Статусы технологического процесса"""
    DRAFT = "Черновик"
    REVIEW = "На согласовании"
    REWORK = "На доработке"
    APPROVED = "Утверждён"
    ARCHIVED = "Архив"


# Утверждённый ТП заблокирован для прямого редактирования.
# Перечисляем здесь чтобы можно было импортировать единым списком.
LOCKED_STATUSES = {TPStatus.APPROVED, TPStatus.ARCHIVED}


# Роли подписантов в workflow утверждения ТП
class SignerRole(enum.Enum):
    AUTHOR = "Разработчик"
    NORMER = "Нормоконтроль"
    CHIEF_TECH = "Гл. технолог"
    QC = "ОТК"
    APPROVER = "Утверждающий"


class TPType(enum.Enum):
    """Типы технологических процессов"""
    SINGLE = "Единичный"
    TYPICAL = "Типовой"
    GROUP = "Групповой"


class TechnologyType(enum.Enum):
    """Виды технологий"""
    MACHINING = "Механическая обработка"
    ASSEMBLY = "Сборка"
    WELDING = "Сварка"
    STAMPING = "Штамповка"
    HEAT_TREATMENT = "Термообработка"
    CASTING = "Литьё"
    COATING = "Покрытия"
    CUTTING = "Резка"
    OTHER = "Другое"


class AssemblyLevel(enum.Enum):
    """Уровень в иерархии БОМ (Bill of Materials)."""
    PRODUCT = "Изделие"             # Top-level finished product
    SUBASSEMBLY = "Сборочная единица"
    DSE = "ДСЕ"                     # Detail assembly unit
    DETAIL = "Деталь"               # Raw part (leaf node)


# ==================== ПОЛЬЗОВАТЕЛИ ====================

class User(Base):
    """Пользователь системы"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    email = Column(String(100))
    role = Column(String(20), default='user')  # admin, technologist, engineer, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime)
    # D15: при первом входе пользователь обязан сменить пароль.
    must_change_password = Column(Boolean, default=False, nullable=False)
    password_changed_at = Column(DateTime, nullable=True)

    # Связи
    products = relationship("Product", back_populates="author",
                            foreign_keys="Product.author_id")
    tech_processes = relationship("TechProcess", back_populates="author",
                                  foreign_keys="TechProcess.author_id")


# ==================== СПРАВОЧНИКИ ====================

class Material(Base):
    """Справочник материалов"""
    __tablename__ = 'materials'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    grade = Column(String(50))  # Марка
    gost = Column(String(50))   # ГОСТ
    density = Column(Float)     # Плотность, кг/м³
    price_per_kg = Column(Float)  # Цена за кг
    description = Column(Text)
    
    # Связи
    products = relationship("Product", back_populates="material")


class Equipment(Base):
    """Справочник оборудования"""
    __tablename__ = 'equipment'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    model = Column(String(50))
    type = Column(String(50))  # Тип оборудования
    power = Column(Float)      # Мощность, кВт
    cost_per_hour = Column(Float)  # Стоимость часа работы
    description = Column(Text)
    
    # Связи
    operations = relationship("Operation", back_populates="equipment")


class Tool(Base):
    """Справочник инструмента"""
    __tablename__ = 'tools'
    
    id = Column(Integer, primary_key=True)
    designation = Column(String(100), nullable=False)
    name = Column(String(200))
    tool_type = Column(String(50))  # Режущий, измерительный, вспомогательный
    description = Column(Text)
    
    # Связи
    operation_tools = relationship("OperationTool", back_populates="tool")


class Profession(Base):
    """Справочник профессий"""
    __tablename__ = 'professions'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    typical_grade = Column(Integer)  # Типовой разряд
    hourly_rates = Column(Text)  # JSON: {1: 200, 2: 220, ...}
    
    # Связи
    operations = relationship("Operation", back_populates="profession")


class OperationTemplate(Base):
    """Справочник типовых операций.

    Используется в «Импорт из шаблона…» — позволяет создать операцию
    с дефолтными полями в один клик.
    """
    __tablename__ = 'operation_templates'
    
    id = Column(Integer, primary_key=True)
    code = Column(String(20))
    name = Column(String(200), nullable=False)
    technology_type = Column(SQLEnum(TechnologyType))
    typical_equipment_id = Column(Integer, ForeignKey('equipment.id'))
    typical_profession_id = Column(Integer, ForeignKey('professions.id'))
    description = Column(Text)
    shop = Column(String(100))
    grade = Column(Integer)
    t_setup = Column(Float, default=0)
    t_piece = Column(Float, default=0)
    usage_count = Column(Integer, default=0)

    equipment = relationship("Equipment")
    profession = relationship("Profession")


class TransitionTemplate(Base):
    """Справочник типовых переходов"""
    __tablename__ = 'transition_templates'
    
    id = Column(Integer, primary_key=True)
    operation_template_id = Column(Integer, ForeignKey('operation_templates.id'))
    code = Column(String(20))
    text = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0)


# ==================== ГРУППЫ ИЗДЕЛИЙ ====================

class ProductGroup(Base):
    """Группа/подгруппа изделий"""
    __tablename__ = 'product_groups'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)       # Название группы, напр. "53-74.80"
    display_name = Column(String(200))               # Отображаемое название
    parent_id = Column(Integer, ForeignKey('product_groups.id'), nullable=True)
    sort_order = Column(Integer, default=0)

    # Самосвязь
    children = relationship("ProductGroup", back_populates="parent",
                            order_by="ProductGroup.sort_order")
    parent = relationship("ProductGroup", back_populates="children",
                          remote_side="ProductGroup.id")
    products = relationship("Product", back_populates="group")


# ==================== ИЗДЕЛИЯ ====================

class Product(Base):
    """Изделие"""
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    designation = Column(String(100), unique=True, nullable=False)  # Обозначение
    name = Column(String(200), nullable=False)  # Наименование
    group_id = Column(Integer, ForeignKey('product_groups.id'), nullable=True)  # Группа
    material_id = Column(Integer, ForeignKey('materials.id'))
    mass = Column(Float)  # Масса, кг
    dimensions = Column(String(100))  # Габариты
    blank_type = Column(String(50))  # Вид заготовки
    blank_dimensions = Column(String(100))  # Размеры заготовки
    material_gost = Column(String(200))    # ГОСТ/ТУ сортамента
    accuracy_class = Column(String(20))  # Класс точности
    roughness = Column(String(20))  # Шероховатость
    quantity_in_assembly = Column(Integer, default=1)
    description = Column(Text)

    author_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # v8: Soft delete (Корзина для деталей).
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime)
    deleted_by = Column(Integer, ForeignKey('users.id'))

    # Связи
    author = relationship(
        "User", back_populates="products", foreign_keys="Product.author_id",
    )
    group = relationship("ProductGroup", back_populates="products")
    material = relationship("Material", back_populates="products")
    tech_processes = relationship("TechProcess", back_populates="product")


# ==================== BOM (МНОГОУРОВНЕВЫЙ СОСТАВ ИЗДЕЛИЯ) ====================

class BOMItem(Base):
    """Элемент состава изделия (Bill of Materials).

    Self-referencing adjacency list: ``parent_id`` = NULL означает
    корневой узел (верхний уровень изделия).  Рекурсивные CTE
    используются для flatten-запросов.
    """
    __tablename__ = 'bom_items'

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('bom_items.id'), nullable=True,
                       index=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False,
                        index=True)

    level = Column(SQLEnum(AssemblyLevel),
                   default=AssemblyLevel.DETAIL, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    position = Column(String(20))          # Позиция в сборке, напр. "поз.1"
    note = Column(Text)

    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Self-referencing
    children = relationship("BOMItem", back_populates="parent",
                            cascade="all, delete-orphan",
                            order_by="BOMItem.sort_order")
    parent = relationship("BOMItem", back_populates="children",
                          remote_side="BOMItem.id")

    # Связь с продуктом
    product = relationship("Product", foreign_keys=[product_id])


# ==================== ТЕХНОЛОГИЧЕСКИЕ ПРОЦЕССЫ ====================

class TechProcess(Base):
    """Технологический процесс"""
    __tablename__ = 'tech_processes'
    
    id = Column(Integer, primary_key=True)
    number = Column(String(50), unique=True, nullable=False)  # Номер ТП
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    
    tp_type = Column(SQLEnum(TPType), default=TPType.SINGLE)
    technology_type = Column(SQLEnum(TechnologyType))
    status = Column(SQLEnum(TPStatus), default=TPStatus.DRAFT)
    
    version = Column(String(20), default="1.0")
    description = Column(Text)

    # Вариант исполнения ТП — для нескольких ТП на одну деталь
    execution_variant = Column(String(100), nullable=True)

    # v7.7d: вариант, который мастер видит в наряде по умолчанию.
    # Только один на product_id может быть True (контролируется в UI/db_manager).
    is_default_for_product = Column(Boolean, default=False, nullable=False)

    # v7.7e: ТП-шаблон без привязки к детали (product_id может быть NULL,
    # но мы оставляем его обязательным; отдельный признак ниже).
    is_template = Column(Boolean, default=False, nullable=False)

    # v10: привязка ТП к строке многоуровневого БОМ
    bom_item_id = Column(Integer, ForeignKey('bom_items.id'), nullable=True)
    bom_item = relationship("BOMItem", foreign_keys=[bom_item_id])

    author_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    approved_at = Column(DateTime)
    approved_by = Column(String(100))

    # Soft delete (вместо физического удаления — флаг + дата)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime)
    deleted_by = Column(Integer, ForeignKey('users.id'))

    # Связи
    product = relationship("Product", back_populates="tech_processes")
    author = relationship("User", back_populates="tech_processes",
                          foreign_keys="TechProcess.author_id")
    signatures = relationship("ApprovalSignature",
                              cascade="all, delete-orphan",
                              order_by="ApprovalSignature.signed_at")
    operations = relationship("Operation", back_populates="tech_process", 
                            cascade="all, delete-orphan", order_by="Operation.sort_order")
    material_norms = relationship("MaterialNorm", back_populates="tech_process")
    cost_calculation = relationship("CostCalculation", back_populates="tech_process", uselist=False)


class Operation(Base):
    """Операция технологического процесса"""
    __tablename__ = 'operations'
    
    id = Column(Integer, primary_key=True)
    tech_process_id = Column(Integer, ForeignKey('tech_processes.id'), nullable=False)
    
    number = Column(String(10), nullable=False)  # Номер операции (005, 010, ...)
    name = Column(String(200), nullable=False)
    code = Column(String(20))
    
    shop = Column(String(100))  # Цех/участок
    equipment_id = Column(Integer, ForeignKey('equipment.id'))
    profession_id = Column(Integer, ForeignKey('professions.id'))
    grade = Column(Integer)  # Разряд
    
    # Нормы времени
    t_setup = Column(Float, default=0)  # Тпз, мин
    t_piece = Column(Float, default=0)  # Тшт, мин
    t_main = Column(Float, default=0)   # То, мин
    t_auxiliary = Column(Float, default=0)  # Тв, мин
    
    machine_count = Column(Integer, default=1)
    note = Column(Text)
    sort_order = Column(Integer, default=0)

    # Включать ли операцию в маршрутно-технологический паспорт (МТП).
    # По умолчанию True. Если False — операция остаётся в ТП и участвует
    # в расчётах (норма времени, себестоимость), но в МК/МСК не выводится.
    include_in_mtp = Column(Boolean, default=True, nullable=False)

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime)

    # Связи
    tech_process = relationship("TechProcess", back_populates="operations")
    equipment = relationship("Equipment", back_populates="operations")
    profession = relationship("Profession", back_populates="operations")
    transitions = relationship("Transition", back_populates="operation", 
                              cascade="all, delete-orphan", order_by="Transition.sort_order")
    tools = relationship("OperationTool", back_populates="operation", cascade="all, delete-orphan")
    sketches = relationship("Sketch", back_populates="operation",
                            cascade="all, delete-orphan",
                            order_by="Sketch.sort_order")


class Transition(Base):
    """Переход операции"""
    __tablename__ = 'transitions'
    
    id = Column(Integer, primary_key=True)
    operation_id = Column(Integer, ForeignKey('operations.id'), nullable=False)
    
    number = Column(String(10), nullable=False)
    text = Column(Text, nullable=False)
    code = Column(String(20))
    
    # Параметры обработки (для механической обработки)
    diameter = Column(Float)  # Диаметр, мм
    length = Column(Float)    # Длина, мм
    depth = Column(Float)     # Глубина резания, мм
    feed = Column(Float)      # Подача, мм/об
    speed = Column(Float)     # Скорость резания, м/мин
    rpm = Column(Float)       # Частота вращения, об/мин
    passes = Column(Integer, default=1)  # Число проходов
    
    sort_order = Column(Integer, default=0)
    
    # Связи
    operation = relationship("Operation", back_populates="transitions")
    sketches = relationship("Sketch", back_populates="transition",
                            cascade="all, delete-orphan",
                            order_by="Sketch.sort_order")


class OperationTool(Base):
    """Оснастка операции"""
    __tablename__ = 'operation_tools'
    
    id = Column(Integer, primary_key=True)
    operation_id = Column(Integer, ForeignKey('operations.id'), nullable=False)
    tool_id = Column(Integer, ForeignKey('tools.id'), nullable=False)
    quantity = Column(Integer, default=1)
    
    # Связи
    operation = relationship("Operation", back_populates="tools")
    tool = relationship("Tool", back_populates="operation_tools")


class Sketch(Base):
    """Эскиз, прикреплённый к операции или переходу."""
    __tablename__ = 'sketches'

    id = Column(Integer, primary_key=True)
    operation_id = Column(Integer, ForeignKey('operations.id'), nullable=True)
    transition_id = Column(Integer, ForeignKey('transitions.id'), nullable=True)

    title = Column(String(200))                 # Подпись
    original_filename = Column(String(255))     # Оригинальное имя файла
    stored_path = Column(String(500), nullable=False)   # Относительный путь в data/sketches/
    file_type = Column(String(20))              # 'image' / 'pdf'
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    # Связи
    operation = relationship("Operation", back_populates="sketches")
    transition = relationship("Transition", back_populates="sketches")


# ==================== НОРМИРОВАНИЕ ====================

class MaterialNorm(Base):
    """Норма расхода материала"""
    __tablename__ = 'material_norms'
    
    id = Column(Integer, primary_key=True)
    tech_process_id = Column(Integer, ForeignKey('tech_processes.id'), nullable=False)
    material_id = Column(Integer, ForeignKey('materials.id'), nullable=False)
    
    blank_profile = Column(String(50))  # Профиль заготовки
    blank_dimensions = Column(String(100))  # Размеры заготовки
    allowance = Column(Float)  # Припуск, мм
    cutting_allowance = Column(Float)  # Припуск на отрезку, мм
    consumption_coefficient = Column(Float, default=1.0)
    
    norm_per_piece = Column(Float)  # Норма на деталь, кг
    waste_percent = Column(Float)   # % отходов
    cost_per_piece = Column(Float)  # Стоимость материала на деталь
    
    # Связи
    tech_process = relationship("TechProcess", back_populates="material_norms")


class CostCalculation(Base):
    """Расчёт себестоимости"""
    __tablename__ = 'cost_calculations'
    
    id = Column(Integer, primary_key=True)
    tech_process_id = Column(Integer, ForeignKey('tech_processes.id'), nullable=False)
    
    # Материалы
    material_cost = Column(Float, default=0)
    
    # Заработная плата
    labor_cost = Column(Float, default=0)
    
    # Отчисления
    social_contributions = Column(Float, default=0)
    
    # Эксплуатация оборудования
    equipment_cost = Column(Float, default=0)
    
    # Цеховые расходы
    shop_overhead = Column(Float, default=0)
    
    # Общезаводские расходы
    factory_overhead = Column(Float, default=0)
    
    # Итого
    production_cost = Column(Float, default=0)  # Производственная себестоимость
    full_cost = Column(Float, default=0)        # Полная себестоимость
    price = Column(Float, default=0)            # Цена с рентабельностью
    profit = Column(Float, default=0)           # Прибыль
    
    calculated_at = Column(DateTime, default=datetime.now)
    
    # Связи
    tech_process = relationship("TechProcess", back_populates="cost_calculation")


# ==================== ЖУРНАЛЫ И ИСТОРИЯ ====================

class ChangeLog(Base):
    """Журнал изменений"""
    __tablename__ = 'change_logs'
    
    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50))  # TechProcess, Operation, etc.
    entity_id = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'))
    action = Column(String(50))  # create, update, delete, approve, etc.
    description = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)

    user = relationship("User")


class TPVersion(Base):
    """Версии технологического процесса"""
    __tablename__ = 'tp_versions'
    
    id = Column(Integer, primary_key=True)
    tech_process_id = Column(Integer, ForeignKey('tech_processes.id'))
    version_number = Column(String(20))
    data_snapshot = Column(Text)  # JSON snapshot
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.now)
    comment = Column(Text)


# ==================== WORKFLOW УТВЕРЖДЕНИЯ ====================

class ApprovalSignature(Base):
    """Подпись (роль / пользователь / дата) на утверждении ТП.

    Несколько подписей на один ТП — workflow можно настраивать.
    """
    __tablename__ = 'approval_signatures'

    id = Column(Integer, primary_key=True)
    tech_process_id = Column(Integer, ForeignKey('tech_processes.id'),
                             nullable=False)
    role = Column(String(50), nullable=False)  # значение SignerRole.value
    user_id = Column(Integer, ForeignKey('users.id'))
    signed_at = Column(DateTime, default=datetime.now)
    comment = Column(Text)

    user = relationship("User")




# ==================== ЖУРНАЛ РЕГИСТРАЦИИ ТП/МТП ====================

class RegistrationJournal(Base):
    """Единый журнал регистрации ТП и МТП.

    Замещает два отдельных бумажных журнала:
    - «МСП -УЗГА.02101.NNNNN-19999» (журнал регистрации ТП)
    - «КП -УЗГА-изд-5xxx-год» (журнал паспортов / МТП)

    Одна запись = один зарегистрированный документ. Флаги
    in_tp_journal / in_mtp_journal управляют тем, в каких выгрузках
    запись отображается. Excluded = запись «исключена из журнала»,
    не удаляется, можно восстановить.
    """
    __tablename__ = 'registration_journal'

    id = Column(Integer, primary_key=True)
    entry_no = Column(Integer)  # № п/п в журнале (sequential)

    # Номера. Обычно совпадают (УЗГА.02101.NNNNN), но могут отличаться.
    tp_number = Column(String(80))   # Номер технологического процесса
    mtp_number = Column(String(80))  # Номер МТП / маршрутной карты

    # Связи на ORM-сущности (опц.)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    tech_process_id = Column(Integer, ForeignKey('tech_processes.id'),
                             nullable=True)

    # Snapshot полей: чтобы запись оставалась читаемой даже после
    # удаления связанных изделия / ТП.
    product_designation = Column(String(200))   # Обозначение чертежа
    product_name = Column(String(255))          # Наименование детали
    product_type = Column(String(255))          # Тип самолёта/изделия
    project = Column(String(255))               # Проект (ремонт и т.п.)
    executor = Column(String(255))              # Исполнитель
    notes = Column(Text)                        # Примечание

    # Даты
    date_registered = Column(Date, default=datetime.now)
    date_developed = Column(Date)               # Дата разработки ТП

    # Флаги участия в выгрузках
    in_tp_journal = Column(Boolean, default=True)
    in_mtp_journal = Column(Boolean, default=True)

    # Soft-exclude: пометить «исключено из журнала» с возможностью
    # восстановления (не удаление!)
    excluded = Column(Boolean, default=False)
    excluded_reason = Column(Text)
    excluded_at = Column(DateTime)
    excluded_by_user_id = Column(Integer, ForeignKey('users.id'),
                                 nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now,
                        onupdate=datetime.now)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    product = relationship('Product', foreign_keys=[product_id])
    tech_process = relationship('TechProcess', foreign_keys=[tech_process_id])
    excluded_by = relationship('User', foreign_keys=[excluded_by_user_id])


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
    payload = Column(Text)  # произвольный JSON

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
    received_date = Column(Date, default=datetime.utcnow)
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
