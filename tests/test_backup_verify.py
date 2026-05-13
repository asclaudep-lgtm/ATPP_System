"""Tests for C11 verify_backup_integrity (test-restore)."""
import gzip
import shutil
import sqlite3
from pathlib import Path

from modules import backup


def _make_sqlite_db(path: Path):
    con = sqlite3.connect(str(path))
    cur = con.cursor()
    cur.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)')
    cur.execute('CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)')
    cur.execute("INSERT INTO users (username) VALUES ('alice'), ('bob')")
    cur.execute("INSERT INTO products (name) VALUES ('p1'), ('p2'), ('p3')")
    con.commit()
    con.close()


def test_verify_sqlite_backup_ok(tmp_path):
    raw = tmp_path / 'sample.db'
    _make_sqlite_db(raw)
    gz = tmp_path / 'sample.db.gz'
    with open(raw, 'rb') as src, gzip.open(gz, 'wb') as dst:
        shutil.copyfileobj(src, dst)
    info = backup.verify_backup_integrity(gz)
    assert info['ok']
    assert info['kind'] == 'sqlite'
    assert info['rows_users'] == 2
    assert info['rows_products'] == 3


def test_verify_sqlite_backup_bad_archive(tmp_path):
    bad = tmp_path / 'bad.db.gz'
    bad.write_bytes(b'not a gzip')
    info = backup.verify_backup_integrity(bad)
    assert not info['ok']
    assert info['error']


def test_verify_unknown_extension(tmp_path):
    f = tmp_path / 'file.bak'
    f.write_bytes(b'random')
    info = backup.verify_backup_integrity(f)
    assert not info['ok']


def test_verify_pg_backup_recognises_pgdmp_header(tmp_path):
    f = tmp_path / 'real.dump'
    f.write_bytes(b'PGDMP' + b'\x00' * 4096)
    info = backup.verify_backup_integrity(f)
    assert info['kind'] == 'postgresql'
    assert info['ok']
