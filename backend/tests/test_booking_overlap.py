"""A room must never hold two overlapping stays.

A stay is the half-open interval [check_in, check_out), so a checkout and a
check-in on the same day are not a conflict.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app

STAY = ("2026-09-10", "2026-09-20")


@pytest.fixture()
def booked(conn):
    """A room with one existing stay, 10 Sep -> 20 Sep."""
    room_id = db.add_room(conn, "Ocean View", 2, 40_000)
    ada = db.add_guest(conn, "Ada", "ada@example.com")
    grace = db.add_guest(conn, "Grace", "grace@example.com")
    db.add_booking(conn, room_id, ada, *STAY)
    conn.commit()
    return {"room": room_id, "ada": ada, "grace": grace}


@pytest.mark.parametrize(
    ("check_in", "check_out", "label"),
    [
        ("2026-09-05", "2026-09-15", "starts before, ends inside"),
        ("2026-09-15", "2026-09-25", "starts inside, ends after"),
        ("2026-09-12", "2026-09-14", "fully contained"),
        ("2026-09-01", "2026-09-30", "fully contains"),
        ("2026-09-10", "2026-09-20", "exact duplicate"),
        ("2026-09-19", "2026-09-21", "one-day tail overlap"),
        ("2026-09-09", "2026-09-11", "one-day nose overlap"),
    ],
)
def test_overlapping_stays_are_rejected(booked, conn, check_in, check_out, label):
    with pytest.raises(db.BookingConflict):
        db.add_booking(conn, booked["room"], booked["grace"], check_in, check_out)

    # Nothing was written.
    assert len(db.list_bookings(conn)) == 1, label


@pytest.mark.parametrize(
    ("check_in", "check_out", "label"),
    [
        ("2026-09-20", "2026-09-25", "check-in on the previous checkout day"),
        ("2026-09-05", "2026-09-10", "checkout on the existing check-in day"),
        ("2026-09-21", "2026-09-25", "clearly after"),
        ("2026-09-01", "2026-09-05", "clearly before"),
    ],
)
def test_adjacent_stays_are_allowed(booked, conn, check_in, check_out, label):
    db.add_booking(conn, booked["room"], booked["grace"], check_in, check_out)
    assert len(db.list_bookings(conn)) == 2, label


def test_same_dates_in_a_different_room_are_allowed(booked, conn):
    other = db.add_room(conn, "Garden Room", 2, 30_000)
    db.add_booking(conn, other, booked["grace"], *STAY)
    assert len(db.list_bookings(conn)) == 2


def test_conflict_names_the_blocking_stay(booked, conn):
    with pytest.raises(db.BookingConflict) as raised:
        db.add_booking(conn, booked["room"], booked["grace"], "2026-09-12", "2026-09-14")

    conflict = raised.value.conflict
    assert conflict is not None
    assert (conflict["check_in"], conflict["check_out"]) == STAY
    assert conflict["guest"] == "Ada"


def test_find_booking_conflict_excludes_the_row_itself(booked, conn):
    existing = db.list_bookings(conn)[0]
    assert db.find_booking_conflict(conn, booked["room"], *STAY, exclude_id=existing["id"]) is None
    assert db.find_booking_conflict(conn, booked["room"], *STAY) is not None


def test_moving_a_booking_onto_another_is_rejected(booked, conn):
    """The UPDATE trigger holds the same invariant as the INSERT one."""
    later = db.add_booking(conn, booked["room"], booked["grace"], "2026-09-25", "2026-09-28")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "UPDATE bookings SET check_in = ?, check_out = ? WHERE id = ?",
            ("2026-09-11", "2026-09-13", later),
        )


def test_editing_a_booking_does_not_conflict_with_itself(booked, conn):
    existing = db.list_bookings(conn)[0]["id"]
    conn.execute(
        "UPDATE bookings SET check_in = ?, check_out = ? WHERE id = ?",
        ("2026-09-11", "2026-09-19", existing),
    )
    row = conn.execute("SELECT check_in FROM bookings WHERE id = ?", (existing,)).fetchone()
    assert row["check_in"] == "2026-09-11"


# --------------------------------------------------------------------------
# API surface
# --------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RESORT_DB", str(tmp_path / "resort.db"))
    with TestClient(app) as c:
        yield c


def _seed(client):
    room = client.post(
        "/api/rooms", json={"name": "Ocean View", "capacity": 2, "rate_cents": 40_000}
    ).json()
    ada = client.post("/api/guests", json={"name": "Ada", "email": "ada@example.com"}).json()
    grace = client.post("/api/guests", json={"name": "Grace", "email": "grace@example.com"}).json()
    return room["id"], ada["id"], grace["id"]


def test_issue_1_reproduction_now_returns_409(client):
    """The exact sequence from the issue report."""
    room, ada, grace = _seed(client)

    first = client.post(
        "/api/bookings",
        json={
            "room_id": room,
            "guest_id": ada,
            "check_in": "2026-09-01",
            "check_out": "2026-09-10",
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/bookings",
        json={
            "room_id": room,
            "guest_id": grace,
            "check_in": "2026-09-05",
            "check_out": "2026-09-15",
        },
    )
    assert second.status_code == 409
    assert "already booked" in second.json()["detail"]

    # And no row was written for the rejected request.
    assert len(client.get("/api/bookings").json()) == 1


def test_api_rejects_an_exact_duplicate(client):
    room, ada, grace = _seed(client)
    payload = {
        "room_id": room,
        "guest_id": ada,
        "check_in": "2026-09-01",
        "check_out": "2026-09-10",
    }
    assert client.post("/api/bookings", json=payload).status_code == 201
    assert client.post("/api/bookings", json={**payload, "guest_id": grace}).status_code == 409


def test_api_allows_same_day_turnover(client):
    room, ada, grace = _seed(client)
    client.post(
        "/api/bookings",
        json={
            "room_id": room,
            "guest_id": ada,
            "check_in": "2026-09-01",
            "check_out": "2026-09-10",
        },
    )
    turnover = client.post(
        "/api/bookings",
        json={
            "room_id": room,
            "guest_id": grace,
            "check_in": "2026-09-10",
            "check_out": "2026-09-12",
        },
    )
    assert turnover.status_code == 201
    assert len(client.get("/api/bookings").json()) == 2


def test_conflict_detail_names_the_guest_in_the_way(client):
    room, ada, grace = _seed(client)
    client.post(
        "/api/bookings",
        json={
            "room_id": room,
            "guest_id": ada,
            "check_in": "2026-09-01",
            "check_out": "2026-09-10",
        },
    )
    clash = client.post(
        "/api/bookings",
        json={
            "room_id": room,
            "guest_id": grace,
            "check_in": "2026-09-05",
            "check_out": "2026-09-15",
        },
    )
    detail = clash.json()["detail"]
    assert "2026-09-01" in detail and "2026-09-10" in detail and "Ada" in detail


def test_reversed_dates_are_a_422_not_a_409(client):
    """A bad range must stay a validation failure, not be read as a conflict.

    Rejected by BookingIn now rather than by the CHECK constraint, but the
    point is unchanged: it must not be reported as an overlap.
    """
    room, ada, _ = _seed(client)
    bad = client.post(
        "/api/bookings",
        json={
            "room_id": room,
            "guest_id": ada,
            "check_in": "2026-09-10",
            "check_out": "2026-09-01",
        },
    )
    assert bad.status_code == 422


# --------------------------------------------------------------------------
# Concurrency: the issue notes the check must not be raceable
# --------------------------------------------------------------------------


def test_concurrent_overlapping_bookings_cannot_both_win(tmp_path):
    """Two connections racing on the same room must yield exactly one booking.

    This is why the invariant lives in a trigger rather than in a
    SELECT-then-INSERT: application-level checks let both callers pass.
    """
    import threading

    path = tmp_path / "race.db"
    db.init_db(path)
    with db.session(path) as conn:
        room = db.add_room(conn, "Ocean View", 2, 40_000)
        ada = db.add_guest(conn, "Ada", "ada@example.com")
        grace = db.add_guest(conn, "Grace", "grace@example.com")

    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def book(guest_id: int, check_in: str, check_out: str) -> None:
        conn = db.connect(path)
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            barrier.wait(timeout=10)
            conn.execute("BEGIN IMMEDIATE")
            db.add_booking(conn, room, guest_id, check_in, check_out)
            conn.commit()
            outcome = "committed"
        except db.BookingConflict:
            outcome = "rejected"
        except sqlite3.Error:
            outcome = "rejected"
        finally:
            conn.close()
        with lock:
            outcomes.append(outcome)

    threads = [
        threading.Thread(target=book, args=(ada, "2026-09-01", "2026-09-10")),
        threading.Thread(target=book, args=(grace, "2026-09-05", "2026-09-15")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert sorted(outcomes) == ["committed", "rejected"]
    with db.session(path) as conn:
        assert len(db.list_bookings(conn)) == 1
