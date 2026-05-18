"""
Конфигурация приложения АТПП
"""
import os
from pathlib import Path

# Базовые пути
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RESOURCES_DIR = BASE_DIR / "resources"
TEMPLATES_DIR = RESOURCES_DIR / "templates"

# Создаём директории если их нет
DATA_DIR.mkdir(exist_ok=True)
RESOURCES_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# База данных
def _load_database_url() -> str:
    """DATABASE_URL: ENV > data/db.cfg > default sqlite."""
    env = os.getenv("DATABASE_URL")
    if env:
        return env
    cfg = DATA_DIR / "db.cfg"
    if cfg.exists():
        try:
            for line in cfg.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
        except Exception:
            pass
    return f"sqlite:///{DATA_DIR / 'atpp.db'}"


DATABASE_URL = _load_database_url()

# Настройки приложения
APP_NAME = "АТПП - Система автоматизации технологической подготовки производства"
APP_VERSION = "1.0.0"
COMPANY_NAME = "УЗГА"

# Настройки интерфейса
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
THEME = "light"  # always light

# Настройки безопасности
PASSWORD_MIN_LENGTH = 6
SESSION_TIMEOUT = 3600  # секунд
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # секунд

# Настройки документов
DEFAULT_TEMPLATE = TEMPLATES_DIR / "default_template.xlsx"
EXPORT_DIR = DATA_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

# Хранилище эскизов
SKETCHES_DIR = DATA_DIR / "sketches"
SKETCHES_DIR.mkdir(exist_ok=True)


def _sanitize_designation(s: str) -> str:
    """
    Приводим обозначение к имени папки, безопасному для FS.
    Запрещены: \\ / : * ? " < > |  и управляющие символы.
    """
    if not s:
        return "_no_designation"
    bad = set('\\/:*?"<>|')
    out = ''.join(('_' if (ch in bad or ord(ch) < 32) else ch) for ch in s)
    out = out.strip(' .')        # хвостовые точки/пробелы запрещены в Windows
    return out or "_no_designation"


def product_export_dir(designation_or_product) -> Path:
    """
    Папка экспорта для конкретной детали:
        data/exports/<sanitized designation>/

    Принимает либо строку обозначения, либо ORM-объект Product / TechProcess
    (берём designation из product). Создаёт папку, если её нет.
    """
    if designation_or_product is None:
        designation = ''
    elif isinstance(designation_or_product, str):
        designation = designation_or_product
    else:
        designation = (
            getattr(designation_or_product, 'designation', None)
            or getattr(getattr(designation_or_product, 'product', None),
                       'designation', '')
            or ''
        )
    folder = EXPORT_DIR / _sanitize_designation(designation)
    folder.mkdir(parents=True, exist_ok=True)
    return folder

# Настройки расчётов
DEFAULT_MATERIAL_COEFFICIENT = 1.15
DEFAULT_LABOR_OVERHEAD = 0.302  # 30.2% отчисления
DEFAULT_SHOP_OVERHEAD = 0.25    # 25% цеховые расходы
DEFAULT_FACTORY_OVERHEAD = 0.40  # 40% общезаводские
DEFAULT_PROFIT_MARGIN = 0.20     # 20% рентабельность

# Логирование
LOG_LEVEL = "INFO"
LOG_FILE = DATA_DIR / "atpp.log"
