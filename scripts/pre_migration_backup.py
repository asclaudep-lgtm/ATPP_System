"""Auto-backup before Alembic migrations. Called from CI / deploy scripts.

Usage:
  python scripts/pre_migration_backup.py

Reads DATABASE_URL from env. Creates a timestamped backup in data/backups/.
Skips if DATABASE_URL is sqlite (just copies the file).
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import DATABASE_URL


def backup_sqlite(url: str) -> Path:
    """Copy SQLite file to backups/."""
    db_path = Path(url.replace('sqlite:///', ''))
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    if not db_path.exists():
        print(f'DB file not found: {db_path}')
        sys.exit(0)

    backup_dir = ROOT / 'data' / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = backup_dir / f'pre_migrate_{db_path.stem}_{ts}.db'
    shutil.copy2(str(db_path), str(dest))
    print(f'SQLite backup: {dest} ({dest.stat().st_size} bytes)')
    return dest


def backup_postgres(url: str) -> Path:
    """Run pg_dump for PostgreSQL."""
    backup_dir = ROOT / 'data' / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = backup_dir / f'pre_migrate_pg_{ts}.dump'

    cmd = ['pg_dump', '--format=custom', '--no-owner', f'--file={dest}']
    # Pass URL as env PGPASSWORD etc
    env = os.environ.copy()
    if '@' in url:
        # Parse postgresql://user:pass@host:port/db
        from urllib.parse import urlparse
        u = url.replace('postgresql+asyncpg://', 'postgresql://')
        u = u.replace('postgresql+psycopg2://', 'postgresql://')
        p = urlparse(u)
        env['PGHOST'] = p.hostname or 'localhost'
        env['PGPORT'] = str(p.port or 5432)
        env['PGUSER'] = p.username or 'postgres'
        env['PGPASSWORD'] = p.password or ''
        env['PGDATABASE'] = (p.path or '').lstrip('/') or 'postgres'
        cmd = ['pg_dump', '--format=custom', '--no-owner', f'--file={dest}']
    subprocess.run(cmd, env=env, check=True)
    print(f'PostgreSQL backup: {dest}')
    return dest


if __name__ == '__main__':
    if DATABASE_URL.startswith('sqlite'):
        backup_sqlite(DATABASE_URL)
    elif 'postgres' in DATABASE_URL:
        backup_postgres(DATABASE_URL)
    else:
        print(f'Unknown DB type: {DATABASE_URL}')
        sys.exit(1)
