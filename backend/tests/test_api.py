import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RESORT_DB", str(tmp_path / "resort.db"))
    with TestClient(app) as c:
        yield c


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_does_not_disclose_the_database_path(client, tmp_path):
    """The endpoint is public by convention, so it must not describe the disk."""
    body = response_text = client.get("/api/health").text
    assert "resort.db" not in body
    assert str(tmp_path) not in response_text
    assert set(client.get("/api/health").json()) == {"status", "db"}


class UnreachableConnection:
    """Stands in for a database that is there but will not answer."""

    def execute(self, *args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    def commit(self) -> None:
        pass

    def close(self) -> None:
        pass


def test_health_reports_an_unreachable_database(client, monkeypatch):
    """`ok` should mean the database answered, not just that the process is up."""
    monkeypatch.setattr(main.db, "connect", lambda *a, **kw: UnreachableConnection())
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "database unavailable"


def test_create_and_list_rooms(client):
    created = client.post(
        "/api/rooms", json={"name": "Ocean View", "capacity": 4, "rate_cents": 42_000}
    )
    assert created.status_code == 201

    rooms = client.get("/api/rooms").json()
    assert [r["name"] for r in rooms] == ["Ocean View"]


def test_duplicate_room_conflicts(client):
    payload = {"name": "Palm Suite", "capacity": 2, "rate_cents": 25_000}
    assert client.post("/api/rooms", json=payload).status_code == 201
    assert client.post("/api/rooms", json=payload).status_code == 409


def test_invalid_room_rejected(client):
    bad = client.post("/api/rooms", json={"name": "Tiny", "capacity": 0, "rate_cents": 100})
    assert bad.status_code == 422


def test_booking_flow(client):
    room_id = client.post(
        "/api/rooms", json={"name": "Cliff Villa", "capacity": 6, "rate_cents": 90_000}
    ).json()["id"]
    guest_id = client.post("/api/guests", json={"name": "Ada", "email": "ada@example.com"}).json()[
        "id"
    ]

    created = client.post(
        "/api/bookings",
        json={
            "room_id": room_id,
            "guest_id": guest_id,
            "check_in": "2026-09-01",
            "check_out": "2026-09-05",
        },
    )
    assert created.status_code == 201

    bookings = client.get("/api/bookings").json()
    assert len(bookings) == 1
    assert bookings[0]["room"] == "Cliff Villa"


def test_booking_with_bad_dates_rejected(client):
    room_id = client.post(
        "/api/rooms", json={"name": "Dune House", "capacity": 2, "rate_cents": 30_000}
    ).json()["id"]
    guest_id = client.post(
        "/api/guests", json={"name": "Grace", "email": "grace@example.com"}
    ).json()["id"]

    bad = client.post(
        "/api/bookings",
        json={
            "room_id": room_id,
            "guest_id": guest_id,
            "check_in": "2026-09-05",
            "check_out": "2026-09-01",
        },
    )
    assert bad.status_code == 400
