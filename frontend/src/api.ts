export interface Room {
  id: number;
  name: string;
  capacity: number;
  rate_cents: number;
  created_at?: string;
}

export interface Booking {
  id: number;
  room: string;
  guest: string;
  email: string;
  check_in: string;
  check_out: string;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} responded ${response.status}`);
  }
  return (await response.json()) as T;
}

export const fetchRooms = () => get<Room[]>("/api/rooms");
export const fetchBookings = () => get<Booking[]>("/api/bookings");

/** Renders cents as a plain currency string, e.g. 42000 -> "$420.00". */
export function formatRate(rateCents: number): string {
  return `$${(rateCents / 100).toFixed(2)}`;
}

/** Whole nights between two ISO dates; 0 if the range is empty or invalid. */
export function nights(checkIn: string, checkOut: string): number {
  const start = Date.parse(checkIn);
  const end = Date.parse(checkOut);
  if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return 0;
  return Math.round((end - start) / 86_400_000);
}
