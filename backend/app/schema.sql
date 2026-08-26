-- resort schema
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    rate_cents  INTEGER NOT NULL CHECK (rate_cents >= 0),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS guests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id     INTEGER NOT NULL REFERENCES rooms(id)  ON DELETE CASCADE,
    guest_id    INTEGER NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
    check_in    TEXT    NOT NULL,
    check_out   TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    CHECK (check_out > check_in)
);

CREATE INDEX IF NOT EXISTS idx_bookings_room  ON bookings(room_id, check_in);
CREATE INDEX IF NOT EXISTS idx_bookings_guest ON bookings(guest_id);

-- Candidate resorts for the trip, with pricing and review data.
CREATE TABLE IF NOT EXISTS resorts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    destination   TEXT    NOT NULL,
    transport     TEXT    NOT NULL,
    travel_time   TEXT    NOT NULL,
    unit          TEXT    NOT NULL,
    bedrooms      INTEGER,
    one_unit      INTEGER NOT NULL DEFAULT 0,
    in_budget     INTEGER NOT NULL DEFAULT 1,
    nightly_low   INTEGER,
    nightly_high  INTEGER,
    review_score  REAL,
    review_scale  REAL,
    review_count  INTEGER,
    review_source TEXT,
    rank_note     TEXT,
    highlights    TEXT,
    watchouts     TEXT,
    price_note    TEXT
);

CREATE INDEX IF NOT EXISTS idx_resorts_destination ON resorts(destination);
