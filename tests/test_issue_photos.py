"""Tests for A5 issue photo storage."""
from pathlib import Path

import pytest

from database.models import (
    IssueKind, IssueSeverity, Operation, Product, ProductionIssue,
    TechProcess, TPStatus, TPType, User,
)
from modules import issue_photos, production


def _admin(s):
    return s.query(User).filter_by(username='admin').first()


def _make_tp_and_issue(db_manager) -> tuple[int, int]:
    """Создаёт ТП, наряд и issue. Возвращает (issue_id, admin_id)."""
    db_manager.create_user('master_p', 'StrongPass1!', role='master',
                           must_change_password=False)
    with db_manager.get_session() as s:
        admin = _admin(s)
        master = s.query(User).filter_by(username='master_p').first()
        p = Product(designation='PHOTO-1', name='Photo'); s.add(p); s.flush()
        tp = TechProcess(number='TP-PHOTO-1', version='1', author_id=admin.id,
                         product_id=p.id, status=TPStatus.APPROVED,
                         tp_type=TPType.SINGLE)
        s.add(tp); s.flush()
        for i in range(1, 3):
            s.add(Operation(tech_process_id=tp.id, number=f'{i*5:03d}',
                             name=f'Op {i}', sort_order=i))
        s.flush()
        wo = production.release_to_production(
            s, user={'id': admin.id, 'role': 'admin'},
            tech_process_id=tp.id, qty_total=10)
        issue = production.open_issue(
            s, user={'id': master.id, 'role': 'master'},
            work_order_id=wo.id,
            kind=IssueKind.NO_MATERIAL,
            severity=IssueSeverity.HIGH,
            title='Нет материала',
        )
        return issue.id, admin.id


def _make_dummy_png(path: Path):
    # 1×1 PNG
    import base64
    raw = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlE'
        'QVR42mNgYGD4DwABBAEAVnTNQAAAAABJRU5ErkJggg=='
    )
    path.write_bytes(raw)


def test_attach_and_list_photo(db_manager, tmp_path, monkeypatch):
    monkeypatch.setattr('config.DATA_DIR', str(tmp_path / 'data'),
                         raising=False)
    issue_id, admin_id = _make_tp_and_issue(db_manager)
    src = tmp_path / 'sample.png'
    _make_dummy_png(src)

    with db_manager.get_session() as s:
        ph = issue_photos.attach_photo(
            s, issue_id=issue_id, source_path=src,
            caption='тест', uploaded_by=admin_id)
        assert ph.id
        photos = issue_photos.list_photos(s, issue_id)
        assert len(photos) == 1
        assert Path(photos[0].file_path).exists()


def test_attach_rejects_unsupported_extension(db_manager, tmp_path):
    issue_id, _ = _make_tp_and_issue(db_manager)
    src = tmp_path / 'bad.txt'
    src.write_text('not an image')
    with db_manager.get_session() as s:
        with pytest.raises(ValueError):
            issue_photos.attach_photo(
                s, issue_id=issue_id, source_path=src)


def test_remove_photo_deletes_file(db_manager, tmp_path, monkeypatch):
    monkeypatch.setattr('config.DATA_DIR', str(tmp_path / 'data'),
                         raising=False)
    issue_id, _ = _make_tp_and_issue(db_manager)
    src = tmp_path / 's.png'
    _make_dummy_png(src)

    with db_manager.get_session() as s:
        ph = issue_photos.attach_photo(s, issue_id=issue_id,
                                        source_path=src)
        path = Path(ph.file_path)
        assert path.exists()
        ph_id = ph.id

    with db_manager.get_session() as s:
        ok = issue_photos.remove_photo(s, ph_id)
        assert ok
    assert not path.exists()
