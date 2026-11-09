CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    email       TEXT NOT NULL DEFAULT '',
    phone       TEXT NOT NULL DEFAULT '',
    id_type     TEXT,
    id_number   TEXT,
    id_file     TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    type_key         TEXT NOT NULL,
    category         TEXT NOT NULL,
    daily_rate_cents INTEGER NOT NULL,
    attributes       TEXT NOT NULL DEFAULT '{}',
    active           INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rentals (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          INTEGER NOT NULL REFERENCES items(id),
    customer_id      INTEGER NOT NULL REFERENCES customers(id),
    start_date       TEXT NOT NULL,
    days             INTEGER NOT NULL,
    due_date         TEXT NOT NULL,
    daily_rate_cents INTEGER NOT NULL,
    total_cents      INTEGER NOT NULL,
    price_lines      TEXT NOT NULL DEFAULT '[]',
    created_at       TEXT NOT NULL,
    returned_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_rentals_item ON rentals(item_id);
CREATE INDEX IF NOT EXISTS idx_rentals_customer ON rentals(customer_id);
CREATE INDEX IF NOT EXISTS idx_rentals_open ON rentals(returned_at);
