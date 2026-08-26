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
    assert bad.status_code == 422
    assert bad.json()["detail"] == "check_out must be later than check_in."


# --------------------------------------------------------------------------
# #3: stable details, and failure modes the caller can tell apart
# --------------------------------------------------------------------------


def _room_and_guest(client) -> tuple[int, int]:
    room_id = client.post(
        "/api/rooms", json={"name": "Reef Cabin", "capacity": 3, "rate_cents": 33_000}
    ).json()["id"]
    guest_id = client.post(
        "/api/guests", json={"name": "Alan", "email": "alan@example.com"}
    ).json()["id"]
    return room_id, guest_id


def test_duplicate_room_detail_names_no_internals(client):
    payload = {"name": "Palm Suite", "capacity": 2, "rate_cents": 25_000}
    client.post("/api/rooms", json=payload)
    clash = client.post("/api/rooms", json=payload)

    assert clash.status_code == 409
    detail = clash.json()["detail"]
    assert detail == "A room with that name already exists."
    assert "UNIQUE" not in detail and "rooms." not in detail


def test_duplicate_guest_email_conflicts_with_a_stable_detail(client):
    payload = {"name": "Ada", "email": "ada@example.com"}
    assert client.post("/api/guests", json=payload).status_code == 201
    clash = client.post("/api/guests", json=payload)

    assert clash.status_code == 409
    assert clash.json()["detail"] == "A guest with that email address already exists."


def test_unknown_room_is_a_404_naming_the_room(client):
    _, guest_id = _room_and_guest(client)
    missing = client.post(
        "/api/bookings",
        json={
            "room_id": 9999,
            "guest_id": guest_id,
            "check_in": "2026-09-01",
            "check_out": "2026-09-02",
        },
    )

    assert missing.status_code == 404
    assert missing.json()["detail"] == "There is no room with id 9999."


def test_unknown_guest_is_a_404_naming_the_guest(client):
    room_id, _ = _room_and_guest(client)
    missing = client.post(
        "/api/bookings",
        json={
            "room_id": room_id,
            "guest_id": 9999,
            "check_in": "2026-09-01",
            "check_out": "2026-09-02",
        },
    )

    assert missing.status_code == 404
    assert missing.json()["detail"] == "There is no guest with id 9999."


def test_both_references_unknown_are_named_together(client):
    missing = client.post(
        "/api/bookings",
        json={
            "room_id": 8888,
            "guest_id": 9999,
            "check_in": "2026-09-01",
            "check_out": "2026-09-02",
        },
    )

    assert missing.status_code == 404
    assert missing.json()["detail"] == (
        "There is no room with id 8888. There is no guest with id 9999."
    )


def test_the_three_booking_failures_are_distinguishable(client):
    """A bad reference, a bad range and a duplicate must not share a status."""
    room_id, guest_id = _room_and_guest(client)
    stay = {"check_in": "2026-09-01", "check_out": "2026-09-05"}
    assert (
        client.post(
            "/api/bookings", json={"room_id": room_id, "guest_id": guest_id, **stay}
        ).status_code
        == 201
    )

    def status(**overrides) -> int:
        body = {"room_id": room_id, "guest_id": guest_id, **stay, **overrides}
        return client.post("/api/bookings", json=body).status_code

    assert status(room_id=9999) == 404
    assert status(check_in="2026-09-05", check_out="2026-09-01") == 422
    assert status() == 409


def test_no_sqlite_message_reaches_a_client(client):
    """No response body should carry SQLite's own constraint prose."""
    payload = {"name": "Palm Suite", "capacity": 2, "rate_cents": 25_000}
    client.post("/api/rooms", json=payload)
    room_id, guest_id = _room_and_guest(client)

    bodies = [
        client.post("/api/rooms", json=payload).text,
        client.post("/api/guests", json={"name": "Alan", "email": "alan@example.com"}).text,
        client.post(
            "/api/bookings",
            json={
                "room_id": 9999,
                "guest_id": guest_id,
                "check_in": "2026-09-01",
                "check_out": "2026-09-02",
            },
        ).text,
        client.post(
            "/api/bookings",
            json={
                "room_id": room_id,
                "guest_id": guest_id,
                "check_in": "2026-09-05",
                "check_out": "2026-09-01",
            },
        ).text,
    ]

    for body in bodies:
        assert "constraint failed" not in body
        assert "rooms." not in body and "guests." not in body and "bookings." not in body
