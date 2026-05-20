"""IoT-сбор данных со станков (MQTT collector).

Подписывается на MQTT-топики, парсит JSON-телеметрию и сохраняет
в таблицы MachineStatus / MachineStatusSummary.

Может работать в фоновом потоке внутри desktop-приложения или как
отдельный процесс.  При отсутствии paho-mqtt модуль деградирует —
функции store_telemetry / get_latest_status работают без MQTT.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from threading import Event, Thread
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

# Optional import
try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

from database.models import MachineStatus, MachineStatusSummary


@dataclass
class MachineTelemetry:
    equipment_id: int
    status: str  # running / idle / offline / alarm
    spindle_speed: Optional[float] = None
    feed_rate: Optional[float] = None
    power_consumption: Optional[float] = None
    program_number: Optional[str] = None
    active_operation_id: Optional[int] = None
    work_order_item_id: Optional[int] = None
    reported_at: Optional[datetime] = None


def store_telemetry(session: Session, *,
                    telemetry: MachineTelemetry) -> int:
    """Сохранить одну запись телеметрии в БД.

    Также обновляет MachineStatusSummary для быстрого lookup.
    Возвращает id созданной записи MachineStatus.
    """
    record = MachineStatus(
        equipment_id=telemetry.equipment_id,
        status=telemetry.status,
        spindle_speed=telemetry.spindle_speed,
        feed_rate=telemetry.feed_rate,
        power_consumption=telemetry.power_consumption,
        program_number=telemetry.program_number,
        active_operation_id=telemetry.active_operation_id,
        work_order_item_id=telemetry.work_order_item_id,
        reported_at=telemetry.reported_at or datetime.now(),
        is_simulated=False,
    )
    session.add(record)
    session.flush()

    # Обновить или создать summary
    summary = session.query(MachineStatusSummary).filter(
        MachineStatusSummary.equipment_id == telemetry.equipment_id,
    ).first()
    if summary is None:
        summary = MachineStatusSummary(
            equipment_id=telemetry.equipment_id,
            status=telemetry.status,
            last_update=datetime.now(),
        )
        session.add(summary)
    else:
        summary.status = telemetry.status
        summary.last_update = datetime.now()
        if telemetry.status == 'running':
            summary.uptime_today_min = float(
                summary.uptime_today_min or 0) + 1.0

    session.flush()
    return record.id


def get_latest_status(session: Session, *,
                      equipment_id: int) -> Optional[Dict[str, Any]]:
    """Получить последний статус одного станка."""
    s = session.query(MachineStatusSummary).filter(
        MachineStatusSummary.equipment_id == equipment_id,
    ).first()
    if s is None:
        return None
    return {
        'equipment_id': s.equipment_id,
        'status': s.status,
        'last_update': s.last_update.isoformat() if s.last_update else None,
        'uptime_today_min': s.uptime_today_min,
        'equipment_name': s.equipment.name if s.equipment else '',
    }


def get_all_machine_statuses(session: Session) -> List[Dict[str, Any]]:
    """Получить последний статус всех станков."""
    result = []
    for s in session.query(MachineStatusSummary).all():
        result.append({
            'equipment_id': s.equipment_id,
            'status': s.status,
            'last_update': s.last_update.isoformat() if s.last_update else None,
            'uptime_today_min': s.uptime_today_min,
            'equipment_name': s.equipment.name if s.equipment else '',
        })
    return result


def get_status_history(session: Session, *,
                       equipment_id: int,
                       since: datetime,
                       until: Optional[datetime] = None,
                       limit: int = 1000) -> List[Dict[str, Any]]:
    """История статусов станка за период."""
    q = session.query(MachineStatus).filter(
        MachineStatus.equipment_id == equipment_id,
        MachineStatus.recorded_at >= since,
    ).order_by(MachineStatus.recorded_at.desc())
    if until is not None:
        q = q.filter(MachineStatus.recorded_at <= until)
    records = q.limit(limit).all()
    return [{
        'status': r.status,
        'spindle_speed': r.spindle_speed,
        'feed_rate': r.feed_rate,
        'power': r.power_consumption,
        'program': r.program_number,
        'recorded_at': r.recorded_at.isoformat() if r.recorded_at else None,
        'is_simulated': r.is_simulated,
    } for r in records]


# ──────────────────────────────────────────────────────────────
# MQTT Collector
# ──────────────────────────────────────────────────────────────


class MqttCollector:
    """Фоновый MQTT-коллектор телеметрии.

    Подключается к брокеру, подписывается на топики вида
    ``atpp/machine/+/status`` и сохраняет полученные данные в БД.
    """

    def __init__(self, db_manager, *,
                 broker_host: str = "localhost",
                 broker_port: int = 1883,
                 topic: str = "atpp/machine/+/status",
                 client_id: Optional[str] = None):
        if not HAS_MQTT:
            raise RuntimeError(
                "paho-mqtt не установлен. Установите: pip install paho-mqtt")
        self.db = db_manager
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.client_id = client_id or f'atpp-collector-{id(self)}'
        self._client: Optional[mqtt.Client] = None
        self._thread: Optional[Thread] = None
        self._stop = Event()

    def start(self):
        """Подключиться и запустить MQTT loop в daemon-потоке."""
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                   client_id=self.client_id)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        self._client.connect(self.broker_host, self.broker_port, keepalive=60)
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Остановить коллектор."""
        self._stop.set()
        if self._client:
            self._client.disconnect()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop.is_set():
            if self._client:
                self._client.loop(timeout=1.0)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        client.subscribe(self.topic)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        eq_id = payload.get('equipment_id')
        if eq_id is None:
            # Извлечь из топика: atpp/machine/{id}/status
            parts = msg.topic.split('/')
            if len(parts) >= 3 and parts[2].isdigit():
                eq_id = int(parts[2])

        if eq_id is None:
            return

        telemetry = MachineTelemetry(
            equipment_id=eq_id,
            status=payload.get('status', 'offline'),
            spindle_speed=payload.get('spindle_speed'),
            feed_rate=payload.get('feed_rate'),
            power_consumption=payload.get('power'),
            program_number=payload.get('program'),
            active_operation_id=payload.get('operation_id'),
            work_order_item_id=payload.get('wo_item_id'),
            reported_at=datetime.now(),
        )
        with self.db.get_session() as s:
            store_telemetry(s, telemetry=telemetry)
