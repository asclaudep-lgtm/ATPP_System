"""In-app уведомления (A6).

Простой модуль уведомлений: создаёт записи в таблице ``notifications`` и
позволяет другим частям системы прочитать их / отметить как прочитанные.

Сообщения остаются внутри приложения — никаких email/SMS. Если в будущем
потребуется внешний канал (Telegram, Slack), достаточно добавить
обработчик после ``notify_user`` (см. ``modules.alerts``).
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from database.models import Notification


def notify_user(
    session: Session,
    *,
    user_id: int,
    kind: str,
    title: str,
    body: Optional[str] = None,
    related_issue_id: Optional[int] = None,
    related_work_order_id: Optional[int] = None,
) -> Notification:
    """Создаёт уведомление для пользователя ``user_id``.

    Возвращает объект Notification (уже добавленный в сессию).
    Параллельно (через try/except) — пытается отправить алёрт по
    зарегистрированным каналам (см. ``modules.alerts``); если каналы
    не настроены, ошибки тихо игнорируются.
    """
    note = Notification(
        user_id=user_id,
        kind=kind,
        title=title[:200] if title else '',
        body=body,
        related_issue_id=related_issue_id,
        related_work_order_id=related_work_order_id,
        created_at=datetime.now(),
    )
    session.add(note)
    session.flush()

    # Опциональный внешний канал (вебхук)
    try:
        from . import alerts as _alerts
        _alerts.dispatch(kind=kind, title=title, body=body or '',
                         user_id=user_id,
                         related_issue_id=related_issue_id,
                         related_work_order_id=related_work_order_id)
    except Exception as e:  # noqa: BLE001
        print(f'[notify] alerts dispatch skipped: {e}')

    return note


def list_notifications(
    session: Session,
    *,
    user_id: int,
    only_unread: bool = False,
    limit: int = 100,
) -> list[Notification]:
    """Возвращает уведомления пользователя (новые сверху)."""
    q = (session.query(Notification)
         .filter(Notification.user_id == user_id)
         .order_by(Notification.created_at.desc()))
    if only_unread:
        q = q.filter(Notification.read_at.is_(None))
    return q.limit(int(limit)).all()


def unread_count(session: Session, user_id: int) -> int:
    """Сколько непрочитанных уведомлений у пользователя."""
    return (session.query(Notification)
            .filter(Notification.user_id == user_id,
                    Notification.read_at.is_(None))
            .count())


def mark_read(session: Session, *, ids: Iterable[int]) -> int:
    """Помечает указанные уведомления прочитанными. Возвращает их число."""
    ids = [int(i) for i in ids if i]
    if not ids:
        return 0
    rows = (session.query(Notification)
            .filter(Notification.id.in_(ids),
                    Notification.read_at.is_(None)).all())
    now = datetime.now()
    for r in rows:
        r.read_at = now
    return len(rows)


def mark_all_read(session: Session, user_id: int) -> int:
    """Помечает все непрочитанные уведомления пользователя прочитанными."""
    rows = (session.query(Notification)
            .filter(Notification.user_id == user_id,
                    Notification.read_at.is_(None)).all())
    now = datetime.now()
    for r in rows:
        r.read_at = now
    return len(rows)
