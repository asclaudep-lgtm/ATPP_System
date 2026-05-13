"""
v9-10: Метрологическая поверка.

API над таблицами ``instruments`` / ``calibrations``.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import List, Optional

from sqlalchemy import or_, and_

from database.models import (
    Instrument, Calibration, InstrumentStatus,
)


# Алерт за N дней до окончания срока поверки.
ALERT_WINDOW_DAYS = 30


def add_calibration(
    session,
    *,
    instrument_id: int,
    performed_at: date,
    organization: str = '',
    certificate_no: str = '',
    cert_path: Optional[str] = None,
    result: str = 'годен',
    notes: str = '',
    created_by: Optional[int] = None,
) -> Calibration:
    """Зарегистрировать поверку: обновить last/next даты у Instrument."""
    inst: Instrument = session.get(Instrument, instrument_id)
    if inst is None:
        raise ValueError(f'Instrument #{instrument_id} not found')

    cal = Calibration(
        instrument_id=instrument_id,
        performed_at=performed_at,
        organization=organization or None,
        certificate_no=certificate_no or None,
        cert_path=cert_path or None,
        result=result or None,
        notes=notes or None,
        created_by=created_by,
    )
    months = int(inst.cal_interval_months or 12)
    next_due = _add_months(performed_at, months)
    cal.next_due = next_due

    inst.last_cal_date = performed_at
    inst.next_cal_date = next_due
    if result and result.lower().startswith('не'):
        inst.status = InstrumentStatus.EXPIRED
    else:
        inst.status = InstrumentStatus.ACTIVE

    session.add(cal)
    session.flush()
    return cal


def _add_months(d: date, months: int) -> date:
    """Прибавить N месяцев к дате (без dateutil)."""
    y, m = d.year, d.month + months
    while m > 12:
        m -= 12
        y += 1
    # Корректируем день, если такого нет в месяце (31→30 и т.д.).
    day = d.day
    while True:
        try:
            return date(y, m, day)
        except ValueError:
            day -= 1


def instruments_due_soon(session, *, days: int = ALERT_WINDOW_DAYS
                         ) -> List[Instrument]:
    """СИ, у которых поверка истекает в ближайшие N дней или уже просрочена."""
    today = date.today()
    horizon = today + timedelta(days=days)
    rows = (session.query(Instrument)
            .filter(Instrument.status != InstrumentStatus.WRITE_OFF)
            .filter(or_(Instrument.next_cal_date <= horizon,
                        Instrument.next_cal_date.is_(None)))
            .order_by(Instrument.next_cal_date.asc().nulls_first())
            .all())
    return rows


def refresh_statuses(session) -> int:
    """Пересчитать статусы по дате next_cal_date.

    Возвращает количество СИ, у которых статус изменился.
    """
    today = date.today()
    changed = 0
    for inst in session.query(Instrument).all():
        if inst.status == InstrumentStatus.WRITE_OFF:
            continue
        new_status = inst.status
        if inst.next_cal_date and inst.next_cal_date < today:
            new_status = InstrumentStatus.EXPIRED
        elif inst.next_cal_date and inst.next_cal_date >= today \
                and inst.status == InstrumentStatus.EXPIRED:
            new_status = InstrumentStatus.ACTIVE
        if new_status != inst.status:
            inst.status = new_status
            changed += 1
    return changed


def check_due_alerts(session, *, days_warning: int = 30) -> List[dict]:
    """Проверить приборы с истекающей поверкой.

    Возвращает список dict с полями: inventory_no, name, next_cal_date,
    days_left, severity ('warning' — жёлтый / 'expired' — красный).
    """
    today = date.today()
    deadline = today + timedelta(days=days_warning)
    alerts: List[dict] = []

    instruments = session.query(Instrument).filter(
        Instrument.status != InstrumentStatus.WRITE_OFF,
        Instrument.next_cal_date.isnot(None),
    ).order_by(Instrument.next_cal_date).all()

    for inst in instruments:
        nd = inst.next_cal_date
        if nd is None:
            continue
        days_left = (nd - today).days
        if days_left < 0:
            alerts.append({
                'inventory_no': inst.inventory_no,
                'name': inst.name,
                'next_cal_date': nd.isoformat(),
                'days_left': days_left,
                'severity': 'expired',
                'message': f'Поверка просрочена на {-days_left} дн.',
            })
        elif days_left <= days_warning:
            alerts.append({
                'inventory_no': inst.inventory_no,
                'name': inst.name,
                'next_cal_date': nd.isoformat(),
                'days_left': days_left,
                'severity': 'warning',
                'message': f'Поверка через {days_left} дн.',
            })
    return alerts


def send_metrology_alerts(session):
    """Отправить алерты по СИ с истекающей поверкой через alerts.py."""
    alerts = check_due_alerts(session, days_warning=30)
    if not alerts:
        return 0

    from modules.alerts import dispatch_alert
    expired = [a for a in alerts if a['severity'] == 'expired']
    warning = [a for a in alerts if a['severity'] == 'warning']

    text_parts = []
    if expired:
        text_parts.append(
            f"🔴 ПРОСРОЧЕНО ({len(expired)}):\n" +
            "\n".join(f"  • {a['inventory_no']} {a['name']} — {a['message']}"
                      for a in expired[:5]))
    if warning:
        text_parts.append(
            f"🟡 ИСТЕКАЕТ ({len(warning)}):\n" +
            "\n".join(f"  • {a['inventory_no']} {a['name']} — {a['message']}"
                      for a in warning[:5]))

    dispatch_alert(
        kind='METROLOGY_DUE',
        title=f'Метрология: {len(expired)} просрочено, {len(warning)} истекает',
        body='\n\n'.join(text_parts),
    )
    return len(alerts)
