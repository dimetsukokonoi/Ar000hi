# Arooohi Backend API — Ornab's Feature Modules

> Added by MD. Aminul Islam Ornab (2026-07-31) for the SRS features:
> Trusted Contact Sharing (#12), Ride Cost Splitter (#5), Peak Hour Surge (#13),
> Ride Chat (#15), Eco/Footprint Tracker (#20).
>
> Base URL: `http://localhost:8000`
> Auth: `Authorization: Bearer <token>` (get token from `POST /api/auth/login` or `/api/auth/verify-otp`).
> WebSocket: query param `?token=<token>`.

All endpoints return JSON. Errors return `{"detail": "..."}` with 4xx/5xx status.

---

## 1. Trusted Contacts  (`/api/contacts`)

Backed by the existing `trusted_contacts` table. Used by the SOS flow (which reads contacts from the DB).

| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| GET | `/api/contacts` | yes | — | `[{ id, contact_name, contact_phone, contact_email, created_at }]` |
| POST | `/api/contacts` | yes | `{ contact_name, contact_phone, contact_email? }` | `{ message, contact: { id, ... } }` |
| DELETE | `/api/contacts/{contact_id}` | yes | — | `{ message }` |
| POST | `/api/contacts/auto-share` | yes | `{ share_url, session_id? }` | `{ message, share_url, contacts_notified, share_id }` |
| GET | `/api/contacts/shares` | yes | — | `[{ share_id, share_url, contact_count, created_at }]` |

- Phone numbers must be BD format (`^01\d{9}$`).
- `auto-share` persists a row in the new `contact_shares` table (a visible share history) **and** mocks delivery to each trusted contact (console log) — same pattern as SOS. Replace with real SMS/push in production.
- `GET /api/contacts/shares` lists the current user's share history (most recent first).

---

## 2. Rides  (`/api/rides`)

Minimal ride lifecycle. New tables: `rides`, `ride_passengers`. Full matching/booking (Sprint 2) can build on these.

| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| POST | `/api/rides` | yes | `{ source, destination, base_fare, total_seats?, scheduled_at? }` | `{ message, ride_id, status, surge_multiplier, total_seats }` |
| GET | `/api/rides` | yes | — | `{ mine: [ride...], available: [ride...] }` |
| GET | `/api/rides/{ride_id}` | yes | — | ride detail incl. `passengers[]` and `total_seats` |
| POST | `/api/rides/{ride_id}/join` | yes | `{ seats? }` | `{ message, passenger_id, status }` |
| POST | `/api/rides/{ride_id}/accept/{passenger_id}` | driver | — | `{ message }` |
| POST | `/api/rides/{ride_id}/start` | driver | — | `{ message, status }` |
| POST | `/api/rides/{ride_id}/end` | driver | `{}` or `{ distance_km? }` | `{ message, distance_km }` |
| GET | `/api/rides/{ride_id}/split` | participant | — | cost split breakdown (see below) |
| GET | `/api/rides/{ride_id}/messages` | participant | — | `[{ id, sender_id, sender_name, message, created_at }]` |

Notes:
- **create** captures the current surge multiplier into the ride; `total_seats` defaults to 4.
- **join** is seat-aware: `seats + already-accepted seats` must be `<= total_seats`, else `409` "not enough seats". Passengers requesting more seats than remaining get the error.
- **end** estimates distance from the **full path length** of the most recent inactive GPS tracking session, else from a BRACU zone lookup (`ZONES` in `rides.py`), else 5 km default.
- Ride status flow: `scheduled -> active -> completed` (or `cancelled`, reserved for future).
- Any verified user can create a ride for demo purposes.

### Cost Splitter — `GET /api/rides/{ride_id}/split`
Formula: `total = base_fare x surge_multiplier`; share split is **seat-weighted** across accepted passengers (driver excluded).

```json
{
  "ride_id": "...", "source": "Gate 1", "destination": "Library",
  "base_fare": 100.0, "surge_multiplier": 1.3,
  "total": 130.0, "passenger_count": 2,
  "per_seat": 43.33, "total_seats": 3,
  "breakdown": [ { "passenger": "Rider A", "share": 86.67, "seats": 2 }, { "passenger": "Rider B", "share": 43.33, "seats": 1 } ]
}
```

- `per_seat = total / sum(all passenger seats)`; each passenger pays `per_seat x seats`.
- Splitting uses **largest-remainder (paisa) rounding** so the breakdown always sums to exactly `total` (no cent loss).

---

## 3. Peak Hour Surge  (`/api/surge`)

New table `surge_config` (24 seeded hourly baselines). Multiplier = baseline + live ride volume bump, clamped 1.0–2.0.

| Method | Path | Auth | Returns |
|---|---|---|---|---|
| GET | `/api/surge/current` | yes | `{ hour, demand, active_rides, multiplier, label, message }` |
| GET | `/api/surge/schedule` | yes | `{ schedule: [{ hour, demand, multiplier, label, is_current }...] }` (24 entries) |

`label`: `Normal` (1.0) / `Elevated` (1.1–1.2) / `High` (1.3–1.4) / `Peak` (>=1.5).
`is_current`: `true` for exactly one entry — the current hour — and the live active-ride bump is applied **only** to that entry.

---

## 4. Ride Chat  (`/api/...`) + WebSocket

New table `chat_messages`. Chat is scoped to a ride; only the **driver and accepted passengers** can join.

- History: `GET /api/rides/{ride_id}/messages` (see section 2).
- Real-time: `ws://localhost:8000/ws/chat/{ride_id}?token=<JWT>`

**Send:** `{ "message": "hi" }` (text frame, JSON-encoded)
**Receive (broadcast to all participants):**
```json
{ "id": "...", "ride_id": "...", "sender_id": "...", "sender_name": "A", "message": "hi", "created_at": "..." }
```
Close codes: `4401` bad/expired token, `4403` not a ride participant.

Rate limits: spam guard allows at most **20 messages per 10 seconds** per user (excess gets close code `4429`); messages are capped at 500 characters.

---

## 5. Eco/Footprint Tracker  (`/api/eco`)

| Method | Path | Auth | Returns |
|---|---|---|---|---|
| GET | `/api/eco/stats` | yes | see below |
| GET | `/api/eco/leaderboard` | yes | `[{ rank, user_id, name, total_km, total_saved_kg, trips }]` (top 10 by distance) |

```json
{
  "trips": 3, "total_km": 12.4,
  "total_solo_kg": 1.61, "total_saved_kg": 0.81,
  "trees_equivalent": 0.04, "fuel_saved_l": 0.87,
  "rides": [ { "ride_id": "...", "distance_km": 4.1, "occupancy": 2, "solo_kg": 0.53, "shared_kg": 0.27, "saved_kg": 0.27 } ]
}
```

Formula per completed ride: `saved = distance x 0.13 kg/km x (1 - 1/occupancy)`, where `occupancy = driver + accepted passengers`. Aggregated over rides where the user is driver or passenger.

---

## Quick demo flow (two accounts)

1. Register + verify two BRACU emails (`POST /api/auth/register`, `POST /api/auth/verify-otp`).
2. Driver: `POST /api/rides` `{ source: "Gate 1", destination: "Library", base_fare: 100 }`.
3. Rider: `POST /api/rides/{id}/join` → Driver: `POST /api/rides/{id}/accept/{pid}`.
4. Driver: `POST /api/rides/{id}/start`, then `POST /api/rides/{id}/end`.
5. Any participant: `GET /api/rides/{id}/split` and `GET /api/rides/{id}/messages`.
6. Open two WebSocket clients to `/ws/chat/{id}?token=...` to chat.
7. `GET /api/eco/stats` shows the completed ride's CO2 savings.
