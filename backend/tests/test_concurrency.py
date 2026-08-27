"""Concurrent-request coverage for the sqlite connection's thread affinity.

A serial test suite cannot see this class of bug: with no contention anyio
hands the same idle worker thread to both threadpool hops, so the connection
opened by the `get_conn` dependency and the query run by the endpoint always
agree on their thread. These tests create the contention on purpose.
"""

from __future__ import annotations

import socket
import threading
import time
import urllib.error
import urllib.request
from collections import Counter

import pytest
import uvicorn

REQUESTS = 40
STARTUP_TIMEOUT = 30.0


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def live_server(tmp_path, monkeypatch):
    """A real uvicorn server, so requests are served by the threadpool."""
    monkeypatch.setenv("RESORT_DB", str(tmp_path / "resort.db"))

    from app.main import app

    port = free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not server.started:
            pytest.fail(f"server did not start within {STARTUP_TIMEOUT}s")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=STARTUP_TIMEOUT)


def hammer(url: str, count: int = REQUESTS) -> Counter[int]:
    """Fire `count` requests that are released simultaneously."""
    barrier = threading.Barrier(count)
    statuses: Counter[int] = Counter()
    lock = threading.Lock()

    def one() -> None:
        barrier.wait()
        try:
            with urllib.request.urlopen(url, timeout=STARTUP_TIMEOUT) as response:
                status = response.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        except OSError:
            status = 0
        with lock:
            statuses[status] += 1

    threads = [threading.Thread(target=one) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=STARTUP_TIMEOUT)
    return statuses


def test_concurrent_reads_all_succeed(live_server):
    statuses = hammer(f"{live_server}/api/rooms")
    assert statuses == Counter({200: REQUESTS}), dict(statuses)


def test_concurrent_resort_reads_all_succeed(live_server):
    statuses = hammer(f"{live_server}/api/resorts")
    assert statuses == Counter({200: REQUESTS}), dict(statuses)
