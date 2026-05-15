"""Email notifications for critical alerts (scrap, downtime, overdue).

Configure SMTP in settings.json:
  {"smtp_host": "...", "smtp_port": 587, "smtp_user": "...",
   "smtp_password": "...", "smtp_from": "...", "alert_recipients": "..."}
"""

from __future__ import annotations

import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _get_config():
    from modules import settings as us
    return {
        'host': us.get('smtp_host', ''),
        'port': int(us.get('smtp_port', 587)),
        'user': us.get('smtp_user', ''),
        'password': us.get('smtp_password', ''),
        'from': us.get('smtp_from', 'atpp@uzga.ru'),
        'recipients': us.get('alert_recipients', ''),
    }


def send_alert(subject: str, body: str, recipients: str = ''):
    """Send an email alert. Runs in background thread — non-blocking."""

    def _send():
        cfg = _get_config()
        if not cfg['host']:
            return  # SMTP not configured

        to_list = [r.strip() for r in
                   (recipients or cfg['recipients']).split(',') if r.strip()]
        if not to_list:
            return

        msg = MIMEMultipart()
        msg['From'] = cfg['from']
        msg['To'] = ', '.join(to_list)
        msg['Subject'] = f'[ATPP] {subject}'

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        try:
            with smtplib.SMTP(cfg['host'], cfg['port'], timeout=10) as s:
                s.starttls()
                if cfg['user']:
                    s.login(cfg['user'], cfg['password'])
                s.sendmail(cfg['from'], to_list, msg.as_string())
        except Exception:
            pass  # Email is non-critical

    threading.Thread(target=_send, daemon=True).start()


def alert_scrap(order_number: str, part: str, qty: int, reason: str):
    send_alert(
        f'Брак: {order_number} — {part}',
        f'Заказ: {order_number}\nДеталь: {part}\n'
        f'Количество брака: {qty} шт\nПричина: {reason}'
    )


def alert_overdue(order_number: str, due_date: str, days_overdue: int):
    send_alert(
        f'Просрочка: {order_number} ({days_overdue} дн.)',
        f'Заказ {order_number} просрочен на {days_overdue} дней.\n'
        f'Срок: {due_date}\nТребуется эскалация.'
    )


def alert_downtime(equipment: str, reason: str):
    send_alert(
        f'Простой: {equipment}',
        f'Оборудование {equipment} простаивает.\nПричина: {reason}'
    )
