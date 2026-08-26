"""SQLite data layer. The whole database is one file on disk."""

from __future__ import annotations

import os
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "resort.db"


def db_path() -> Path:
    """Location of the database file; override with the RESORT_DB env var."""
    return Path(os.environ.get("RESORT_DB", DEFAULT_DB_PATH))


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | None = None) -> Path:
    """Create the database file and apply schema.sql. Idempotent."""
    target = path or db_path()
    with connect(target) as conn:
        conn.executescript(SCHEMA_PATH.read_text())
    return target


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_room(conn: sqlite3.Connection, name: str, capacity: int, rate_cents: int) -> int:
    cur = conn.execute(
        "INSERT INTO rooms (name, capacity, rate_cents) VALUES (?, ?, ?)",
        (name, capacity, rate_cents),
    )
    return int(cur.lastrowid)


def list_rooms(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM rooms ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def add_guest(conn: sqlite3.Connection, name: str, email: str) -> int:
    cur = conn.execute("INSERT INTO guests (name, email) VALUES (?, ?)", (name, email))
    return int(cur.lastrowid)


def add_booking(
    conn: sqlite3.Connection, room_id: int, guest_id: int, check_in: str, check_out: str
) -> int:
    cur = conn.execute(
        "INSERT INTO bookings (room_id, guest_id, check_in, check_out) VALUES (?, ?, ?, ?)",
        (room_id, guest_id, check_in, check_out),
    )
    return int(cur.lastrowid)


def list_bookings(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT b.id, b.check_in, b.check_out, r.name AS room, g.name AS guest, g.email
        FROM bookings b
        JOIN rooms  r ON r.id = b.room_id
        JOIN guests g ON g.id = b.guest_id
        ORDER BY b.check_in
        """
    ).fetchall()
    return [dict(r) for r in rows]


RESORT_COLUMNS = (
    "name",
    "destination",
    "transport",
    "travel_time",
    "unit",
    "bedrooms",
    "one_unit",
    "in_budget",
    "nightly_low",
    "nightly_high",
    "review_score",
    "review_scale",
    "review_count",
    "review_source",
    "rank_note",
    "highlights",
    "watchouts",
    "price_note",
)


def add_resort(conn: sqlite3.Connection, resort: dict) -> int:
    placeholders = ", ".join("?" for _ in RESORT_COLUMNS)
    columns = ", ".join(RESORT_COLUMNS)
    cur = conn.execute(
        f"INSERT OR REPLACE INTO resorts ({columns}) VALUES ({placeholders})",
        tuple(resort.get(c) for c in RESORT_COLUMNS),
    )
    return int(cur.lastrowid)


def list_resorts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM resorts
        ORDER BY in_budget DESC, one_unit DESC, nightly_low
        """
    ).fetchall()
    return [dict(r) for r in rows]


def seed_resorts(path: Path | None = None) -> int:
    """Load the researched resort shortlist. Creates the schema first; safe to re-run."""
    from .seed_data import RESORTS

    init_db(path)
    with session(path) as conn:
        for resort in RESORTS:
            add_resort(conn, resort)
    return len(RESORTS)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "init":
        print(f"initialized {init_db()}")
    elif command == "seed":
        init_db()
        print(f"seeded {seed_resorts()} resorts into {db_path()}")
    else:
        print("usage: python -m app.db [init|seed]", file=sys.stderr)
        raise SystemExit(2)
