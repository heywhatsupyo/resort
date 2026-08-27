"""FastAPI application for resort."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field, model_validator

from . import db
from .seed_data import TRIP

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.seed_resorts()
    # The resolved path is useful when a deployment reads the wrong database,
    # but it describes the filesystem layout, so it belongs in the operator's
    # logs once at startup rather than in a public response on every request.
    logger.info("database: %s", db.db_path())
    yield


app = FastAPI(title="resort", version="0.1.0", lifespan=lifespan)


def get_conn() -> sqlite3.Connection:
    conn = db.connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


class RoomIn(BaseModel):
    name: str = Field(min_length=1)
    capacity: int = Field(gt=0)
    rate_cents: int = Field(ge=0)


class GuestIn(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr


class BookingIn(BaseModel):
    """A stay, as the half-open interval [check_in, check_out).

    The dates are `date`, not `str`: Pydantic then rejects anything that is not
    a real calendar date with a 422, and normalises what it accepts to
    zero-padded ISO-8601. That normalisation is what makes the schema's
    `CHECK (check_out > check_in)` and `ORDER BY check_in` correct — both are
    lexicographic comparisons on TEXT, so they are only right for input that is
    already padded ISO.
    """

    room_id: int
    guest_id: int
    check_in: date
    check_out: date

    @model_validator(mode="after")
    def check_out_must_follow_check_in(self) -> BookingIn:
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be later than check_in")
        return self

    def stay(self) -> tuple[str, str]:
        """The stay as the ISO-8601 text the database stores."""
        return self.check_in.isoformat(), self.check_out.isoformat()


@app.get("/api/trip")
def get_trip() -> dict:
    """The trip this shortlist was researched for."""
    return TRIP


@app.get("/api/resorts")
def get_resorts(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return db.list_resorts(conn)


def conflict_detail(exc: db.BookingConflict) -> str:
    """Name the stay that blocked the booking, when it is known."""
    conflict = exc.conflict
    if not conflict:
        return "That room is already booked for those dates."
    return (
        f"That room is already booked from {conflict['check_in']} to "
        f"{conflict['check_out']} by {conflict['guest']}."
    )


# Which constraint failed, read from sqlite3's structured error code rather
# than by matching the prose of its message. Available since Python 3.11, which
# this project already requires. Keeping the discrimination off the message text
# is the point: the message is not a stable API, and parsing it is the same
# coupling that shipping it to clients was.
def is_unique_violation(exc: sqlite3.IntegrityError) -> bool:
    return exc.sqlite_errorname == "SQLITE_CONSTRAINT_UNIQUE"


def is_foreign_key_violation(exc: sqlite3.IntegrityError) -> bool:
    return exc.sqlite_errorname == "SQLITE_CONSTRAINT_FOREIGNKEY"


def is_check_violation(exc: sqlite3.IntegrityError) -> bool:
    return exc.sqlite_errorname == "SQLITE_CONSTRAINT_CHECK"


def integrity_failure(exc: sqlite3.IntegrityError, subject: str) -> HTTPException:
    """A constraint failed that no handler expected.

    The underlying error goes to the log, where the schema detail belongs; the
    client gets a 500 and nothing about internal tables or columns.
    """
    logger.error("unhandled integrity error saving %s: %s", subject, exc.sqlite_errorname)
    logger.debug("integrity error detail", exc_info=exc)
    return HTTPException(status_code=500, detail=f"Could not save the {subject}.")


def unresolved_reference_detail(conn: sqlite3.Connection, room_id: int, guest_id: int) -> str:
    """Name the id that does not resolve, so the caller need not guess which."""
    missing = db.missing_references(conn, room_id, guest_id)
    ids = {"room": room_id, "guest": guest_id}
    if not missing:
        # The row went away between the failed insert and this lookup.
        return "The room or guest referenced by this booking does not exist."
    return " ".join(f"There is no {kind} with id {ids[kind]}." for kind in missing)


@app.get("/api/health")
def health(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Liveness, plus proof the database actually answers.

    Deliberately says nothing about *where* the database is: health checks are
    conventionally the one route left unauthenticated and reachable from load
    balancers, so anything here is public.
    """
    try:
        conn.execute("SELECT 1").fetchone()
    except sqlite3.Error as exc:
        logger.exception("health check could not reach the database")
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok", "db": "ok"}


@app.get("/api/rooms")
def get_rooms(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return db.list_rooms(conn)


@app.post("/api/rooms", status_code=201)
def post_room(room: RoomIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        room_id = db.add_room(conn, room.name, room.capacity, room.rate_cents)
    except sqlite3.IntegrityError as exc:
        if is_unique_violation(exc):
            raise HTTPException(
                status_code=409, detail="A room with that name already exists."
            ) from exc
        raise integrity_failure(exc, "room") from exc
    return {"id": room_id, **room.model_dump()}


@app.post("/api/guests", status_code=201)
def post_guest(guest: GuestIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        guest_id = db.add_guest(conn, guest.name, str(guest.email))
    except sqlite3.IntegrityError as exc:
        if is_unique_violation(exc):
            raise HTTPException(
                status_code=409, detail="A guest with that email address already exists."
            ) from exc
        raise integrity_failure(exc, "guest") from exc
    return {"id": guest_id, "name": guest.name, "email": str(guest.email)}


@app.get("/api/bookings")
def get_bookings(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return db.list_bookings(conn)


@app.post("/api/bookings", status_code=201)
def post_booking(booking: BookingIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        check_in, check_out = booking.stay()
        booking_id = db.add_booking(conn, booking.room_id, booking.guest_id, check_in, check_out)
    except db.BookingConflict as exc:
        # 409, matching the duplicate-room response: the request is well formed,
        # it just lost to a stay that is already on the books.
        raise HTTPException(status_code=409, detail=conflict_detail(exc)) from exc
    except sqlite3.IntegrityError as exc:
        if is_foreign_key_violation(exc):
            raise HTTPException(
                status_code=404,
                detail=unresolved_reference_detail(conn, booking.room_id, booking.guest_id),
            ) from exc
        if is_check_violation(exc):
            raise HTTPException(
                status_code=422, detail="check_out must be later than check_in."
            ) from exc
        raise integrity_failure(exc, "booking") from exc
    return {"id": booking_id, **booking.model_dump()}
