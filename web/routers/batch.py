"""Batch-операции: массовое утверждение ТП, назначение нарядов."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from pydantic import BaseModel

from web.deps import get_db, get_current_user
from modules.workflow import try_auto_approve, add_signature
from modules.audit import log_change_session

router = APIRouter(tags=["batch"])


class BatchApproveRequest(BaseModel):
    tp_ids: List[int]
    comment: str = ""


@router.post("/batch/approve-tps")
def batch_approve_tps(
    body: BatchApproveRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    results = []
    for tp_id in body.tp_ids:
        sp = db.begin_nested()
        try:
            ok = try_auto_approve(db, tp_id, user_id=user.id)
            if ok:
                results.append({'tp_id': tp_id, 'status': 'approved'})
            else:
                add_signature(db, tp_id, role='approver', user_id=user.id,
                              comment=body.comment or 'Массовое утверждение')
                ok2 = try_auto_approve(db, tp_id, user_id=user.id)
                if ok2:
                    results.append({'tp_id': tp_id, 'status': 'approved'})
                else:
                    results.append({'tp_id': tp_id, 'status': 'pending', 'error': 'Требуются другие подписи'})
            sp.commit()
        except Exception as e:
            sp.rollback()
            results.append({'tp_id': tp_id, 'status': 'error', 'error': str(e)})
    db.commit()
    return {'results': results, 'total': len(body.tp_ids)}


class BatchAssignRequest(BaseModel):
    wo_ids: List[int]
    workshop_id: int


@router.post("/batch/assign-work-orders")
def batch_assign_work_orders(
    body: BatchAssignRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    from database.models import WorkOrder, Workshop
    results = []
    for wo_id in body.wo_ids:
        sp = db.begin_nested()
        try:
            wo = db.get(WorkOrder, wo_id)
            if wo is None:
                sp.rollback()
                results.append({'wo_id': wo_id, 'status': 'error', 'error': 'Не найден'})
                continue
            ws = db.get(Workshop, body.workshop_id)
            if ws is None:
                sp.rollback()
                results.append({'wo_id': wo_id, 'status': 'error', 'error': 'Цех не найден'})
                continue
            wo.production_workshop_id = body.workshop_id
            wo.status = 'Передан в производство'
            log_change_session(
                db, user_id=user.id, action='batch_assign',
                entity_type='WorkOrder', entity_id=wo_id,
                description=f'Назначен в цех {ws.name}')
            sp.commit()
            results.append({'wo_id': wo_id, 'status': 'assigned'})
        except Exception as e:
            sp.rollback()
            results.append({'wo_id': wo_id, 'status': 'error', 'error': str(e)})
    db.commit()
    return {'results': results, 'total': len(body.wo_ids)}
