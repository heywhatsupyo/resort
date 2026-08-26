"""FastAPI application for resort."""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field

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
    room_id: int
    guest_id: int
    check_in: str
    check_out: str


@app.get("/api/trip")
def get_trip() -> dict:
    """The trip this shortlist was researched for."""
    return TRIP


@app.get("/api/resorts")
def get_resorts(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return db.list_resorts(conn)


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
        booking_id = db.add_booking(
            conn, booking.room_id, booking.guest_id, booking.check_in, booking.check_out
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": booking_id, **booking.model_dump()}
