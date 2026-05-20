"""
Модели базы данных SQLAlchemy
"""
import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import declarative_base, relationship

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
    api_key = Column(String(64), nullable=True)
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
    hourly_rates = Column(JSON)  # {1: 200, 2: 220, ...}

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
    changes = Column(JSON)  # {field: {before: ..., after: ...}}
    timestamp = Column(DateTime, default=datetime.now)

    user = relationship("User")


class TPVersion(Base):
    """Версии технологического процесса"""
    __tablename__ = 'tp_versions'

    id = Column(Integer, primary_key=True)
    tech_process_id = Column(Integer, ForeignKey('tech_processes.id'))
    version_number = Column(String(20))
    data_snapshot = Column(JSON)  # JSON snapshot
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


