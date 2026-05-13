"""Недавно открытые / избранное (D18).

Каждое «открытие» сущности (ТП, изделия, наряда…) фиксируется в
``user_bookmarks`` через ``track_open``; ``list_recent`` возвращает
последние N записей по ``last_opened_at``; ``list_favorites`` —
закладки с флагом ``is_favorite=True``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database.models import UserBookmark


def track_open(
    session: Session,
    *,
    user_id: Optional[int],
    target_type: str,
    target_id: int,
    title: Optional[str] = None,
) -> Optional[UserBookmark]:
    """Регистрирует факт открытия сущности.

    Если запись уже была — обновляет ``last_opened_at`` / увеличивает
    ``open_count`` / обновляет title (на случай переименования).
    Если ``user_id`` пуст — функция тихо возвращает None (например,
    в тестах).
    """
    if not user_id:
        return None
    b = (session.query(UserBookmark)
         .filter(UserBookmark.user_id == user_id,
                 UserBookmark.target_type == target_type,
                 UserBookmark.target_id == int(target_id))
         .one_or_none())
    now = datetime.now()
    if b is None:
        b = UserBookmark(
            user_id=user_id,
            target_type=target_type,
            target_id=int(target_id),
            title=title,
            last_opened_at=now,
            open_count=1,
            is_favorite=False,
        )
        session.add(b)
    else:
        b.last_opened_at = now
        b.open_count = (b.open_count or 0) + 1
        if title:
            b.title = title
    session.flush()
    return b


def list_recent(session: Session, *, user_id: int,
                target_type: Optional[str] = None,
                limit: int = 15) -> list[UserBookmark]:
    q = (session.query(UserBookmark)
         .filter(UserBookmark.user_id == user_id))
    if target_type:
        q = q.filter(UserBookmark.target_type == target_type)
    return q.order_by(UserBookmark.last_opened_at.desc()).limit(int(limit)).all()


def list_favorites(session: Session, *, user_id: int,
                    limit: int = 50) -> list[UserBookmark]:
    return (session.query(UserBookmark)
            .filter(UserBookmark.user_id == user_id,
                    UserBookmark.is_favorite.is_(True))
            .order_by(UserBookmark.last_opened_at.desc())
            .limit(int(limit)).all())


def toggle_favorite(session: Session, *, user_id: int,
                    target_type: str, target_id: int) -> bool:
    """Переключает флаг is_favorite. Возвращает новое значение."""
    b = (session.query(UserBookmark)
         .filter(UserBookmark.user_id == user_id,
                 UserBookmark.target_type == target_type,
                 UserBookmark.target_id == int(target_id))
         .one_or_none())
    if b is None:
        # создаём с already-favorite
        b = UserBookmark(
            user_id=user_id,
            target_type=target_type,
            target_id=int(target_id),
            last_opened_at=datetime.now(),
            open_count=0,
            is_favorite=True,
        )
        session.add(b)
        session.flush()
        return True
    b.is_favorite = not bool(b.is_favorite)
    return b.is_favorite
