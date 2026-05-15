"""
Утилиты для записи журнала изменений (ChangeLog) и снимков версий ТП (TPVersion).

Модуль намеренно сделан безопасным «fire-and-forget»: ошибки логируются в
stderr, но никогда не пробрасываются — основной поток работы пользователя
важнее, чем целостность аудита.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from utils.logger import get_logger

_log = get_logger(__name__)

from database.models import ChangeLog, TPVersion, TechProcess, Operation, Transition


def log_change(
    db_manager,
    *,
    user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int],
    description: str = '',
):
    """Записать одну запись в журнал изменений (открывает свою сессию)."""
    try:
        with db_manager.get_session() as s:
            s.add(ChangeLog(
                entity_type=entity_type,
                entity_id=entity_id,
                user_id=user_id,
                action=action,
                description=description,
                timestamp=datetime.now(),
            ))
    except Exception:
        _log.exception('Audit operation failed')


def log_change_session(
    session,
    *,
    user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int],
    description: str = '',
):
    """Записать в журнал в рамках уже открытой сессии (без commit)."""
    try:
        session.add(ChangeLog(
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            action=action,
            description=description,
            timestamp=datetime.now(),
        ))
    except Exception:
        _log.exception('Audit operation failed')


def snapshot_tp(db_manager, *, tp_id: int, user_id: Optional[int],
                comment: str = '') -> Optional[int]:
    """Сохранить полный снимок ТП в виде JSON в TPVersion.

    Возвращает id созданной версии или None при ошибке.
    """
    try:
        with db_manager.get_session() as s:
            tp = s.get(TechProcess, tp_id)
            if tp is None:
                return None
            data = {
                'tp': {
                    'id': tp.id,
                    'number': tp.number,
                    'version': tp.version,
                    'execution_variant': tp.execution_variant,
                    'status': tp.status.value if hasattr(tp.status, 'value') else str(tp.status),
                    'description': tp.description,
                },
                'product': {
                    'id': tp.product_id,
                    'designation': tp.product.designation if tp.product else None,
                    'name': tp.product.name if tp.product else None,
                },
                'operations': [],
            }
            for op in sorted(tp.operations, key=lambda o: (o.sort_order or 0)):
                op_dump = {
                    'id': op.id,
                    'number': op.number,
                    'name': op.name,
                    'shop': op.shop,
                    'equipment': op.equipment.name if op.equipment else None,
                    'profession': op.profession.name if op.profession else None,
                    'grade': op.grade,
                    't_setup': op.t_setup,
                    't_piece': op.t_piece,
                    'include_in_mtp': bool(op.include_in_mtp),
                    'transitions': [],
                }
                for tr in sorted(op.transitions, key=lambda t: (t.sort_order or 0)):
                    op_dump['transitions'].append({
                        'id': tr.id,
                        'number': tr.number,
                        'text': tr.text,
                    })
                data['operations'].append(op_dump)

            # Считаем следующий номер версии в виде "N"
            count = s.query(TPVersion).filter_by(tech_process_id=tp_id).count()
            version_number = str(count + 1)

            ver = TPVersion(
                tech_process_id=tp_id,
                version_number=version_number,
                data_snapshot=json.dumps(data, ensure_ascii=False, indent=2),
                created_by=user_id,
                created_at=datetime.now(),
                comment=comment or f'Снимок версии {version_number}',
            )
            s.add(ver)
            s.flush()
            return ver.id
    except Exception:
        _log.exception('Audit operation failed')
        return None


def list_audit(db_manager, *, limit: int = 500,
               entity_type: Optional[str] = None,
               action: Optional[str] = None) -> list[dict]:
    """Прочитать последние записи журнала изменений."""
    try:
        with db_manager.get_session() as s:
            q = s.query(ChangeLog).order_by(ChangeLog.timestamp.desc())
            if entity_type:
                q = q.filter(ChangeLog.entity_type == entity_type)
            if action:
                q = q.filter(ChangeLog.action == action)
            rows = q.limit(limit).all()
            out: list[dict] = []
            for r in rows:
                out.append({
                    'id': r.id,
                    'timestamp': r.timestamp,
                    'entity_type': r.entity_type,
                    'entity_id': r.entity_id,
                    'user_id': r.user_id,
                    'user_name': (r.user.full_name or r.user.username) if getattr(r, 'user', None) else '',
                    'action': r.action,
                    'description': r.description,
                })
            return out
    except Exception:
        _log.exception('Audit operation failed')
        return []


def list_versions(db_manager, *, tp_id: int) -> list[dict]:
    try:
        with db_manager.get_session() as s:
            rows = s.query(TPVersion).filter_by(tech_process_id=tp_id).order_by(
                TPVersion.created_at.desc()
            ).all()
            return [{
                'id': r.id,
                'version_number': r.version_number,
                'created_at': r.created_at,
                'created_by': r.created_by,
                'comment': r.comment,
                'data_snapshot': r.data_snapshot,
            } for r in rows]
    except Exception:
        _log.exception('Audit operation failed')
        return []
