"""PDO module — производственные заказы, передача между отделами, подпись МТП."""

from datetime import datetime, date
from typing import Optional, List

from database.models import (
    ProductionOrder, PDOHandoff, MTPSignoff, PDOStatus,
    TechProcess, Product, TPStatus, User,
)


def next_order_number(session) -> str:
    """Generate next order number: PDO-YYYY-001."""
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
    customer_order_no: str = '',
    priority: int = 3,
    created_by: int,
    notes: str = '',
) -> ProductionOrder:
    """Create a new PDO order. Checks if TP exists for the product."""

    tp = session.query(TechProcess).filter(
        TechProcess.product_id == product_id,
        TechProcess.is_deleted == False,
        TechProcess.status.in_([TPStatus.APPROVED, TPStatus.DRAFT]),
    ).first()

    tp_required = tp is None or tp.status != TPStatus.APPROVED
    initial_status = (PDOStatus.WITH_TECHNOLOGIST if tp_required
                      else PDOStatus.READY_FOR_SHOP)

    order = ProductionOrder(
        number=next_order_number(session),
        product_id=product_id,
        tech_process_id=tp.id if tp else None,
        qty=qty,
        due_date=due_date,
        priority=priority,
        customer=customer,
        customer_order_no=customer_order_no,
        status=initial_status,
        created_by=created_by,
        tp_required=tp_required,
        notes=notes,
    )
    session.add(order)
    session.flush()

    if tp_required:
        handoff_to_technologist(session, order.id, created_by,
                                'Требуется разработка/проверка ТП и подпись МТП')

    return order


def handoff_to_technologist(session, order_id: int, transferred_by: int,
                             comment: str = '') -> PDOHandoff:
    """Assign order to technologist for TP/MTP preparation."""
    order = session.query(ProductionOrder).get(order_id)
    if order is None:
        raise ValueError(f'Order #{order_id} not found')

    order.status = PDOStatus.WITH_TECHNOLOGIST
    # Find a technologist
    tech = session.query(User).filter(User.role == 'technologist',
                                        User.is_active == True).first()
    if tech:
        order.technologist_id = tech.id

    handoff = PDOHandoff(
        order_id=order_id,
        from_dept='ПДО',
        to_dept='Технолог',
        transferred_by=transferred_by,
        comment=comment,
    )
    session.add(handoff)
    session.flush()

    # Push alert
    _send_push('technologist', 'Новый заказ на ТП',
               f'Заказ {order.number} ожидает подготовки ТП/МТП')

    return handoff


def sign_mtp(session, *, order_id: int, tech_process_id: int,
             signed_by: int, comment: str = '') -> MTPSignoff:
    """Technologist signs the MTP — order can now go to shop."""

    order = session.query(ProductionOrder).get(order_id)
    if order is None:
        raise ValueError(f'Order #{order_id} not found')

    tp = session.query(TechProcess).get(tech_process_id)
    if tp is None:
        raise ValueError(f'TP #{tech_process_id} not found')

    # Add technologist signature via workflow
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


def release_to_shop(session, *, order_id: int, shop: str,
                     released_by: int) -> ProductionOrder:
    """PDO releases the order to the workshop."""

    order = session.query(ProductionOrder).get(order_id)
    if order is None:
        raise ValueError(f'Order #{order_id} not found')

    if order.status not in (PDOStatus.MTP_SIGNED, PDOStatus.READY_FOR_SHOP):
        raise ValueError(
            f'Order #{order_id} cannot be released: '
            f'MTP not signed (status={order.status.value})')

    order.status = PDOStatus.IN_SHOP
    order.released_to_shop = shop
    order.released_at = datetime.now()
    order.released_by = released_by

    handoff = PDOHandoff(
        order_id=order_id,
        from_dept='Технолог',
        to_dept=f'Цех ({shop})',
        doc_package='МК, ОК, МТП, ВО, ВМ',
        transferred_by=released_by,
    )
    session.add(handoff)
    session.flush()

    _send_push('shop', 'Заказ передан в цех',
               f'Заказ {order.number} → цех {shop}')

    return order


def accept_in_shop(session, *, order_id: int, accepted_by: int) -> PDOHandoff:
    """Shop master accepts the order."""
    order = session.query(ProductionOrder).get(order_id)
    if order is None:
        raise ValueError(f'Order #{order_id} not found')
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
    """Send completed order to QC."""
    order = session.query(ProductionOrder).get(order_id)
    order.status = PDOStatus.QC

    handoff = PDOHandoff(
        order_id=order_id,
        from_dept='Цех',
        to_dept='ОТК',
        transferred_by=transferred_by,
    )
    session.add(handoff)
    session.flush()

    _send_push('qc', 'Заказ на контроле',
               f'Заказ {order.number} передан в ОТК')
    return handoff


def close_order(session, *, order_id: int, qty_done: int = 0,
                qty_scrap: int = 0) -> ProductionOrder:
    """QC accepts → order closed."""
    order = session.query(ProductionOrder).get(order_id)
    order.status = PDOStatus.CLOSED
    order.qty_done = qty_done
    order.qty_scrap = qty_scrap
    order.closed_at = datetime.now()

    handoff = PDOHandoff(
        order_id=order_id,
        from_dept='ОТК',
        to_dept='Склад',
        status='Принят',
    )
    session.add(handoff)
    session.flush()
    return order


def list_orders_by_status(session, status: PDOStatus = None,
                           limit: int = 100) -> List[ProductionOrder]:
    """List orders, optionally filtered by status."""
    q = session.query(ProductionOrder).order_by(
        ProductionOrder.priority, ProductionOrder.created_at)
    if status:
        q = q.filter(ProductionOrder.status == status)
    return q.limit(limit).all()


def get_order_detail(session, order_id: int) -> dict:
    """Get full order detail with handoff history."""
    order = session.query(ProductionOrder).get(order_id)
    if order is None:
        return {}

    handoffs = session.query(PDOHandoff).filter(
        PDOHandoff.order_id == order_id,
    ).order_by(PDOHandoff.created_at).all()

    signoffs = session.query(MTPSignoff).filter(
        MTPSignoff.order_id == order_id,
    ).order_by(MTPSignoff.signed_at.desc()).all()

    return {
        'id': order.id,
        'number': order.number,
        'product': order.product.designation if order.product else '',
        'product_name': order.product.name if order.product else '',
        'qty': order.qty,
        'due_date': str(order.due_date) if order.due_date else None,
        'priority': order.priority,
        'customer': order.customer or '',
        'status': order.status.value,
        'tp_required': order.tp_required,
        'technologist': (order.technologist.full_name
                         if order.technologist else 'Не назначен'),
        'mtp_signed': order.mtp_signed_at is not None,
        'released_to_shop': order.released_to_shop or '',
        'qty_done': order.qty_done,
        'handoffs': [{
            'from': h.from_dept,
            'to': h.to_dept,
            'status': h.status,
            'created_at': str(h.created_at) if h.created_at else None,
            'comment': h.comment or '',
        } for h in handoffs],
        'signoffs': [{
            'signed_by': s.signer.full_name if s.signer else '?',
            'signed_at': str(s.signed_at),
            'comment': s.comment or '',
        } for s in signoffs],
    }


def _send_push(target: str, title: str, message: str):
    """Send push alert — non-critical, failure is silent."""
    try:
        from web.server import send_push_alert
        send_push_alert(target, title, message)
    except Exception:
        pass
