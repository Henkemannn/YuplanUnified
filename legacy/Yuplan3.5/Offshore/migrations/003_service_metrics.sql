-- 003_service_metrics.sql
-- Tabeller för portions-/serviceintelligens och normativa baseline-värden
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS service_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rig_id INTEGER NOT NULL,
    date TEXT NOT NULL,                  -- YYYY-MM-DD
    meal TEXT NOT NULL,                  -- lunsj | middag (kan utökas)
    dish_id INTEGER,                     -- kan vara NULL för total / kategoriagg
    category TEXT,                       -- soppa|fisk|kott|extra (redundans för snabba aggregeringar)
    guest_count INTEGER NOT NULL,
    planned_qty_kg REAL,                 -- planerad mängd (innan produktion)
    produced_qty_kg REAL,                -- faktisk producerad mängd
    served_qty_kg REAL,                  -- faktisk serverad (kan auto-deriveras)
    leftover_qty_kg REAL,                -- faktisk kvar / svinn (kan auto-deriveras)
    served_g_per_guest REAL,             -- denormaliserad (served_qty_kg*1000/guest_count)
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(rig_id, date, meal, dish_id, category)
);

CREATE INDEX IF NOT EXISTS idx_service_metrics_rig_date ON service_metrics(rig_id, date);
CREATE INDEX IF NOT EXISTS idx_service_metrics_rig_dish ON service_metrics(rig_id, dish_id);
CREATE INDEX IF NOT EXISTS idx_service_metrics_rig_cat ON service_metrics(rig_id, category, date);

CREATE TABLE IF NOT EXISTS dish_nutrition (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rig_id INTEGER NOT NULL,
    dish_id INTEGER NOT NULL,
    protein_per_100g REAL,               -- gram protein per 100g
    default_portion_g INTEGER,           -- normative portion om satt pr dish
    protein_source TEXT,                 -- fish|meat|veg|mixed|other
    last_verified_at TEXT,
    UNIQUE(rig_id, dish_id)
);

CREATE INDEX IF NOT EXISTS idx_dish_nutrition_rig_dish ON dish_nutrition(rig_id, dish_id);

CREATE TABLE IF NOT EXISTS normative_portion_guidelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rig_id INTEGER,                      -- NULL = global baseline
    category TEXT NOT NULL,
    protein_source TEXT,                 -- valfritt för finmaskig matching
    baseline_g_per_guest INTEGER NOT NULL,
    protein_per_100g REAL,               -- valfritt default protein
    valid_from TEXT,                     -- YYYY-MM-DD
    source TEXT,                         -- 'system' | 'municipal' | etc.
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(rig_id, category, IFNULL(protein_source, ''))
);

CREATE INDEX IF NOT EXISTS idx_norm_guidelines_rig_cat ON normative_portion_guidelines(rig_id, category);

COMMIT;
