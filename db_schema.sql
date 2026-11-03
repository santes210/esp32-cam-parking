-- Schema de la base de datos del sistema de parking (SQLite).
-- Esta tabla es consistente con core/tracking.py (CREATE TABLE de init_lock).
--
-- Esquema: parking_records (plaque, zone unique)
--
-- id               : clave primaria autoincremental
-- plaque           : placa reconocida (TEXT)
-- zone             : zona donde se detectó la placa (TEXT)
-- recognized_at    : hora de la última detección (TEXT)
-- confidence       : confianza del detector (REAL 0.0-1.0)
-- detected_at      : timestamp de última detección (TEXT)

CREATE TABLE IF NOT EXISTS parking_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    plaque       TEXT    NOT NULL,
    zone         TEXT    NOT NULL,
    recognized_at TEXT    NOT NULL,
    confidence   REAL    NOT NULL,
    detected_at   TEXT    NOT NULL,
    FOREIGN KEY (plaque, zone) UNIQUE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_records_zone ON parking_records (zone);
CREATE INDEX IF NOT EXISTS idx_records_plaque ON parking_records (plaque);
