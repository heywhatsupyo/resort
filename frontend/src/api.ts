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
  check_in: string;
  check_out: string;
}

export interface Trip {
  check_in: string;
  check_out: string;
  nights: number;
  adults: number;
  children: number;
  note: string;
}

export interface Resort {
  id: number;
  name: string;
  destination: string;
  transport: string;
  travel_time: string;
  unit: string;
  bedrooms: number | null;
  one_unit: number;
  in_budget: number;
  nightly_low: number | null;
  nightly_high: number | null;
  review_score: number | null;
  review_scale: number | null;
  review_count: number | null;
  review_source: string | null;
  rank_note: string | null;
  highlights: string | null;
  watchouts: string | null;
  price_note: string | null;
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
export const fetchResorts = () => get<Resort[]>("/api/resorts");
export const fetchTrip = () => get<Trip>("/api/trip");

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

/** Whole SGD with thousands separators, e.g. 1600 -> "S$1,600". */
export function sgd(amount: number): string {
  return `S$${Math.round(amount).toLocaleString("en-SG")}`;
}

/** Midpoint of a price band, tolerating a missing high or low end. */
export function midpoint(low: number | null, high: number | null): number | null {
  if (low === null && high === null) return null;
  if (low === null) return high;
  if (high === null) return low;
  return (low + high) / 2;
}

/** Any review scale (4.0/5, 8.6/10) rescaled to /10 so scores are comparable. */
export function scoreOutOfTen(score: number | null, scale: number | null): number | null {
  if (score === null || !scale) return null;
  return Math.round((score / scale) * 100) / 10;
}

/** Cost of the whole stay for the party, from a per-night band midpoint. */
export function stayTotal(resort: Resort, tripNights: number): number | null {
  const perNight = midpoint(resort.nightly_low, resort.nightly_high);
  return perNight === null ? null : perNight * tripNights;
}

/** Per-head cost of the whole stay, rounded to the nearest dollar. */
export function perPerson(total: number | null, people: number): number | null {
  if (total === null || people <= 0) return null;
  return total / people;
}
