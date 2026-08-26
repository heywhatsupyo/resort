import sqlite3

import pytest

from app import db


def test_init_db_creates_file(tmp_path):
    path = db.init_db(tmp_path / "nested" / "resort.db")
    assert path.exists()


def test_schema_tables_exist(conn):
    names = {
        row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"rooms", "guests", "bookings"} <= names


def test_init_db_is_idempotent(tmp_path):
    path = tmp_path / "resort.db"
    db.init_db(path)
    with db.session(path) as conn:
        db.add_room(conn, "Palm Suite", 2, 25_000)
    db.init_db(path)
    with db.session(path) as conn:
        assert len(db.list_rooms(conn)) == 1


def test_booking_round_trip(conn):
    room_id = db.add_room(conn, "Ocean View", 4, 42_000)
    guest_id = db.add_guest(conn, "Ada", "ada@example.com")
    db.add_booking(conn, room_id, guest_id, "2026-09-01", "2026-09-05")
    conn.commit()

    bookings = db.list_bookings(conn)
    assert len(bookings) == 1
    assert bookings[0]["room"] == "Ocean View"
    assert bookings[0]["guest"] == "Ada"


def test_duplicate_room_name_rejected(conn):
    db.add_room(conn, "Palm Suite", 2, 25_000)
    with pytest.raises(sqlite3.IntegrityError):
        db.add_room(conn, "Palm Suite", 2, 25_000)


def test_check_out_must_follow_check_in(conn):
    room_id = db.add_room(conn, "Garden Room", 2, 18_000)
    guest_id = db.add_guest(conn, "Grace", "grace@example.com")
    with pytest.raises(sqlite3.IntegrityError):
        db.add_booking(conn, room_id, guest_id, "2026-09-05", "2026-09-01")


def test_booking_requires_existing_room(conn):
    guest_id = db.add_guest(conn, "Alan", "alan@example.com")
    with pytest.raises(sqlite3.IntegrityError):
        db.add_booking(conn, 999, guest_id, "2026-09-01", "2026-09-02")
