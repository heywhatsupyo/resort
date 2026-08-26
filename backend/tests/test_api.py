import pytest
from fastapi.testclient import TestClient

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
