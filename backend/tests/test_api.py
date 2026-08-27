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
    assert bad.status_code == 422
    # BookingIn rejects the range, so this is FastAPI's request-validation body
    # rather than the flat `detail` string the endpoint returns for a constraint
    # failure. Assert the reason, not the envelope.
    assert "check_out must be later than check_in" in bad.text


def test_bookings_payload_has_no_guest_email(client):
    room_id = client.post(
        "/api/rooms", json={"name": "Dune Suite", "capacity": 2, "rate_cents": 30_000}
    ).json()["id"]
    guest_id = client.post(
        "/api/guests", json={"name": "Grace", "email": "grace@example.com"}
    ).json()["id"]
    client.post(
        "/api/bookings",
        json={
            "room_id": room_id,
            "guest_id": guest_id,
            "check_in": "2026-10-01",
            "check_out": "2026-10-03",
        },
    )

    response = client.get("/api/bookings")
    assert response.status_code == 200
    assert "grace@example.com" not in response.text
    assert all("email" not in booking for booking in response.json())


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


# --------------------------------------------------------------------------
# #2: check_in / check_out are dates, not arbitrary strings
# --------------------------------------------------------------------------


def _stay(client, **dates) -> tuple[int, dict]:
    room_id = client.post(
        "/api/rooms", json={"name": "Lagoon Hut", "capacity": 2, "rate_cents": 20_000}
    ).json()["id"]
    guest_id = client.post("/api/guests", json={"name": "Ada", "email": "ada@example.com"}).json()[
        "id"
    ]
    response = client.post(
        "/api/bookings", json={"room_id": room_id, "guest_id": guest_id, **dates}
    )
    return response.status_code, response.json()


@pytest.mark.parametrize(
    "check_in, check_out",
    [
        ("banana", "carrot"),
        ("2026-13-45", "2026-99-99"),
        ("2026-02-30", "2026-03-01"),
        ("", ""),
        ("2026-09-01", "not-a-date"),
    ],
)
def test_non_dates_are_rejected(client, check_in, check_out):
    status, _ = _stay(client, check_in=check_in, check_out=check_out)
    assert status == 422


@pytest.mark.parametrize(
    "check_in, check_out",
    [
        # Reversed ranges the lexicographic CHECK let through, because the
        # input was not zero-padded: at the ninth character "9" > "1".
        ("2026-9-10", "2026-9-9"),
        ("01/05/2026", "05/01/2026"),
    ],
)
def test_unpadded_reversed_ranges_are_rejected(client, check_in, check_out):
    """These returned 201 while the only guard was `CHECK (check_out > check_in)`."""
    status, _ = _stay(client, check_in=check_in, check_out=check_out)
    assert status == 422


def test_equal_dates_are_rejected(client):
    """A stay is half-open, so a zero-night range is not a stay."""
    status, _ = _stay(client, check_in="2026-09-01", check_out="2026-09-01")
    assert status == 422


def test_accepted_dates_are_stored_as_padded_iso(client):
    """What ORDER BY check_in and the CHECK constraint both rely on."""
    status, created = _stay(client, check_in="2026-09-01", check_out="2026-09-05")
    assert status == 201
    assert created["check_in"] == "2026-09-01"
    assert created["check_out"] == "2026-09-05"

    [booking] = client.get("/api/bookings").json()
    assert booking["check_in"] == "2026-09-01"
    assert booking["check_out"] == "2026-09-05"


def test_bookings_list_sorts_chronologically(client):
    """Garbage check-in values used to sort wherever they happened to fall."""
    room_a = client.post(
        "/api/rooms", json={"name": "Room A", "capacity": 2, "rate_cents": 10_000}
    ).json()["id"]
    room_b = client.post(
        "/api/rooms", json={"name": "Room B", "capacity": 2, "rate_cents": 10_000}
    ).json()["id"]
    guest_id = client.post(
        "/api/guests", json={"name": "Grace", "email": "grace@example.com"}
    ).json()["id"]

    for room_id, check_in, check_out in [
        (room_a, "2026-10-05", "2026-10-07"),
        (room_b, "2026-09-01", "2026-09-03"),
    ]:
        assert (
            client.post(
                "/api/bookings",
                json={
                    "room_id": room_id,
                    "guest_id": guest_id,
                    "check_in": check_in,
                    "check_out": check_out,
                },
            ).status_code
            == 201
        )

    check_ins = [b["check_in"] for b in client.get("/api/bookings").json()]
    assert check_ins == sorted(check_ins) == ["2026-09-01", "2026-10-05"]
