-- Esquema SQLite del estacionamiento.
-- recognized_at: primera deteccion/entrada; detected_at: ultima deteccion.
-- El importe se calcula en MXN y no se almacena, para que refleje la tarifa actual.

CREATE TABLE IF NOT EXISTS parking_records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    plaque        TEXT NOT NULL,
    zone          TEXT NOT NULL,
    recognized_at TEXT NOT NULL,
    confidence    REAL NOT NULL DEFAULT 0,
    detected_at   TEXT NOT NULL,
    UNIQUE (plaque, zone)
);

CREATE INDEX IF NOT EXISTS idx_records_zone ON parking_records (zone);
CREATE INDEX IF NOT EXISTS idx_records_plaque ON parking_records (plaque);
