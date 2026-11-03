"""Persistencia SQLite + tracking en memoria para el sistema de parking."""

import sqlite3
import threading
from datetime import datetime

import config


# Llave (plaque, zone) -> _Record (estado en memoria).
_TRACKING = {}


class Record:
    """Un coche estacionado en una zona."""

    __slots__ = ("plaque", "zone", "start", "recognized_at", "detected_at", "confidence", "pk")

    def __init__(self, plaque, zone, start, recognized_at, confidence, detected_at):
        self.plaque = plaque
        self.zone = zone
        self.start = start
        self.recognized_at = recognized_at
        self.detected_at = detected_at
        self.confidence = confidence
        self.pk = 0

    @property
    def elapsed_minutes(self):
        """(now - start) / 60 (duración en minutos)."""
        return (now - self.start).total_seconds() / 60

    @property
    def elapsed(self):
        """Duración (now - start) en minutos."""
        return self.elapsed_minutes

    @property
    def cost(self):
        minutes = self.elapsed_minutes
        if minutes <= config.GRACE_MINUTES:
            return 0
        extra = minutes - config.GRACE_MINUTES
        return round(extra / config.RATE_PER_INTERVAL_MINUTES) * config.RATE_PER_INTERVAL_MINUTES


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_lock = threading.Lock()


def init_lock():
    """Crea la tabla de la DB si aún no existe."""
    conn = sqlite3.connect(config.DB_PATH)
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS parking_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plaque TEXT NOT NULL,
                zone TEXT NOT NULL,
                recognized_at TEXT NOT NULL,
                confidence REAL,
                detected_at TEXT,
                FOREIGN KEY (plaque, zone) UNIQUE
            )
            """
        )
    conn.close()


def add_record(plaque, zone, confidence):
    """Registra una observacion de la placa.

    - Si la placa/zone nunca se vio: crea un nuevo _Record (start = ahora),
      persiste fila nueva en la DB (pk = id auto).
    - Si ya existe y aún está "dentro del TTL": renueva el max conf y detected_at.

    El costo se calcula desde el primer start (momento de 'entrada').
    """
    key = (plaque, zone)
    now = _now()

    with _lock:
        rec = _TRACKING.get(key)

        if rec is None:
            rec = Record(
                plaque=plaque,
                zone=zone,
                start=now,
                recognized_at=now,
                confidence=0,
                detected_at=now,
            )
            existing = None
        else:
            rec.confidence = max(rec.confidence, confidence)
            rec.detected_at = now
            existing = _query_row(rec)

        _TRACKING[key] = rec
        return rec


def _query_row(rec):
    """Devuelve la fila DB para (plaque, zone) (primera si hay varias), o None."""
    conn = sqlite3.connect(config.DB_PATH)
    try:
        rows = conn.execute(
            "SELECT id FROM parking_records WHERE plaque=? AND zone=? ORDER BY id",
            (rec.plaque, rec.zone),
        ).fetchall()
        return rows[0]["id"] if rows else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def get_cars():
    """Todas las placas registradas (todas las zones del sistema)."""
    return list(_TRACKING.values())


def find(zone, plate):
    """Busca el reg de una placa zona; o None si nunca se registro."""
    return _TRACKING.get((plate, zone))
