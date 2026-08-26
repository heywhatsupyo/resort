from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.seed_data import RESORTS, TRIP


def test_seed_loads_every_resort(tmp_path):
    path = tmp_path / "resort.db"
    count = db.seed_resorts(path)
    assert count == len(RESORTS)

    with db.session(path) as conn:
        assert len(db.list_resorts(conn)) == len(RESORTS)


def test_seed_is_idempotent(tmp_path):
    path = tmp_path / "resort.db"
    db.seed_resorts(path)
    db.seed_resorts(path)
    with db.session(path) as conn:
        assert len(db.list_resorts(conn)) == len(RESORTS)


def test_resorts_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("RESORT_DB", str(tmp_path / "resort.db"))
    with TestClient(app) as client:
        payload = client.get("/api/resorts").json()

    assert len(payload) == len(RESORTS)
    names = {r["name"] for r in payload}
    assert "Nirwana Gardens - Indra Maya Pool Villa" in names

    # In-budget options must sort ahead of the out-of-budget reference entries.
    budgets = [r["in_budget"] for r in payload]
    assert budgets == sorted(budgets, reverse=True)


def test_every_resort_has_decision_data(tmp_path, monkeypatch):
    monkeypatch.setenv("RESORT_DB", str(tmp_path / "resort.db"))
    with TestClient(app) as client:
        payload = client.get("/api/resorts").json()

    for resort in payload:
        assert resort["destination"]
        assert resort["transport"]
        assert resort["unit"]
        assert resort["highlights"], f"{resort['name']} is missing highlights"
        assert resort["watchouts"], f"{resort['name']} is missing watchouts"
        assert resort["price_note"], f"{resort['name']} is missing a price basis"


def test_trip_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("RESORT_DB", str(tmp_path / "resort.db"))
    with TestClient(app) as client:
        payload = client.get("/api/trip").json()

    assert payload["check_in"] == TRIP["check_in"]
    assert payload["nights"] == 2
    assert payload["adults"] + payload["children"] == 6
