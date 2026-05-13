"""Тесты модуля резервного копирования."""
import gzip
from pathlib import Path


def test_make_backup_creates_gz(db_manager, monkeypatch):
    """Создание бэкапа возвращает существующий *.db.gz файл."""
    import modules.backup as backup

    new_db = Path(db_manager.engine.url.database)
    monkeypatch.setattr(backup, '_sqlite_path', lambda: new_db)

    path = backup.make_backup(force=True)
    assert path is not None
    assert path.exists()
    assert path.suffix == '.gz'
    # читаемый gzip
    with gzip.open(path, 'rb') as g:
        head = g.read(16)
    assert head[:6] == b'SQLite'
    # cleanup
    path.unlink(missing_ok=True)
