"""Управление фотографиями, прикреплёнными к проблемам в производстве (A5).

Фото копируются в ``data/issues/<issue_id>/<uuid>.<ext>``. Это попадает
в обычный backup-каталог, поэтому фото восстанавливаются вместе с БД.
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from database.models import IssuePhoto, ProductionIssue

_ALLOWED_EXT = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}


def _photos_root() -> Path:
    """Каталог для хранения фотографий проблем."""
    try:
        from config import DATA_DIR
        root = Path(DATA_DIR) / 'issues'
    except Exception:
        # Запасной путь — относительно корня проекта.
        root = Path(__file__).resolve().parent.parent / 'data' / 'issues'
    root.mkdir(parents=True, exist_ok=True)
    return root


def attach_photo(
    session: Session,
    *,
    issue_id: int,
    source_path: str | Path,
    caption: Optional[str] = None,
    uploaded_by: Optional[int] = None,
) -> IssuePhoto:
    """Копирует файл в storage и регистрирует в БД."""
    issue = session.get(ProductionIssue, issue_id)
    if issue is None:
        raise ValueError(f'Проблема id={issue_id} не найдена.')

    src = Path(source_path)
    if not src.exists() or not src.is_file():
        raise ValueError(f'Файл не найден: {src}')
    ext = src.suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise ValueError(
            f'Расширение «{ext}» не поддерживается. '
            f'Допустимые: {", ".join(sorted(_ALLOWED_EXT))}.')

    dest_dir = _photos_root() / str(issue_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = f'{uuid.uuid4().hex}{ext}'
    dest = dest_dir / fname
    shutil.copyfile(src, dest)

    rel_path = str(dest.resolve())
    photo = IssuePhoto(
        issue_id=issue_id,
        file_path=rel_path,
        caption=(caption or '').strip() or None,
        uploaded_by=uploaded_by,
    )
    session.add(photo)
    session.flush()
    return photo


def list_photos(session: Session, issue_id: int) -> list[IssuePhoto]:
    """Возвращает фотографии данной проблемы (старые → новые)."""
    return (session.query(IssuePhoto)
            .filter(IssuePhoto.issue_id == issue_id)
            .order_by(IssuePhoto.uploaded_at).all())


def remove_photo(session: Session, photo_id: int, *,
                 delete_file: bool = True) -> bool:
    """Удаляет фотографию (запись и опционально файл)."""
    photo = session.get(IssuePhoto, photo_id)
    if photo is None:
        return False
    path = photo.file_path
    session.delete(photo)
    if delete_file and path:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            from utils.logger import get_logger
            get_logger(__name__).warning('cannot delete file %s: %s', path, e)
    return True
