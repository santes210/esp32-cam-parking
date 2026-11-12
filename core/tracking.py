"""Persistencia SQLite y seguimiento de vehiculos estacionados."""

import math
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta

import config

_TRACKING = {}
_lock = threading.RLock()
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _now():
    return datetime.now()


def _format_time(value):
    return value.strftime(_TIME_FORMAT)


def _parse_time(value):
    return datetime.strptime(value, _TIME_FORMAT)


class Record:
    """Un vehiculo estacionado en una zona."""

    __slots__ = (
        "confidence",
        "detected_at",
        "pk",
        "plaque",
        "recognized_at",
        "start",
        "zone",
    )

    def __init__(
        self, plaque, zone, start, recognized_at, confidence, detected_at, pk=0
    ):
        self.plaque = plaque
        self.zone = zone
        self.start = start
        self.recognized_at = recognized_at
        self.detected_at = detected_at
        self.confidence = confidence
        self.pk = pk

    @property
    def elapsed_minutes(self):
        return max(0.0, (_now() - self.start).total_seconds() / 60.0)

    @property
    def elapsed(self):
        """Alias en minutos conservado por compatibilidad."""
        return self.elapsed_minutes

    @property
    def cost(self):
        """Importe total en MXN, redondeado hacia arriba por intervalo."""
        billable_minutes = max(0.0, self.elapsed_minutes - config.GRACE_MINUTES)
        if billable_minutes == 0:
            return 0.0
        intervals = math.ceil(billable_minutes / config.RATE_PER_INTERVAL_MINUTES)
        return round(intervals * config.RATE_PER_INTERVAL_MXN, 2)


@contextmanager
def _database():
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_lock():
    """Crea la base de datos y recupera los vehiculos activos al reiniciar."""
    database_folder = os.path.dirname(os.path.abspath(config.DB_PATH))
    os.makedirs(database_folder, exist_ok=True)

    with _lock, _database() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS parking_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plaque TEXT NOT NULL,
                zone TEXT NOT NULL,
                recognized_at TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0,
                detected_at TEXT NOT NULL,
                UNIQUE(plaque, zone)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_records_zone ON parking_records (zone)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_records_plaque ON parking_records (plaque)"
        )
        rows = conn.execute("SELECT * FROM parking_records").fetchall()

        for row in rows:
            recognized_at = row["recognized_at"]
            rec = Record(
                plaque=row["plaque"],
                zone=row["zone"],
                start=_parse_time(recognized_at),
                recognized_at=recognized_at,
                confidence=row["confidence"],
                detected_at=row["detected_at"],
                pk=row["id"],
            )
            _TRACKING[(rec.plaque, rec.zone)] = rec


def add_record(plaque, zone, confidence):
    """Crea una entrada o actualiza la ultima deteccion de un vehiculo."""
    plaque = str(plaque).strip().upper()
    zone = str(zone).strip()
    if not plaque or not zone:
        raise ValueError("La placa y la zona son obligatorias")

    now = _now()
    timestamp = _format_time(now)
    confidence = max(0.0, min(float(confidence), 1.0))

    with _lock, _database() as conn:
        key = (plaque, zone)
        rec = _TRACKING.get(key)
        if rec is None:
            cursor = conn.execute(
                """
                INSERT INTO parking_records
                    (plaque, zone, recognized_at, confidence, detected_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (plaque, zone, timestamp, confidence, timestamp),
            )
            rec = Record(
                plaque=plaque,
                zone=zone,
                start=now,
                recognized_at=timestamp,
                confidence=confidence,
                detected_at=timestamp,
                pk=cursor.lastrowid,
            )
            _TRACKING[key] = rec
        else:
            rec.confidence = max(rec.confidence, confidence)
            rec.detected_at = timestamp
            conn.execute(
                """
                UPDATE parking_records
                SET confidence = ?, detected_at = ?
                WHERE id = ?
                """,
                (rec.confidence, rec.detected_at, rec.pk),
            )
        return rec


def remove_stale(timeout_seconds=None):
    """Elimina vehiculos que no se han visto durante el tiempo configurado."""
    if timeout_seconds is None:
        timeout_seconds = config.VEHICLE_EXIT_TIMEOUT_SECONDS
    cutoff = _now() - timedelta(seconds=timeout_seconds)

    with _lock, _database() as conn:
        stale = [
            rec for rec in _TRACKING.values() if _parse_time(rec.detected_at) < cutoff
        ]
        for rec in stale:
            conn.execute("DELETE FROM parking_records WHERE id = ?", (rec.pk,))
            _TRACKING.pop((rec.plaque, rec.zone), None)
        return len(stale)


def get_cars():
    """Devuelve una copia de la lista de vehiculos actualmente registrados."""
    with _lock:
        return sorted(_TRACKING.values(), key=lambda rec: (rec.zone, rec.plaque))


def find(zone, plate):
    with _lock:
        return _TRACKING.get((str(plate).strip().upper(), str(zone).strip()))
