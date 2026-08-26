import sqlite3
from collections.abc import Iterator

import pytest

from app import db


@pytest.fixture()
def conn(tmp_path, monkeypatch) -> Iterator[sqlite3.Connection]:
    """A fresh, isolated database file per test."""
    path = tmp_path / "resort.db"
    monkeypatch.setenv("RESORT_DB", str(path))
    db.init_db(path)
    connection = db.connect(path)
    yield connection
    connection.close()
