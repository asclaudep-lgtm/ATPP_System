"""PDO module v3 — реальный процесс УЗГА: ПЭУ→ОМТС→Тех.отдел→Зам.Тех.Дир→Цех."""

from datetime import datetime, date
from typing import Optional, List

from database.models import (
    ProductionOrder, PDOHandoff, MTPSignoff, PDOStatus,
    NomenclatureItem, ServiceMemo,
    TechProcess, Product, TPStatus, User,
)

import logging
_logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Order lifecycle
# ═══════════════════════════════════════════════════════════════════


def next_order_number(session) -> str:
    year = datetime.now().year
    count = session.query(ProductionOrder).filter(
        ProductionOrder.number.like(f'PDO-{year}-%')
    ).count()
    return f'PDO-{year}-{count + 1:03d}'


def create_order(
    session, *,
    product_id: int,
    qty: int,
    due_date: date,
    customer: str = '',
    aircraft_type: str = '',
    work_scope: str = '',
    priority: int = 3,
    created_by: int,
    nomenclature: list = None,
    notes: str = '',
) -> ProductionOrder:
    """Create a PDO order with optional nomenclature items."""
    tp = session.query(TechProcess).filter(
        TechProcess.product_id == product_id,
        TechProcess.is_deleted == False,
        TechProcess.status == TPStatus.APPROVED,
    ).first()

    order = ProductionOrder(
        number=next_order_number(session),
        product_id=product_id,
        tech_process_id=tp.id if tp else None,
        qty=qty,
        due_date=due_date,
        priority=priority,
        customer=customer,
        aircraft_type=aircraft_type,
        work_scope=work_scope,
        status=PDOStatus.NEW,
        created_by=created_by,
        tp_required=tp is None,
        notes=notes,
    )
    session.add(order)
    session.flush()

    if nomenclature:
        for item in nomenclature:
            ni = NomenclatureItem(
                order_id=order.id,
                designation=item.get('designation', ''),
                name=item.get('name', ''),
                qty=item.get('qty', 1),
            )
            session.add(ni)
        session.flush()

    return order


# ═══════════════════════════════════════════════════════════════════
# Этап ОМТС: проработка материала
# ═══════════════════════════════════════════════════════════════════


def omts_start_review(session, *, order_id: int, memo_number: str = '',
                       issued_by: int = None, content: str = '') -> ServiceMemo:
    """ОМТС начинает проработку — проверка наличия материала."""
    order = session.get(ProductionOrder, order_id)
    if order is None:
        raise ValueError(f'Order #{order_id} not found')

    order.status = PDOStatus.OMTS_REVIEW
    if memo_number:
        order.omts_memo_no = memo_number

    memo = ServiceMemo(
        order_id=order_id,
        memo_type='У',
        memo_number=memo_number,
        from_dept='ОМТС',
        issued_by=issued_by,
        content=content or 'Запрос на проработку материала',
    )
    session.add(memo)
    session.flush()

    _send_push('omts', 'Новый заказ на проработку',
               f'Заказ {order.number} — проверка материала')
    return memo


# ═══════════════════════════════════════════════════════════════════
# Этап Тех.отдел: проверка КД и feasibility
# ═══════════════════════════════════════════════════════════════════


def tech_dept_review(session, *, order_id: int) -> ProductionOrder:
    """Передать заказ в тех.отдел на проверку КД."""
    order = session.get(ProductionOrder, order_id)
    order.status = PDOStatus.TECH_DEPT

    handoff = PDOHandoff(
        order_id=order_id,
        from_dept='ОМТС',
        to_dept='Тех.отдел',
        comment='Передан на проверку КД и feasibility',
    )
    session.add(handoff)
    session.flush()

    _send_push('tech_dept', 'Заказ на проверку КД',
               f'Заказ {order.number} — проверка конструкторской документации')
    return order


def set_feasibility(session, *, item_id: int, feasible: bool,
                     kd_ready: bool = False, material_name: str = '',
                     tech_notes: str = '') -> NomenclatureItem:
    """Тех.отдел: отметить позицию как возможную/невозможную к изготовлению."""
    item = session.get(NomenclatureItem, item_id)
    if item is None:
        raise ValueError(f'NomenclatureItem #{item_id} not found')

    item.tech_feasible = feasible
    item.kd_ready = kd_ready
    if material_name:
        item.material_name = material_name
    if tech_notes:
        item.tech_notes = tech_notes
    session.flush()
    return item


def check_all_feasible(session, *, order_id: int) -> bool:
    """Проверить: все ли позиции заказа признаны возможными к изготовлению."""
    items = session.query(NomenclatureItem).filter(
        NomenclatureItem.order_id == order_id).all()
    if not items:
        return True
    return all(i.tech_feasible is True for i in items)


def any_not_feasible(session, *, order_id: int) -> bool:
    """Есть ли хотя бы одна позиция, которую невозможно изготовить."""
    items = session.query(NomenclatureItem).filter(
        NomenclatureItem.order_id == order_id).all()
    return any(i.tech_feasible is False for i in items)


def complete_tech_review(session, *, order_id: int) -> ProductionOrder:
    """Завершить проверку тех.отдела: если всё '+' → на утверждение, иначе → отказ."""
    order = session.get(ProductionOrder, order_id)

    if any_not_feasible(session, order_id=order_id):
        order.status = PDOStatus.NOT_FEASIBLE
    else:
        order.status = PDOStatus.FEASIBLE
    session.flush()
    return order


# ═══════════════════════════════════════════════════════════════════
# Этап Зам.Тех.Дир: утверждение и служебная записка на изготовление
# ═══════════════════════════════════════════════════════════════════


def deputy_approve(session, *, order_id: int, memo_number: str = '',
                    issued_by: int = None, content: str = '') -> ServiceMemo:
    """Зам.Тех.Дир утверждает заказ и выпускает записку на изготовление."""
    order = session.get(ProductionOrder, order_id)
    if order is None:
        raise ValueError(f'Order #{order_id} not found')

    order.status = PDOStatus.DEPUTY_APPROVAL
    if memo_number:
        order.deputy_memo_no = memo_number

    memo = ServiceMemo(
        order_id=order_id,
        memo_type='П',
        memo_number=memo_number,
        from_dept='Зам.Тех.Дир',
        issued_by=issued_by,
        content=content or 'Служебная записка на изготовление',
    )
    session.add(memo)
    session.flush()
    return memo


def approve_order(session, *, order_id: int) -> ProductionOrder:
    """Финальное утверждение: заказ готов к передаче в цех."""
    order = session.get(ProductionOrder, order_id)
    order.status = PDOStatus.APPROVED

    handoff = PDOHandoff(
        order_id=order_id,
        from_dept='Зам.Тех.Дир',
        to_dept='Производство',
        comment='Утверждён. Готов к созданию наряда.',
    )
    session.add(handoff)
    session.flush()

    _send_push('pdo', 'Заказ утверждён',
               f'Заказ {order.number} утверждён. Можно создавать наряд.')
    return order


# ═══════════════════════════════════════════════════════════════════
# Подпись МТП технологом
# ═══════════════════════════════════════════════════════════════════


def sign_mtp(session, *, order_id: int, tech_process_id: int,
             signed_by: int, comment: str = '') -> MTPSignoff:
    """Технолог подписывает МТП для заказа."""
    order = session.get(ProductionOrder, order_id)
    if order is None:
        raise ValueError(f'Order #{order_id} not found')

    tp = session.get(TechProcess, tech_process_id)
    if tp is None:
        raise ValueError(f'TP #{tech_process_id} not found')

    from modules.workflow import add_signature, try_auto_approve
    from database.models import SignerRole
    add_signature(session, tp_id=tech_process_id,
                  role=SignerRole.CHIEF_TECH.value, user_id=signed_by,
                  comment=f'МТП подписан: {comment}')
    try_auto_approve(session, tp_id=tech_process_id)

    signoff = MTPSignoff(
        order_id=order_id,
        tech_process_id=tech_process_id,
        signed_by=signed_by,
        comment=comment,
    )
    session.add(signoff)
    order.mtp_signed_by = signed_by
    order.mtp_signed_at = datetime.now()
    order.tech_process_id = tech_process_id
    order.tp_required = False
    order.status = PDOStatus.MTP_SIGNED
    session.flush()

    _send_push('pdo', 'МТП подписан',
               f'Технолог подписал МТП для заказа {order.number}')
    return signoff


# ═══════════════════════════════════════════════════════════════════
# Передача в цех (создание WorkOrder)
# ═══════════════════════════════════════════════════════════════════


def release_to_shop(session, *, order_id: int, shop: str,
                     released_by: int) -> ProductionOrder:
    """Передать заказ в цех. Создаёт WorkOrder если ещё не создан."""
    order = session.get(ProductionOrder, order_id)
    if order is None:
        raise ValueError(f'Order #{order_id} not found')

    # Создать WorkOrder если ещё нет
    if order.work_order_id is None:
        from database.models import WorkOrder, WorkOrderStatus
        wo = WorkOrder(
            number=f'WO-{order.number}',
            tech_process_id=order.tech_process_id,
            product_id=order.product_id,
            qty_total=order.qty,
            status=WorkOrderStatus.RELEASED,
            due_date=order.due_date,
        )
        session.add(wo)
        session.flush()
        order.work_order_id = wo.id

    order.status = PDOStatus.IN_SHOP
    order.released_to_shop = shop
    order.released_at = datetime.now()
    order.released_by = released_by

    handoff = PDOHandoff(
        order_id=order_id,
        from_dept='ПДО',
        to_dept=f'Цех ({shop})',
        doc_package='Служебная записка на изготовление, МК, ОК, МТП, ВО, ВМ',
        transferred_by=released_by,
    )
    session.add(handoff)
    session.flush()

    _send_push('shop', 'Заказ передан в цех',
               f'Заказ {order.number} → цех {shop}. Наряд {order.work_order_id}')
    return order


# ═══════════════════════════════════════════════════════════════════
# Accept / QC / Close — как раньше
# ═══════════════════════════════════════════════════════════════════


def accept_in_shop(session, *, order_id: int, accepted_by: int) -> PDOHandoff:
    order = session.get(ProductionOrder, order_id)
    order.status = PDOStatus.IN_SHOP
    handoff = session.query(PDOHandoff).filter(
        PDOHandoff.order_id == order_id,
        PDOHandoff.to_dept.like('Цех%'),
    ).order_by(PDOHandoff.created_at.desc()).first()
    if handoff:
        handoff.status = 'Принят'
        handoff.accepted_by = accepted_by
        handoff.accepted_at = datetime.now()
    session.flush()
    return handoff


def send_to_qc(session, *, order_id: int, transferred_by: int) -> PDOHandoff:
    order = session.get(ProductionOrder, order_id)
    order.status = PDOStatus.QC
    handoff = PDOHandoff(
        order_id=order_id, from_dept='Цех', to_dept='ОТК',
        transferred_by=transferred_by,
    )
    session.add(handoff)
    session.flush()
    _send_push('qc', 'Заказ на контроле', f'Заказ {order.number} → ОТК')
    return handoff


def close_order(session, *, order_id: int, qty_done: int = 0,
                qty_scrap: int = 0) -> ProductionOrder:
    order = session.get(ProductionOrder, order_id)
    order.status = PDOStatus.CLOSED
    order.qty_done = qty_done
    order.qty_scrap = qty_scrap
    order.closed_at = datetime.now()
    handoff = PDOHandoff(
        order_id=order_id, from_dept='ОТК', to_dept='Склад',
        status='Принят',
    )
    session.add(handoff)
    session.flush()
    return order


# ═══════════════════════════════════════════════════════════════════
# Queries
# ═══════════════════════════════════════════════════════════════════


def list_orders_by_status(session, status: PDOStatus = None,
                           limit: int = 100) -> List[ProductionOrder]:
    q = session.query(ProductionOrder).order_by(
        ProductionOrder.priority, ProductionOrder.created_at)
    if status:
        q = q.filter(ProductionOrder.status == status)
    return q.limit(limit).all()


def get_nomenclature(session, order_id: int) -> list:
    items = session.query(NomenclatureItem).filter(
        NomenclatureItem.order_id == order_id,
    ).order_by(NomenclatureItem.sort_order).all()
    return [{
        'id': i.id, 'designation': i.designation,
        'name': i.name or '', 'qty': i.qty,
        'kd_ready': i.kd_ready,
        'material_name': i.material_name or '',
        'tech_feasible': i.tech_feasible,
        'tech_notes': i.tech_notes or '',
        'material_ordered': i.material_ordered,
    } for i in items]


def get_memos(session, order_id: int) -> list:
    memos = session.query(ServiceMemo).filter(
        ServiceMemo.order_id == order_id,
    ).order_by(ServiceMemo.issued_at).all()
    return [{
        'id': m.id, 'memo_type': m.memo_type,
        'memo_number': m.memo_number or '',
        'from_dept': m.from_dept or '',
        'content': m.content or '',
        'issued_at': str(m.issued_at) if m.issued_at else '',
    } for m in memos]


def get_order_detail(session, order_id: int) -> dict:
    order = session.get(ProductionOrder, order_id)
    if order is None:
        return {}

    handoffs = session.query(PDOHandoff).filter(
        PDOHandoff.order_id == order_id,
    ).order_by(PDOHandoff.created_at).all()

    return {
        'id': order.id,
        'number': order.number,
        'product': order.product.designation if order.product else '',
        'product_name': order.product.name if order.product else '',
        'qty': order.qty,
        'due_date': str(order.due_date) if order.due_date else None,
        'priority': order.priority,
        'customer': order.customer or '',
        'aircraft_type': order.aircraft_type or '',
        'work_scope': order.work_scope or '',
        'status': order.status.value,
        'tp_required': order.tp_required,
        'technologist': (order.technologist.full_name
                         if order.technologist else 'Не назначен'),
        'mtp_signed': order.mtp_signed_at is not None,
        'omts_memo_no': order.omts_memo_no or '',
        'deputy_memo_no': order.deputy_memo_no or '',
        'released_to_shop': order.released_to_shop or '',
        'work_order_id': order.work_order_id,
        'qty_done': order.qty_done,
        'nomenclature': get_nomenclature(session, order_id),
        'memos': get_memos(session, order_id),
        'handoffs': [{
            'from': h.from_dept, 'to': h.to_dept,
            'status': h.status,
            'created_at': str(h.created_at) if h.created_at else None,
            'comment': h.comment or '',
        } for h in handoffs],
    }


def _send_push(target: str, title: str, message: str):
    try:
        from web.server import send_push_alert
        send_push_alert(target, title, message)
    except Exception:
        _logger.exception("Unhandled error")
