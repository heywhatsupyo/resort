"""FastAPI application for resort."""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field, model_validator

from . import db
from .seed_data import TRIP


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.seed_resorts()
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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "db": str(db.db_path())}


@app.get("/api/rooms")
def get_rooms(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return db.list_rooms(conn)


@app.post("/api/rooms", status_code=201)
def post_room(room: RoomIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        room_id = db.add_room(conn, room.name, room.capacity, room.rate_cents)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"id": room_id, **room.model_dump()}


@app.post("/api/guests", status_code=201)
def post_guest(guest: GuestIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        guest_id = db.add_guest(conn, guest.name, str(guest.email))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": booking_id, **booking.model_dump()}
