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

-- A room cannot hold two bookings whose stays overlap.
--
-- A stay is the half-open interval [check_in, check_out): the checkout day is
-- free for the next guest, so 09-10 -> 09-12 may follow 09-01 -> 09-10. Two
-- stays overlap when `new.check_in < old.check_out AND old.check_in <
-- new.check_out`.
--
-- Enforced here rather than in the API because the check has to run inside the
-- same statement as the write. A SELECT-then-INSERT in application code lets
-- two concurrent requests both pass the check and both insert; a BEFORE INSERT
-- trigger cannot be raced that way, since SQLite holds the write lock for the
-- duration of the statement.
--
-- The subquery is served by idx_bookings_room (room_id, check_in).
CREATE TRIGGER IF NOT EXISTS bookings_no_overlap_insert
BEFORE INSERT ON bookings
FOR EACH ROW
WHEN EXISTS (
    SELECT 1 FROM bookings
     WHERE room_id = NEW.room_id
       AND NEW.check_in < check_out
       AND check_in < NEW.check_out
)
BEGIN
    SELECT RAISE(ABORT, 'booking overlaps an existing booking for this room');
END;

-- Same invariant for edits. `id <> NEW.id` so a booking never conflicts with
-- itself when only, say, the guest changes.
CREATE TRIGGER IF NOT EXISTS bookings_no_overlap_update
BEFORE UPDATE OF room_id, check_in, check_out ON bookings
FOR EACH ROW
WHEN EXISTS (
    SELECT 1 FROM bookings
     WHERE room_id = NEW.room_id
       AND id <> NEW.id
       AND NEW.check_in < check_out
       AND check_in < NEW.check_out
)
BEGIN
    SELECT RAISE(ABORT, 'booking overlaps an existing booking for this room');
END;

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
