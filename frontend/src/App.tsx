import { useEffect, useState } from "react";
import { type Booking, type Room, fetchBookings, fetchRooms, formatRate, nights } from "./api";

export function App() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchRooms(), fetchBookings()])
      .then(([nextRooms, nextBookings]) => {
        setRooms(nextRooms);
        setBookings(nextBookings);
      })
      .catch((cause: unknown) => setError(String(cause)));
  }, []);

  return (
    <main>
      <h1>resort</h1>
      {error && <p className="error">Could not reach the API: {error}</p>}

      <section>
        <h2>Rooms</h2>
        {rooms.length === 0 ? (
          <p className="empty">No rooms yet.</p>
        ) : (
          <ul>
            {rooms.map((room) => (
              <li key={room.id}>
                {room.name} — sleeps {room.capacity} — {formatRate(room.rate_cents)}/night
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Bookings</h2>
        {bookings.length === 0 ? (
          <p className="empty">No bookings yet.</p>
        ) : (
          <ul>
            {bookings.map((booking) => (
              <li key={booking.id}>
                {booking.guest} — {booking.room} — {nights(booking.check_in, booking.check_out)}{" "}
                night(s) from {booking.check_in}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
