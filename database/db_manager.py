"""
Менеджер базы данных
"""
from datetime import datetime
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool, NullPool
import bcrypt
from contextlib import contextmanager

from .models import (Base, User, Material, Equipment, Tool, Profession,
                     Product, ProductGroup, TechProcess, Workshop,
                     BOMItem, AssemblyLevel)
from config import DATABASE_URL
from utils.logger import get_logger

log = get_logger(__name__)


class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    def __init__(self, database_url=None):
        self.database_url = database_url or DATABASE_URL
        
        if self.database_url.startswith('sqlite'):
            self.engine = create_engine(
                self.database_url,
                connect_args={'check_same_thread': False, 'timeout': 30},
                poolclass=NullPool
            )
        else:
            self.engine = create_engine(
                self.database_url,
                pool_size=5, max_overflow=10
            )
        
        # Создаём фабрику сессий
        session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(session_factory)
    
    def init_database(self):
        """Инициализация БД: create_all для свежих, Alembic для миграций."""
        # Всегда создаём таблицы, которых ещё нет (работает на свежей БД).
        Base.metadata.create_all(self.engine)

        # Миграции: Alembic — основной механизм (v10+).
        # _ensure_* — страховочный пояс для legacy БД, где Alembic может не сработать.
        from pathlib import Path
        alembic_ini = Path(__file__).resolve().parent.parent / 'alembic.ini'
        alembic_ok = False
        try:
            if alembic_ini.exists():
                from alembic import command
                from alembic.config import Config as AlembicConfig
                cfg = AlembicConfig(str(alembic_ini))
                cfg.set_main_option('sqlalchemy.url', self.database_url)
                command.upgrade(cfg, 'head')
                alembic_ok = True
        except (ImportError, RuntimeError, OSError):
            log.debug('Alembic upgrade skipped (no new migrations or DB unavailable)')
        except Exception:
            log.warning('Alembic upgrade failed — DB may need manual migration', exc_info=True)

        # v13: исправить INTEGER PRIMARY KEY (только если Alembic недоступен)
        if not alembic_ok:
            self._ensure_primary_keys()

        # v14: добавить отсутствующие колонки (только если Alembic недоступен)
        if not alembic_ok:
            self._ensure_v14_columns()

        self._create_initial_data()

    def _ensure_v14_columns(self):
        """Синхронизирует все колонки моделей с БД (добавляет отсутствующие)."""
        from sqlalchemy import inspect, text
        inspector = inspect(self.engine)
        with self.engine.connect() as conn:
            # Пройти по всем моделям и проверить колонки
            for table_name, table in Base.metadata.tables.items():
                if table_name not in inspector.get_table_names():
                    continue  # таблица ещё не создана — create_all сделает позже
                existing = {c['name'] for c in inspector.get_columns(table_name)}
                for col in table.columns:
                    if col.name not in existing:
                        # построить DDL для колонки
                        col_type_str = str(col.type).upper()
                        # упрощаем типы для SQLite
                        nullable = '' if col.nullable else ' NOT NULL'
                        default = ''
                        if col.default and col.default.arg is not None:
                            dv = col.default.arg
                            if isinstance(dv, bool):
                                default = f' DEFAULT {1 if dv else 0}'
                            elif isinstance(dv, (int, float)):
                                default = f' DEFAULT {dv}'
                            elif isinstance(dv, str):
                                default = f" DEFAULT '{dv}'"
                        sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type_str}{default}{nullable}"
                        try:
                            conn.execute(text(sql))
                            conn.commit()
                            log.info('Added column %s.%s', table_name, col.name)
                        except (sqlalchemy.exc.OperationalError, AttributeError) as e:
                            log.debug('Skip %s.%s: %s', table_name, col.name, e)
    
    def _ensure_primary_keys(self):
        """v13: гарантирует INTEGER PRIMARY KEY AUTOINCREMENT для всех id.

        SQLite требует INTEGER PRIMARY KEY (не INT) для автоинкремента rowid.
        Если таблица создана с id INT вместо INTEGER, INSERT даёт NULL в id.
        Метод проверяет и пересоздаёт таблицы с неправильной схемой.
        """
        from sqlalchemy import inspect, text

        inspector = inspect(self.engine)
        for table_name in inspector.get_table_names():
            if table_name.endswith('_new'):
                continue
            try:
                cols = inspector.get_columns(table_name)
                id_col = next((c for c in cols if c['name'] == 'id'), None)
                if id_col is None:
                    continue
                # SQLite reports type as 'INTEGER' if properly created
                col_type = str(id_col['type']).upper() if id_col.get('type') else ''
                if col_type == 'INTEGER' and id_col.get('primary_key'):
                    continue  # OK

                # Check actual SQLite schema
                pk_cols = inspector.get_pk_constraint(table_name)
                if pk_cols and 'id' in pk_cols.get('constrained_columns', []):
                    continue  # Already a PK

                # Fix: rebuild table
                self._rebuild_table_with_pk(table_name, cols)
            except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.InvalidRequestError):
                pass  # Non-critical — best-effort migration — don't block startup

    def _rebuild_table_with_pk(self, table_name: str, columns: list):
        """Rebuild a table with INTEGER PRIMARY KEY AUTOINCREMENT."""
        from sqlalchemy import text
        col_defs = []
        col_names = []
        for c in columns:
            name = c['name']
            col_names.append(name)
            ctype = 'INTEGER' if name == 'id' else str(c['type'] or 'TEXT')
            if name == 'id':
                col_defs.append(f'"{name}" INTEGER PRIMARY KEY AUTOINCREMENT')
                continue
            nullable = ''
            if c.get('nullable', True) is False:
                nullable = ' NOT NULL'
            default = ''
            cdefault = c.get('default')
            if cdefault:
                default = f' DEFAULT {cdefault}'
            col_defs.append(f'"{name}" {ctype}{nullable}{default}')

        with self.engine.begin() as conn:
            conn.execute(text(
                f'CREATE TABLE "{table_name}_new" ({", ".join(col_defs)})'))
            cols_str = ', '.join(f'"{n}"' for n in col_names)
            conn.execute(text(
                f'INSERT INTO "{table_name}_new" ({cols_str}) '
                f'SELECT {cols_str} FROM "{table_name}"'))
            if not table_name.replace('_', '').isalnum():
                raise ValueError(f"Invalid table name for rebuild: {table_name}")
            conn.execute(text(f'DROP TABLE "{table_name}"'))
            conn.execute(text(
                f'ALTER TABLE "{table_name}_new" RENAME TO "{table_name}"'))

    def _fill_work_order_barcodes(self):
        """Дозаполняет WorkOrder.barcode уникальным значением для существующих
        нарядов, у которых поле пустое (после миграции с v6)."""
        try:
            from database.models import WorkOrder
            with self.get_session() as s:
                rows = (s.query(WorkOrder)
                        .filter((WorkOrder.barcode.is_(None)) |
                                 (WorkOrder.barcode == '')).all())
                if not rows:
                    return
                for wo in rows:
                    # Базовый формат — номер наряда (он уже уникальный).
                    # Code128 принимает любой ASCII-текст.
                    wo.barcode = wo.number or f'WO-{wo.id}'
        except (ImportError, ValueError) as e:
            log.warning('fill barcodes skipped: %s', e)

    def _ensure_index(self, table: str, name: str, columns: list[str]):
        """Создаёт индекс, если он отсутствует. Безопасно для SQLite/PG."""
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            if table not in tables:
                return
            existing = {ix['name'] for ix in inspector.get_indexes(table)}
            if name in existing:
                return
            cols = ', '.join(columns)
            ddl = f'CREATE INDEX {name} ON {table} ({cols})'
            with self.engine.begin() as conn:
                conn.execute(text(ddl))
        except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.ProgrammingError) as e:
            log.warning('index %s on %s skipped: %s', name, table, e)

    def _create_initial_data(self):
        """Создание начальных данных"""
        session = self.Session()
        try:
            admin = None
            # Upsert admin user (race-condition safe)
            existing = session.query(User).filter_by(username='admin').first()
            if existing:
                admin = existing
            else:
                admin = User(
                    username='admin',
                    password_hash=self._hash_password('admin'),
                    full_name='Администратор',
                    role='admin',
                    is_active=True,
                    must_change_password=True,
                )
                session.add(admin)
                session.flush()  # get admin.id for FK references below
                session.flush()
            
            # Добавляем базовые материалы
            if session.query(Material).count() == 0:
                materials = [
                    Material(name='Сталь 45', grade='45', gost='ГОСТ 1050-88', density=7850, price_per_kg=50),
                    Material(name='Сталь 40Х', grade='40Х', gost='ГОСТ 4543-71', density=7850, price_per_kg=65),
                    Material(name='Д16Т', grade='Д16Т', gost='ГОСТ 4784-97', density=2780, price_per_kg=350),
                    Material(name='АМг6', grade='АМг6', gost='ГОСТ 4784-97', density=2640, price_per_kg=320),
                    Material(name='Бронза БрАЖ9-4', grade='БрАЖ9-4', gost='ГОСТ 18175-78', density=7600, price_per_kg=800),
                ]
                session.add_all(materials)
            
            # Добавляем базовое оборудование
            if session.query(Equipment).count() == 0:
                equipment = [
                    Equipment(name='Станок токарный 16К20', model='16К20', type='Токарный', power=10, cost_per_hour=150),
                    Equipment(name='Станок фрезерный 6Р12', model='6Р12', type='Фрезерный', power=7.5, cost_per_hour=120),
                    Equipment(name='Станок шлифовальный 3М151', model='3М151', type='Шлифовальный', power=5, cost_per_hour=100),
                    Equipment(name='Пресс гидравлический', model='П6330', type='Прессовое', power=15, cost_per_hour=200),
                ]
                session.add_all(equipment)
            
            # Добавляем профессии
            if session.query(Profession).count() == 0:
                professions = [
                    Profession(name='Токарь', typical_grade=3, 
                              hourly_rates='{"1": 200, "2": 220, "3": 250, "4": 280, "5": 320, "6": 360}'),
                    Profession(name='Фрезеровщик', typical_grade=3,
                              hourly_rates='{"1": 200, "2": 220, "3": 250, "4": 280, "5": 320, "6": 360}'),
                    Profession(name='Шлифовщик', typical_grade=4,
                              hourly_rates='{"1": 210, "2": 230, "3": 260, "4": 290, "5": 330, "6": 370}'),
                    Profession(name='Слесарь', typical_grade=3,
                              hourly_rates='{"1": 190, "2": 210, "3": 240, "4": 270, "5": 310, "6": 350}'),
                    Profession(name='Контролёр', typical_grade=3,
                              hourly_rates='{"1": 180, "2": 200, "3": 230, "4": 260, "5": 300, "6": 340}'),
                ]
                session.add_all(professions)
            
            # Добавим демонстрационные группы и изделия, чтобы UI имел что отображать
            if session.query(ProductGroup).count() == 0:
                g1 = ProductGroup(name='G1', display_name='Группа 1', sort_order=1)
                g2 = ProductGroup(name='G2', display_name='Группа 2', sort_order=2)
                session.add_all([g1, g2])
                session.flush()

                # Пример изделия
                # Выбираем любой материал если он есть
                mat = session.query(Material).first()
                prod1 = Product(
                    designation='P-001',
                    name='Деталь образца 1',
                    group_id=g1.id,
                    material_id=mat.id if mat else None,
                    mass=1.2,
                    dimensions='100x50x20',
                    blank_type='Обозначение',
                    accuracy_class='IT7',
                    roughness='Ra1.6',
                    quantity_in_assembly=1,
                    description='Пример детали для демонстрации',
                    author_id=admin.id if admin is not None else None,
                )
                session.add(prod1)
            
            # Базовые производственные участки (для модуля «Производство»)
            if session.query(Workshop).count() == 0:
                workshops = [
                    Workshop(code='WH', name='Склад', sort_order=1),
                    Workshop(code='TURN1', name='Токарный участок 1',
                             sort_order=10),
                    Workshop(code='MILL1', name='Фрезерный участок 1',
                             sort_order=20),
                    Workshop(code='ASSY', name='Слесарно-сборочный',
                             sort_order=30),
                    Workshop(code='QC', name='ОТК', sort_order=99),
                ]
                session.add_all(workshops)

            if session.query(BOMItem).count() == 0:
                # Демо-БОМ: привязываем к первому демо-изделию
                demo_product = session.query(Product).filter(
                    Product.designation == 'P-001').first()
                if demo_product:
                    root = BOMItem(product_id=demo_product.id,
                                   level=AssemblyLevel.PRODUCT,
                                   quantity=1, sort_order=0, position='')
                    session.add(root)
                    session.flush()
                    # Добавим пару дочерних компонентов
                    for i, (des, name, lev, qty, pos) in enumerate([
                        ('P-001-001', 'Корпус', AssemblyLevel.SUBASSEMBLY,
                         1, 'поз.1'),
                        ('P-001-002', 'Вал', AssemblyLevel.DETAIL,
                         2, 'поз.2'),
                    ]):
                        child_p = session.query(Product).filter(
                            Product.designation == des).first()
                        if not child_p:
                            child_p = Product(
                                designation=des, name=name,
                                author_id=1,
                                group_id=demo_product.group_id,
                            )
                            session.add(child_p)
                            session.flush()
                        item = BOMItem(
                            parent_id=root.id,
                            product_id=child_p.id,
                            level=lev, quantity=qty,
                            position=pos,
                            sort_order=i + 1,
                        )
                        session.add(item)

            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """Хеширование пароля"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Проверка пароля"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    @contextmanager
    def get_session(self):
        """Контекстный менеджер для работы с сессией"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def authenticate_user(self, username: str, password: str):
        """Аутентификация пользователя"""
        session = self.Session()
        try:
            user = session.query(User).filter_by(username=username, is_active=True).first()
            if user and self.verify_password(password, user.password_hash):
                # Сохраняем данные в переменные СРАЗУ после запроса
                user_id = user.id
                username_val = user.username
                full_name_val = user.full_name
                email_val = user.email
                role_val = user.role
                is_active_val = user.is_active
                created_at_val = user.created_at
                last_login_val = user.last_login
                must_change_pw = bool(user.must_change_password)

                # Обновляем время последнего входа
                user.last_login = datetime.now()
                session.commit()

                # Логируем факт входа в user_sessions (C13). Делаем это
                # отдельной операцией, чтобы её провал не ронял аутентификацию.
                try:
                    self._log_login(user_id)
                except (sqlalchemy.exc.OperationalError, TypeError) as e:
                    log.warning('log_login skipped: %s', e)

                # Возвращаем словарь с сохранёнными данными
                return {
                    'id': user_id,
                    'username': username_val,
                    'full_name': full_name_val,
                    'email': email_val,
                    'role': role_val,
                    'is_active': is_active_val,
                    'created_at': created_at_val,
                    'last_login': datetime.now(),
                    'must_change_password': must_change_pw,
                }
            return None
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def create_user(self, username: str, password: str, full_name: str = None,
                   email: str = None, role: str = 'user',
                   must_change_password: bool = True):
        """Создание нового пользователя.

        ``must_change_password`` — по умолчанию True: новый пользователь
        обязан сменить пароль при первом входе (D15).
        """
        with self.get_session() as session:
            user = User(
                username=username,
                password_hash=self._hash_password(password),
                full_name=full_name,
                email=email,
                role=role,
                must_change_password=bool(must_change_password),
            )
            session.add(user)
            session.flush()
            return user.id

    # ──────────────────────────────────────────────────────────────────
    # Лог входов / выходов (C13) и смена пароля (D15)
    # ──────────────────────────────────────────────────────────────────

    def _log_login(self, user_id: int) -> int:
        """Создаёт запись в user_sessions. Возвращает id сессии."""
        from .models import UserSession
        import socket
        try:
            host = socket.gethostname()
        except OSError:
            host = None
        try:
            from config import APP_VERSION
            ver = APP_VERSION
        except ImportError:
            ver = None
        with self.get_session() as s:
            us = UserSession(user_id=user_id, hostname=host, app_version=ver)
            s.add(us)
            s.flush()
            return us.id

    def end_user_session(self, user_id: int):
        """Закрывает все открытые user_sessions данного пользователя."""
        from .models import UserSession
        try:
            with self.get_session() as s:
                rows = (s.query(UserSession)
                        .filter(UserSession.user_id == user_id,
                                UserSession.ended_at.is_(None)).all())
                for row in rows:
                    row.ended_at = datetime.now()
        except (sqlalchemy.exc.OperationalError, AttributeError) as e:
            log.warning('end_user_session skipped: %s', e)

    def change_user_password(self, user_id: int, new_password: str,
                              clear_must_change: bool = True):
        """Меняет пароль пользователя и снимает флаг must_change_password."""
        with self.get_session() as s:
            u = s.get(User, user_id)
            if u is None:
                raise ValueError(f'Пользователь id={user_id} не найден.')
            u.password_hash = self._hash_password(new_password)
            u.password_changed_at = datetime.now()
            if clear_must_change:
                u.must_change_password = False
    
    def close(self):
        """Закрытие соединения"""
        self.Session.remove()
        self.engine.dispose()

    def summarize_data(self):
        """Возвращает сводку по данным в БД (для диагностики Seed)"""
        session = self.Session()
        try:
            return {
                'users': session.query(User).count(),
                'materials': session.query(Material).count(),
                'equipment': session.query(Equipment).count(),
                'tools': session.query(Tool).count(),
                'professions': session.query(Profession).count(),
                'product_groups': session.query(ProductGroup).count(),
                'products': session.query(Product).count(),
                'tech_processes': session.query(TechProcess).count(),
            }
        finally:
            session.close()
