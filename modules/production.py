"""Бизнес-логика модуля «Производство» (MES-lite).

Все операции — короткие транзакции, конкурентный доступ защищён
optimistic-lock на ``WorkOrderItem.version``.

Терминология:
    - WorkOrder (наряд)         — производственное задание по одному ТП
    - WorkOrderItem (партия)    — одна единица учёта внутри наряда (qty шт.)
    - RouteStep (маршрутная точка) — шаг маршрута (одна операция для одной партии)
    - ProductionEvent           — событие в журнале (audit log)
    - ProductionIssue           — проблема в производстве

Роли:
    - technologist / admin       — RELEASE (передать ТП в производство)
    - master / admin             — REGISTER, MOVE, RESOLVE
    - worker / master / admin    — START_OP / FINISH_OP, raise issues
    - qc / admin                 — финальная приёмка
"""
from __future__ import annotations

from modules import audit as _audit

import json
import secrets
from datetime import datetime, date
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from database.models import (
    Operation,
    ProductionEvent,
    ProductionIssue,
    RouteStep,
    RouteStepStatus,
    TechProcess,
    WorkOrder,
    WorkOrderItem,
    WorkOrderItemStatus,
    WorkOrderStatus,
    Workshop,
    IssueKind,
    IssueSeverity,
    IssueStatus,
)


# ────────────────────────────────────────────────────────────────────────────
# Роли — кому что разрешено
# ────────────────────────────────────────────────────────────────────────────

ROLE_RELEASE = {'admin', 'technologist'}
ROLE_REGISTER = {'admin', 'master'}
ROLE_MOVE = {'admin', 'master', 'worker'}
ROLE_ISSUE_OPEN = {'admin', 'master', 'worker', 'qc'}
ROLE_ISSUE_RESOLVE = {'admin', 'master', 'technologist', 'qc'}
ROLE_QC = {'admin', 'qc', 'master'}
# Возврат партии на доработку — мастер участка или технолог.
ROLE_REWORK = {'admin', 'master', 'technologist'}
# Отмена наряда — только технолог (запустивший) или администратор.
ROLE_CANCEL = {'admin', 'technologist'}


class ProductionError(Exception):
    """Бизнес-ошибка модуля производства."""


def _check_role(user: dict, allowed: set, action: str) -> None:
    role = (user or {}).get('role', '')
    if role not in allowed:
        raise ProductionError(
            f'Действие «{action}» доступно ролям: {", ".join(sorted(allowed))}'
            f' (ваша роль: {role or "—"})'
        )


# ────────────────────────────────────────────────────────────────────────────
# Утилиты
# ────────────────────────────────────────────────────────────────────────────

BARCODE_PREFIX = 'ATPP-WI-'


def generate_barcode(item_id: int) -> str:
    """Уникальный штрих-код для партии. Формат: ATPP-WI-<id>-<rand6>."""
    rand = secrets.token_hex(3).upper()  # 6 hex символов
    return f'{BARCODE_PREFIX}{item_id}-{rand}'


def parse_barcode(text: str) -> Optional[int]:
    """Возвращает id WorkOrderItem из штрих-кода ATPP-WI-<id>-... или None."""
    if not text:
        return None
    s = text.strip()
    if not s.startswith(BARCODE_PREFIX):
        return None
    rest = s[len(BARCODE_PREFIX):]
    head = rest.split('-', 1)[0]
    try:
        return int(head)
    except ValueError:
        return None


def _next_wo_number(session: Session) -> str:
    """Генерирует номер наряда вида WO-YYYY-NNNN."""
    year = datetime.now().year
    prefix = f'WO-{year}-'
    last = (
        session.query(WorkOrder)
        .filter(WorkOrder.number.like(prefix + '%'))
        .order_by(WorkOrder.id.desc())
        .first()
    )
    next_n = 1
    if last and last.number:
        try:
            next_n = int(last.number.rsplit('-', 1)[-1]) + 1
        except (ValueError, IndexError):
            next_n = 1
    return f'{prefix}{next_n:04d}'


def _log_event(
    session: Session,
    user_id: Optional[int],
    event_type: str,
    *,
    work_order: Optional[WorkOrder] = None,
    item: Optional[WorkOrderItem] = None,
    workshop: Optional[Workshop] = None,
    operation: Optional[Operation] = None,
    payload: Optional[dict] = None,
) -> ProductionEvent:
    ev = ProductionEvent(
        at=datetime.now(),
        user_id=user_id,
        work_order_id=work_order.id if work_order else (
            item.work_order_id if item else None),
        work_order_item_id=item.id if item else None,
        workshop_id=workshop.id if workshop else None,
        operation_id=operation.id if operation else None,
        event_type=event_type,
        payload=json.dumps(payload, ensure_ascii=False) if payload else None,
    )
    session.add(ev)
    return ev


# ────────────────────────────────────────────────────────────────────────────
# 1. Передача ТП в производство (технолог)
# ────────────────────────────────────────────────────────────────────────────

def release_to_production(
    session: Session,
    *,
    user: dict,
    tech_process_id: int,
    qty_total: int,
    customer_order: Optional[str] = None,
    priority: int = 0,
    due_date: Optional[date] = None,
    notes: Optional[str] = None,
) -> WorkOrder:
    """Создаёт наряд в статусе RELEASED. Возвращает наряд."""
    _check_role(user, ROLE_RELEASE, 'передача ТП в производство')

    if qty_total <= 0:
        raise ProductionError('Количество должно быть > 0.')

    tp = session.get(TechProcess, tech_process_id)
    if tp is None:
        raise ProductionError('Технологический процесс не найден.')

    # Опционально: разрешать только утверждённые ТП. Сейчас разрешаем любой —
    # при необходимости можно ужесточить.
    wo_number = _next_wo_number(session)
    wo = WorkOrder(
        number=wo_number,
        # v7: один штрих-код на МТП (равен номеру наряда — уникальный
        # короткий ASCII, отлично подходит для Code128).
        barcode=wo_number,
        tech_process_id=tp.id,
        product_id=tp.product_id,
        qty_total=qty_total,
        qty_done=0,
        qty_scrap=0,
        customer_order=customer_order,
        priority=priority,
        due_date=due_date,
        status=WorkOrderStatus.RELEASED,
        released_by=user.get('id'),
        released_at=datetime.now(),
        notes=notes,
    )
    session.add(wo)
    session.flush()  # получить wo.id
    _log_event(
        session, user.get('id'), 'RELEASED',
        work_order=wo,
        payload={'qty_total': qty_total, 'tp_number': tp.number,
                 'customer_order': customer_order},
    )
    _audit.log_change_session(session, user_id=user.get('id'), entity_type='WorkOrder',
                              entity_id=wo.id, action='release',
                              description=f'Наряд {wo.number} передан в производство')
    return wo


# ────────────────────────────────────────────────────────────────────────────
# 2. Регистрация наряда мастером
# ────────────────────────────────────────────────────────────────────────────

def register_work_order(
    session: Session,
    *,
    user: dict,
    work_order_id: int,
    initial_workshop_id: int,
    split_into: Optional[Iterable[int]] = None,
) -> list[WorkOrderItem]:
    """Создаёт партии и маршрутные точки.

    ``split_into`` — список количеств партий. Например, для qty_total=100:
        - None              → одна партия 100 шт.
        - [100]             → одна партия 100 шт.
        - [50, 50]          → две партии по 50 шт.
        - [1] * 100         → единичная маркировка
    """
    _check_role(user, ROLE_REGISTER, 'регистрация наряда')

    wo = session.get(WorkOrder, work_order_id)
    if wo is None:
        raise ProductionError('Наряд не найден.')
    if wo.status != WorkOrderStatus.RELEASED:
        raise ProductionError(
            f'Наряд в статусе «{wo.status.value}», его нельзя регистрировать заново.'
        )

    workshop = session.get(Workshop, initial_workshop_id)
    if workshop is None or not workshop.is_active:
        raise ProductionError('Начальный участок не найден или неактивен.')

    sizes = list(split_into) if split_into else [wo.qty_total]
    if any(s <= 0 for s in sizes):
        raise ProductionError('Размер партии должен быть > 0.')
    if sum(sizes) != wo.qty_total:
        raise ProductionError(
            f'Сумма партий ({sum(sizes)}) должна равняться {wo.qty_total}.'
        )

    operations = (
        session.query(Operation)
        .filter(Operation.tech_process_id == wo.tech_process_id,
                Operation.is_deleted.is_(False))
        .order_by(Operation.sort_order, Operation.number)
        .all()
    )
    if not operations:
        raise ProductionError(
            'В технологическом процессе нет операций. '
            'Перед запуском в производство добавьте операции.'
        )

    items: list[WorkOrderItem] = []
    for idx, qty in enumerate(sizes, start=1):
        item = WorkOrderItem(
            work_order_id=wo.id,
            barcode='',  # сгенерим после flush
            serial=f'{wo.number}/{idx:02d}',
            qty=qty,
            current_workshop_id=workshop.id,
            current_operation_id=operations[0].id,
            status=WorkOrderItemStatus.WAITING,
        )
        session.add(item)
        session.flush()
        item.barcode = generate_barcode(item.id)

        # Создаём шаги маршрута по операциям ТП
        for seq, op in enumerate(operations, start=1):
            step = RouteStep(
                work_order_item_id=item.id,
                operation_id=op.id,
                workshop_id=workshop.id if seq == 1 else None,
                seq=seq,
                status=RouteStepStatus.PENDING,
            )
            session.add(step)
        items.append(item)

    wo.status = WorkOrderStatus.REGISTERED
    wo.registered_by = user.get('id')
    wo.registered_at = datetime.now()

    _log_event(
        session, user.get('id'), 'REGISTERED',
        work_order=wo, workshop=workshop,
        payload={'items_count': len(items), 'sizes': sizes},
    )
    return items


# ────────────────────────────────────────────────────────────────────────────
# 3. Перемещение партии: старт/финиш операции, передача на следующий участок
# ────────────────────────────────────────────────────────────────────────────

def _current_step(item: WorkOrderItem) -> Optional[RouteStep]:
    """Текущая (PENDING/IN_PROGRESS) маршрутная точка партии."""
    pending = [s for s in item.route_steps
               if s.status in (RouteStepStatus.PENDING,
                               RouteStepStatus.IN_PROGRESS,
                               RouteStepStatus.REWORK)]
    return pending[0] if pending else None


def start_operation(
    session: Session,
    *,
    user: dict,
    item_id: int,
    workshop_id: Optional[int] = None,
) -> RouteStep:
    """Мастер/рабочий начинает выполнение текущей операции."""
    _check_role(user, ROLE_MOVE, 'начало операции')

    item = session.get(WorkOrderItem, item_id)
    if item is None:
        raise ProductionError('Партия не найдена.')

    step = _current_step(item)
    if step is None:
        raise ProductionError('У партии нет ожидающих операций.')

    if step.status == RouteStepStatus.IN_PROGRESS:
        raise ProductionError('Операция уже выполняется.')

    step.status = RouteStepStatus.IN_PROGRESS
    step.started_at = datetime.now()
    step.worker_user_id = user.get('id')
    if workshop_id:
        step.workshop_id = workshop_id

    item.status = WorkOrderItemStatus.IN_PROGRESS
    if workshop_id:
        item.current_workshop_id = workshop_id
    item.current_operation_id = step.operation_id

    wo = item.work_order
    if wo.status == WorkOrderStatus.REGISTERED:
        wo.status = WorkOrderStatus.IN_PROGRESS

    _log_event(
        session, user.get('id'), 'STARTED',
        work_order=wo, item=item,
        operation=step.operation,
        payload={'seq': step.seq,
                 'workshop_id': item.current_workshop_id},
    )
    return step


def finish_operation(
    session: Session,
    *,
    user: dict,
    item_id: int,
    qty_good: int,
    qty_scrap: int = 0,
    note: Optional[str] = None,
    next_workshop_id: Optional[int] = None,
) -> RouteStep:
    """Мастер/рабочий завершает текущую операцию.

    Если есть следующий шаг — партия становится WAITING на следующей операции,
    при этом current_workshop переключается на ``next_workshop_id`` (если задан),
    либо на тот же.
    Если шагов больше нет — партия и наряд завершаются (если все партии готовы).
    """
    _check_role(user, ROLE_MOVE, 'завершение операции')

    if qty_good < 0 or qty_scrap < 0:
        raise ProductionError('Количество не может быть отрицательным.')

    item = session.get(WorkOrderItem, item_id)
    if item is None:
        raise ProductionError('Партия не найдена.')

    step = _current_step(item)
    if step is None:
        raise ProductionError('У партии нет активной операции.')
    if step.status not in (RouteStepStatus.IN_PROGRESS,
                           RouteStepStatus.REWORK,
                           RouteStepStatus.PENDING):
        raise ProductionError(
            f'Шаг в статусе «{step.status.value}», завершить нельзя.'
        )

    if qty_good + qty_scrap > item.qty:
        raise ProductionError(
            f'Сумма годных ({qty_good}) и брака ({qty_scrap}) превышает '
            f'размер партии ({item.qty}).'
        )

    step.status = RouteStepStatus.DONE
    step.finished_at = datetime.now()
    step.qty_good = qty_good
    step.qty_scrap = qty_scrap
    if note:
        step.note = note
    if step.worker_user_id is None:
        step.worker_user_id = user.get('id')

    # Накопление брака на партии (учитывается только последний снятый брак)
    item.qty_good = qty_good
    item.qty_scrap = (item.qty_scrap or 0) + qty_scrap

    next_step = next(
        (s for s in item.route_steps
         if s.seq > step.seq and s.status == RouteStepStatus.PENDING),
        None,
    )

    wo = item.work_order

    if next_step is not None:
        # Передача на следующий участок / следующую операцию
        item.status = WorkOrderItemStatus.WAITING
        item.current_operation_id = next_step.operation_id
        if next_workshop_id:
            item.current_workshop_id = next_workshop_id
            next_step.workshop_id = next_workshop_id
        else:
            # остаёмся на том же участке (multi-op в одном цеху)
            next_step.workshop_id = item.current_workshop_id
        _log_event(
            session, user.get('id'), 'FINISHED',
            work_order=wo, item=item, operation=step.operation,
            payload={'qty_good': qty_good, 'qty_scrap': qty_scrap,
                     'note': note},
        )
        _log_event(
            session, user.get('id'), 'MOVED',
            work_order=wo, item=item, operation=next_step.operation,
            payload={'to_workshop_id': item.current_workshop_id,
                     'next_seq': next_step.seq},
        )
    else:
        # Это была последняя операция — партия готова
        item.status = (
            WorkOrderItemStatus.DONE if qty_good > 0
            else WorkOrderItemStatus.SCRAP
        )
        _log_event(
            session, user.get('id'), 'FINISHED',
            work_order=wo, item=item, operation=step.operation,
            payload={'qty_good': qty_good, 'qty_scrap': qty_scrap,
                     'note': note},
        )
        _log_event(
            session, user.get('id'), 'ITEM_DONE',
            work_order=wo, item=item,
            payload={'qty_good': qty_good},
        )

    _recompute_work_order(session, wo)
    return step


def _recompute_work_order(session: Session, wo: WorkOrder) -> None:
    """Пересчитывает qty_done / qty_scrap наряда и закрывает его, если всё готово."""
    items = list(wo.items)
    wo.qty_done = sum(i.qty_good or 0 for i in items)
    wo.qty_scrap = sum(i.qty_scrap or 0 for i in items)
    all_finished = items and all(
        i.status in (WorkOrderItemStatus.DONE, WorkOrderItemStatus.SCRAP)
        for i in items
    )
    if all_finished and wo.status not in (WorkOrderStatus.DONE,
                                          WorkOrderStatus.CANCELED):
        wo.status = WorkOrderStatus.DONE
        wo.closed_at = datetime.now()
        _log_event(
            session, None, 'WO_DONE',
            work_order=wo,
            payload={'qty_done': wo.qty_done, 'qty_scrap': wo.qty_scrap},
        )


# ────────────────────────────────────────────────────────────────────────────
# 4. Проблемы в производстве
# ────────────────────────────────────────────────────────────────────────────

def open_issue(
    session: Session,
    *,
    user: dict,
    work_order_id: int,
    kind: IssueKind,
    severity: IssueSeverity,
    title: str,
    description: Optional[str] = None,
    work_order_item_id: Optional[int] = None,
    workshop_id: Optional[int] = None,
    operation_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    blocks_production: bool = False,
) -> ProductionIssue:
    _check_role(user, ROLE_ISSUE_OPEN, 'открытие проблемы')
    if not title.strip():
        raise ProductionError('Укажите краткое описание проблемы.')

    wo = session.get(WorkOrder, work_order_id)
    if wo is None:
        raise ProductionError('Наряд не найден.')

    issue = ProductionIssue(
        kind=kind,
        severity=severity,
        title=title.strip(),
        description=description,
        work_order_id=wo.id,
        work_order_item_id=work_order_item_id,
        workshop_id=workshop_id,
        operation_id=operation_id,
        status=IssueStatus.OPEN,
        opened_by=user.get('id'),
        opened_at=datetime.now(),
        assignee_id=assignee_id,
        blocks_production=blocks_production,
    )
    session.add(issue)

    if blocks_production and wo.status not in (
        WorkOrderStatus.DONE, WorkOrderStatus.CANCELED
    ):
        wo.status = WorkOrderStatus.ON_HOLD
        _log_event(
            session, user.get('id'), 'WO_ON_HOLD',
            work_order=wo,
            payload={'reason': title, 'kind': kind.name},
        )

    session.flush()
    _log_event(
        session, user.get('id'), 'ISSUE_OPENED',
        work_order=wo,
        payload={'issue_id': issue.id, 'kind': kind.name,
                 'severity': severity.name, 'title': title,
                 'blocks': blocks_production},
    )

    # A6: уведомление ответственному, если он назначен и не сам открыл проблему.
    if assignee_id and assignee_id != user.get('id'):
        try:
            from .notifications import notify_user
            notify_user(
                session,
                user_id=assignee_id,
                kind='ISSUE_ASSIGNED',
                title=f'Назначена проблема: {title.strip()}',
                body=(
                    f'Тип: {kind.value}\nНаряд: {wo.number}\n'
                    f'Серьёзность: {severity.value}'
                    + (f'\nОписание: {description}' if description else '')
                ),
                related_issue_id=issue.id,
                related_work_order_id=wo.id,
            )
        except Exception as e:  # noqa: BLE001
            from utils.logger import get_logger
            get_logger(__name__).debug('skip ISSUE_ASSIGNED: %s', e)
    _audit.log_change_session(session, user_id=user.get('id'), entity_type='ProductionIssue',
                              entity_id=issue.id, action='create',
                              description=f'Проблема: {title.strip()}')
    return issue


def acknowledge_issue(session: Session, *, user: dict, issue_id: int) -> ProductionIssue:
    issue = session.get(ProductionIssue, issue_id)
    if issue is None:
        raise ProductionError('Проблема не найдена.')
    if issue.status != IssueStatus.OPEN:
        return issue
    issue.status = IssueStatus.ACKNOWLEDGED
    if issue.assignee_id is None:
        issue.assignee_id = user.get('id')
    _log_event(
        session, user.get('id'), 'ISSUE_ACK',
        work_order=issue.work_order,
        payload={'issue_id': issue.id},
    )
    return issue


def resolve_issue(
    session: Session,
    *,
    user: dict,
    issue_id: int,
    resolution: str,
) -> ProductionIssue:
    _check_role(user, ROLE_ISSUE_RESOLVE, 'закрытие проблемы')
    if not resolution.strip():
        raise ProductionError('Укажите, как именно проблема была решена.')

    issue = session.get(ProductionIssue, issue_id)
    if issue is None:
        raise ProductionError('Проблема не найдена.')
    if issue.status == IssueStatus.RESOLVED:
        return issue

    issue.status = IssueStatus.RESOLVED
    issue.resolved_by = user.get('id')
    issue.resolved_at = datetime.now()
    issue.resolution = resolution.strip()

    # Если эта проблема была блокирующей и других блокирующих больше нет —
    # снимаем наряд с ON_HOLD.
    wo = issue.work_order
    other_blockers = [
        i for i in wo.issues
        if i.id != issue.id and i.blocks_production
        and i.status not in (IssueStatus.RESOLVED, IssueStatus.CANCELED)
    ]
    if (issue.blocks_production and not other_blockers
            and wo.status == WorkOrderStatus.ON_HOLD):
        # Возвращаем в IN_PROGRESS, если есть начатые партии,
        # иначе REGISTERED. Если ни одна партия не имеет шагов — оставляем как было.
        any_in_progress = any(
            it.status == WorkOrderItemStatus.IN_PROGRESS for it in wo.items
        )
        wo.status = (WorkOrderStatus.IN_PROGRESS if any_in_progress
                     else WorkOrderStatus.REGISTERED)
        _log_event(
            session, user.get('id'), 'WO_RESUMED',
            work_order=wo,
            payload={'after_issue_id': issue.id},
        )

    _log_event(
        session, user.get('id'), 'ISSUE_CLOSED',
        work_order=wo,
        payload={'issue_id': issue.id, 'resolution': issue.resolution},
    )

    # A6: уведомить открывшего проблему о её решении.
    if issue.opened_by and issue.opened_by != user.get('id'):
        try:
            from .notifications import notify_user
            notify_user(
                session,
                user_id=issue.opened_by,
                kind='ISSUE_RESOLVED',
                title=f'Решена проблема: {issue.title}',
                body=f'Резолюция: {issue.resolution}',
                related_issue_id=issue.id,
                related_work_order_id=wo.id,
            )
        except Exception as e:  # noqa: BLE001
            from utils.logger import get_logger
            get_logger(__name__).debug('skip ISSUE_RESOLVED: %s', e)
    return issue


# ────────────────────────────────────────────────────────────────────────────
# 5. Отчёты — простые SQL-агрегаты
# ────────────────────────────────────────────────────────────────────────────

def wip_by_workshop(session: Session) -> list[dict]:
    """WIP-сводка: что сейчас в работе на каждом участке."""
    result: list[dict] = []
    workshops = (
        session.query(Workshop)
        .filter(Workshop.is_active.is_(True))
        .order_by(Workshop.sort_order, Workshop.id)
        .all()
    )
    for ws in workshops:
        items = (
            session.query(WorkOrderItem)
            .filter(WorkOrderItem.current_workshop_id == ws.id)
            .filter(WorkOrderItem.status.in_((
                WorkOrderItemStatus.WAITING,
                WorkOrderItemStatus.IN_PROGRESS,
            )))
            .all()
        )
        result.append({
            'workshop_id': ws.id,
            'workshop_code': ws.code,
            'workshop_name': ws.name,
            'items_count': len(items),
            'qty_total': sum(i.qty for i in items),
            'in_progress': sum(1 for i in items
                               if i.status == WorkOrderItemStatus.IN_PROGRESS),
            'waiting': sum(1 for i in items
                           if i.status == WorkOrderItemStatus.WAITING),
        })
    return result


def open_issues_summary(session: Session) -> list[dict]:
    """Открытые проблемы сгруппированы по типу."""
    issues = (
        session.query(ProductionIssue)
        .filter(ProductionIssue.status.in_((
            IssueStatus.OPEN, IssueStatus.ACKNOWLEDGED,
        )))
        .all()
    )
    by_kind: dict[str, dict] = {}
    for i in issues:
        k = i.kind.value
        if k not in by_kind:
            by_kind[k] = {'kind': k, 'count': 0, 'blockers': 0}
        by_kind[k]['count'] += 1
        if i.blocks_production:
            by_kind[k]['blockers'] += 1
    return list(by_kind.values())


# ────────────────────────────────────────────────────────────────────────────
# 6. Возврат партии на доработку (REWORK)
# ────────────────────────────────────────────────────────────────────────────

def rework_partition(
    session: Session,
    *,
    user: dict,
    item_id: int,
    reason: str,
    target_seq: Optional[int] = None,
) -> RouteStep:
    """Возвращает партию на доработку — на предыдущую (или указанную) операцию.

    Поведение:
        - текущий шаг (PENDING/IN_PROGRESS/REWORK) сбрасывается в PENDING
          и перемещается «на потом» — ничего не теряется,
        - предыдущий шаг (DONE) переводится в статус REWORK и считается
          текущим: ``current_operation_id`` партии указывает на него,
        - партия переводится в WAITING (готова к повторному запуску),
        - наряд, если был DONE, возвращается в IN_PROGRESS (на доработке),
        - в журнал пишется событие REWORK_INITIATED с причиной.

    ``target_seq`` — на какой именно шаг откатить (по seq). Если не задан,
    откатываемся на ближайший предыдущий DONE.
    """
    _check_role(user, ROLE_REWORK, 'возврат на доработку')
    if not (reason or '').strip():
        raise ProductionError('Укажите причину возврата на доработку.')

    item = session.get(WorkOrderItem, item_id)
    if item is None:
        raise ProductionError('Партия не найдена.')

    wo = item.work_order
    if wo.status == WorkOrderStatus.CANCELED:
        raise ProductionError('Наряд отменён, доработка невозможна.')

    steps = sorted(item.route_steps, key=lambda s: s.seq)
    if not steps:
        raise ProductionError('У партии нет шагов маршрута.')

    cur = _current_step(item)
    cur_seq = cur.seq if cur is not None else (steps[-1].seq + 1)

    # Подбираем шаг, на который откатываемся
    if target_seq is not None:
        target = next((s for s in steps if s.seq == target_seq), None)
        if target is None:
            raise ProductionError(
                f'Шаг #{target_seq} не найден в маршруте партии.')
        if target.status != RouteStepStatus.DONE:
            raise ProductionError(
                f'Шаг #{target_seq} ещё не выполнен — на него нельзя вернуть.')
    else:
        done_before = [s for s in steps
                       if s.seq < cur_seq and s.status == RouteStepStatus.DONE]
        if not done_before:
            raise ProductionError(
                'Нет предыдущей выполненной операции, на которую можно вернуть.')
        target = done_before[-1]

    # Если был активный шаг — сбрасываем его в PENDING (он будет выполняться
    # повторно после rework). Сохраняем заметки/количества, но снимаем started/finished.
    if cur is not None and cur.status != RouteStepStatus.PENDING:
        cur.status = RouteStepStatus.PENDING
        cur.started_at = None
        cur.finished_at = None
        cur.qty_good = 0
        cur.qty_scrap = 0
        cur.worker_user_id = None

    # Переоткрываем целевой шаг в режиме REWORK
    target.status = RouteStepStatus.REWORK
    target.finished_at = None  # снимаем флаг «закрыт»

    item.status = WorkOrderItemStatus.WAITING
    item.current_operation_id = target.operation_id
    if target.workshop_id:
        item.current_workshop_id = target.workshop_id

    # Если наряд уже был DONE, возвращаем его в работу
    if wo.status == WorkOrderStatus.DONE:
        wo.status = WorkOrderStatus.IN_PROGRESS
        wo.closed_at = None

    _log_event(
        session, user.get('id'), 'REWORK_INITIATED',
        work_order=wo, item=item,
        operation=target.operation,
        payload={'reason': reason.strip(),
                 'from_seq': cur_seq,
                 'to_seq': target.seq},
    )
    return target


# ────────────────────────────────────────────────────────────────────────────
# 7. Отмена наряда
# ────────────────────────────────────────────────────────────────────────────

def cancel_work_order(
    session: Session,
    *,
    user: dict,
    work_order_id: int,
    reason: str,
) -> WorkOrder:
    """Отменяет наряд: помечает наряд и все недоделанные партии как CANCELED.

    Уже завершённые партии (DONE/SCRAP) сохраняют свой статус —
    их количество остаётся в qty_done.

    Для отмены требуется обязательная причина. Событие журналируется как
    ORDER_CANCELLED. Доступно только ролям ``admin`` и ``technologist``.
    """
    _check_role(user, ROLE_CANCEL, 'отмена наряда')
    if not (reason or '').strip():
        raise ProductionError('Укажите причину отмены наряда.')

    wo = session.get(WorkOrder, work_order_id)
    if wo is None:
        raise ProductionError('Наряд не найден.')

    if wo.status in (WorkOrderStatus.CANCELED, WorkOrderStatus.DONE):
        raise ProductionError(
            f'Наряд в статусе «{wo.status.value}», его уже нельзя отменить.')

    # Отменяем все партии, которые ещё не завершены и не в браке.
    canceled_items: list[int] = []
    for item in wo.items:
        if item.status in (WorkOrderItemStatus.DONE, WorkOrderItemStatus.SCRAP):
            continue
        item.status = WorkOrderItemStatus.SCRAP  # «Брак» — признак закрытия
        # Помечаем невыполненные шаги как пропущенные
        for step in item.route_steps:
            if step.status in (RouteStepStatus.PENDING,
                               RouteStepStatus.IN_PROGRESS,
                               RouteStepStatus.REWORK):
                step.status = RouteStepStatus.SKIPPED
        canceled_items.append(item.id)

    wo.status = WorkOrderStatus.CANCELED
    wo.closed_at = datetime.now()

    _log_event(
        session, user.get('id'), 'ORDER_CANCELLED',
        work_order=wo,
        payload={'reason': reason.strip(),
                 'canceled_items': canceled_items,
                 'qty_done_so_far': wo.qty_done or 0},
    )
    return wo


def work_order_progress(session: Session, work_order_id: int) -> dict:
    """Сводка прогресса по наряду: где партии, сколько готово/брака, проблемы."""
    wo = session.get(WorkOrder, work_order_id)
    if wo is None:
        raise ProductionError('Наряд не найден.')

    items_info = []
    for item in wo.items:
        cur_step = _current_step(item)
        items_info.append({
            'item_id': item.id,
            'serial': item.serial,
            'barcode': item.barcode,
            'qty': item.qty,
            'qty_good': item.qty_good or 0,
            'qty_scrap': item.qty_scrap or 0,
            'status': item.status.value,
            'workshop': item.current_workshop.name if item.current_workshop else '—',
            'current_op_seq': cur_step.seq if cur_step else None,
            'current_op_name': cur_step.operation.name if cur_step else None,
        })

    return {
        'wo_id': wo.id,
        'number': wo.number,
        'status': wo.status.value,
        'qty_total': wo.qty_total,
        'qty_done': wo.qty_done,
        'qty_scrap': wo.qty_scrap,
        'items': items_info,
        'open_issues': sum(
            1 for i in wo.issues
            if i.status in (IssueStatus.OPEN, IssueStatus.ACKNOWLEDGED)
        ),
    }
