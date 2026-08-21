# Arooohi — Project Plan & Roadmap

> SRS source: `Misc./Arooohi_Complete_SRS_Report.pdf` (Section 7 = Development Plan).
> Companion doc: [`PROJECT_PROGRESS.md`](./PROJECT_PROGRESS.md) for current status.
> This file is commit-friendly and team-facing. Private working notes live in `.arooohi-dev/` (git-ignored).

## 1. Purpose

Arooohi is an exclusive, student-to-student ride-sharing network for BRAC University.
Goal: secure, low-cost commutes; passive income for student drivers; safety-first
design (female-only mode, SOS, trusted-contact tracking). This plan maps the 20 SRS
features onto an actionable roadmap, defines acceptance criteria, and tracks the
known code-quality backlog that must be addressed alongside feature work.

## 2. Technology Stack (actual vs. SRS)

| Layer | SRS (planned) | Actual | Deviation |
|-------|---------------|--------|-----------|
| Backend | FastAPI (Python) | FastAPI 0.115 + uvicorn | ✔ |
| Database | PostgreSQL (PostGIS) / MongoDB | SQLite (stdlib `sqlite3`) | ⚠ SQLite only — no geospatial (PostGIS). Fine for demo; blocks zone-matching/heatmaps at scale. |
| Frontend | React.js (web) + React Native (mobile) | Next.js 16 (web only) | ⚠ Mobile is out of scope for now |
| Auth | — | JWT (python-jose HS256) + bcrypt | ✔ |
| Realtime | REST + WebSockets (SRS 3.3.4) | WebSockets only for ride chat; GPS tracking is 5s HTTP polling | ⚠ See NFR-1 |
| Payments | bKash API | Wallet ledger (SQLite) + mocked bKash gateway | ⚠ Real bKash still deferred; the mock is isolated in `wallet.py::_mock_bkash_charge()` |

## 3. Sprint Roadmap (from SRS §7) — with acceptance criteria

Legend: ✅ done · 🔶 partial · ❌ not started

### Sprint 1 — Core Setup & Authentication (weeks 1-2)
| # | Feature | Status | Acceptance criteria |
|---|---------|--------|---------------------|
| 1 | BRACU Student Verification | ✅ | Non-@g.bracu.ac.bd emails rejected; 6-digit OTP verifies account; unverified users cannot log in. |
| 11 | Driver Vehicle Verification | ✅ | Driver uploads NID/license/vehicle reg; admin approves/rejects; role flips to driver only on approval; rejected → resubmit allowed. |

### Sprint 2 — Ride Matching & Logistics (weeks 3-4)
| # | Feature | Status | Acceptance criteria |
|---|---------|--------|---------------------|
| 6 | Campus Zone Smart Matching | ✅ | `GET /rides/match` scores rides on pickup/drop-off zone proximity (haversine over `ZONES`), intermediate stops, and class-time flex. |
| 14 | Campus Pickup Hotspots | ✅ | 12 categorized hotspots + dropdowns in the ride form; geo matching now live via `_haversine_km`. |
| 8 | Scheduled Ride Booking | ✅ | ISO `scheduled_at` validated on create; datetime picker in the form; "Scheduled" filter tab on the rides page. |
| 19 | Multi-Stop Ride Support | 🔶 | Backend complete (`ride_stops`, per-passenger pickup/drop-off, stop status endpoint). Frontend reads the wrong field names — see §6.4. |

### Sprint 3 — Tracking & Safety (weeks 5-6)
| # | Feature | Status | Acceptance criteria |
|---|---------|--------|---------------------|
| 2 | Live GPS Ride Tracking | ✅ | Coordinates update ≤3s; share link shows live position (currently 5s polling, not WS). |
| 3 | Female-Only Ride Mode | ✅ | `rides.female_only`; gender-gated on create/join/match/list, enforced in SQL; pink-bordered cards + filter tab. |
| 4 | In-App SOS Button | ✅ | SOS dispatches mock alerts to saved contacts + campus security with lat/lng; admin can resolve. |
| 12 | Trusted Contact Sharing | ✅ | Contacts persist in DB; auto-share mocks delivery of ride/tracking link; SOS reads contacts from DB. |
| 15 | Ride Chat (In-App Messaging) | ✅ | Driver + accepted passengers chat in real time (WS); messages persist; non-participants rejected (4403). |

### Sprint 4 — Payments & Earnings (weeks 7-8)
| # | Feature | Status | Acceptance criteria |
|---|---------|--------|---------------------|
| 5 | Ride Cost Splitter | ✅ | total = base_fare × surge; split evenly among accepted passengers; breakdown shown. |
| 13 | Peak Hour Surge Indicator | ✅ | Surge reflects current hour (Asia/Dhaka) + live ride volume; badge shown on booking screen. |
| 9 | Wallet & bKash Integration | ✅ | `wallets` + append-only `wallet_transactions` ledger; mock bKash top-up isolated in `_mock_bkash_charge()`. |
| 10 | Ride History & Receipt Log | ✅ | `GET /history` (role filter) + `GET /history/{id}/receipt`; printable receipt modal reuses the splitter math. |
| 16 | Driver Earnings Dashboard | ✅ | `GET /earnings/summary` — weekly buckets, ride count, pending payout; `POST /earnings/payout` sweeps into the wallet. |

### Sprint 5 — Quality & Admin Controls (weeks 9-10)
| # | Feature | Status | Acceptance criteria |
|---|---------|--------|---------------------|
| 7 | Driver Rating & Review | ✅ | `reviews` table with UNIQUE(ride, reviewer, reviewee); post-ride prompt on the history page; average + histogram on the driver profile. |
| 17 | Admin Complaint Panel | ✅ | File complaint; admin review + notes + statuses + stats. |
| 18 | Ride Cancellation Policy & Penalty | ✅ | Free before dispatch; 20% fee after (floor ৳20, ceiling ৳150) charged to the wallet. Preview endpoint feeds the warning dialog. |
| 20 | Eco/Footprint Tracker | ✅ | CO₂ saved per completed ride vs solo; aggregated totals + trees/fuel equivalents. |

## 4. Remaining work

All 20 SRS features now have an implementation. What is left is repair and polish,
not new features:

1. **Fix the two Feature 19 / Feature 6 frontend field-name mismatches** (see §6.4) —
   both are silent: the UI renders but the feature does not do what it appears to.
   *(≈0.5 day)*
2. **Cap the tracking `points` array + retention policy** (§6.3). *(≈0.5 day)*
3. ~~**Charge fares to the wallet on ride completion**~~ — ✅ **DONE.** `end_ride` now
   debits every accepted passenger their seat-weighted share (same `_split_total` math
   the splitter shows) as a `fare` ledger row. Overdraft is allowed so a broke rider
   can never block the driver from finishing; the wallet then shows an "You owe ৳X"
   prompt and the next top-up settles it. `end_ride` also rejects a second call, which
   would otherwise double-charge.
4. **Swap the mock bKash gateway for the real API** — replace `_mock_bkash_charge()` in
   `wallet.py`; nothing else in the app needs to change. *(deferred, needs credentials)*

## 5. Non-Functional Requirements — gap checklist

| NFR | Status | Notes |
|-----|--------|-------|
| NFR-1 Performance (<2s GPS/SOS) | ⚠ | SOS is REST (fast); GPS is 5s polling. WS upgrade recommended. |
| NFR-2 Security (encryption at rest/in transit) | ⚠ | Passwords bcrypt-hashed ✔; JWT HS256 ✔; no TLS on local; OTP hint is DEMO_MODE-gated ✔; rate limiting added ✔; uploads MIME-validated ✔; WS token still in query string; admin creds shown on login (demo). |
| NFR-3 Reliability (99.9% uptime) | ⚠ | Demo-grade; single-process SQLite (now WAL mode); no retries/backup strategy. |
| NFR-4 Maintainability (Swagger docs) | ✔ | FastAPI auto-generates Swagger UI; add response models to fully self-document. |
| NFR-5 Scalability (horizontal scaling) | ⚠ | Chat ConnectionManager is in-memory (single process); SQLite single-writer (WAL + FK indexes added ✔). |

## 6. Code-Quality & Improvement Backlog

Prioritized (🔴 = fix soon, 🟡 = improve, 🟢 = nice-to-have). File references included.

> **Status (2026-07-31, Session 10 live-test pass):** all 🔴 Security (§6.1) and
> Correctness (§6.2) items are now FIXED ✅, as are most §6.3/§6.4 items. Session 10
> ran a full live-browser suite — **45/45 green** (harness `/tmp/opencode/e2e/`
> `live-test.js`, screenshots committed in `demo/live-test-screenshots/`) and caught
> one last bug, now fixed: chat spam-guard closed HTTP 403 instead of WS 4429.
> Unchecked items below are remaining/out-of-scope.

### 6.1 Security (🔴) — ✅ ALL DONE (Session 9)
- ✅ **Hardcoded JWT secret fallback** — `auth.py`. Warns on default secret; fails fast when `DEMO_MODE != 1`.
- ✅ **OTP returned in API response** — `routes/auth.py`. `otp_hint` returned only when `DEMO_MODE=1`.
- ✅ **No login/OTP rate limiting** — `routes/auth.py`. Per-IP+email, per-scope (login vs otp): 5 attempts/5 min → 429.
- ✅ **Uploaded files unvalidated** — `routes/drivers.py`. MIME whitelist + size cap; extension derived from MIME.
- ✅ **Weak public share token** — `routes/tracking.py`. Now 32 hex chars.
- ❌ **Token in WebSocket query string** — `chat.py`. Still `?token=`. Accepted deviation (demo); swap to `Sec-WebSocket-Protocol` or a short-lived ticket for production.
- ✅ **`get_current_user_id` doesn't check account status** — `auth.py`. Rejects missing/inactive users.
- ❌ **Admin credentials hardcoded + shown on login page** — demo-only, kept for showcase convenience.

### 6.2 Correctness bugs (🔴) — ✅ ALL DONE (Session 9)
- ✅ **`end_ride` distance uses the wrong tracking points** — `routes/rides.py`. Uses the FULL path length of the most recent inactive tracking session.
- ✅ **Surge schedule applies live bump to all 24 hours** — `routes/surge.py`. Entries carry `is_current`; live bump only affects that hour.
- ✅ **Eco stats can crash on NULL distance** — `routes/eco.py`. `COALESCE(distance_km, 0)`.
- ✅ **Cost splitter rounding** — `routes/rides.py`. Seat-weighted with largest-remainder paisa pass; breakdown sums exactly to `total`.
- ✅ **Join ride lacks seat validation/capacity** — `routes/rides.py`. `total_seats` (default 4); `seats >= 1` + capacity → 409.
- ✅ **`GET /api/drivers/pending` returns all statuses** — `routes/drivers.py`. `?status=all|pending|approved|rejected` (default `pending`).
- ✅ **`get_session_points` leaks any session** — `routes/tracking.py`. Owner-only read.
- ✅ **`resolve_sos` no 404 on missing alert** — `routes/sos.py`. 404 when alert missing.
- ✅ **`resend_otp` uses raw `dict`** — `routes/auth.py`. `ResendOTPRequest` Pydantic model.
- ✅ **`auto_share` ignores `session_id`** — `routes/contacts.py`. Persists to `contact_shares` + share-history endpoint.
- ✅ **Chat spam-guard close never reached the client (Session 10)** — the rate-limit
  path returned HTTP 403; now `await websocket.close(4429)` + `break` so the close
  code documented in `API.md` actually propagates (`chat.py`).

### 6.3 Architecture / reliability (🟡)
- ❌ **Manual `conn.close()` everywhere** — convert to a `get_db()` FastAPI dependency/context manager.
- ❌ **Duplicate participant check** — `rides.py` + `chat.py`. Extract a shared `is_ride_participant()` helper.
- ✅ **SQLite hardening** — WAL + `busy_timeout` + FK indexes on the 6 join/lookup tables (`database.py`).
- ❌ **`init_db()` at import time** — move to FastAPI lifespan.
- ❌ **`requirements.txt` stale** — refresh pins to the tested versions.
- ⏳ **No automated tests in repo** — regression script at `/tmp/opencode/test_backend.py` (54 checks, throwaway DB); port into `backend/tests/` pytest suite.
- ⏳ **Live e2e harness not committed (Session 10)** — Playwright suite at `/tmp/opencode/e2e/live-test.js` (45 checks, 45/45 green); port into a `backend/` or `e2e/` folder for CI.
- ⏳ **Cross-engine e2e (Session 11 to-do)** — the UI stack is engine-agnostic (Next.js/React/Leaflet/WebSockets; no Chrome-only APIs — only standard `navigator.geolocation`/`clipboard`). Both engines are already testable via `./launch.sh --browser chrome|firefox` (chromium at `/opt/helium/chrome`, gecko = Zen via flatpak). TODO: run the Playwright suite against BOTH engines to prove it, and add the frontend feature-map as a `/demo` page.
- ❌ **Mock notifications scattered** — consolidate into a `notifications.py` service.
- ❌ **Hardcoded `ZONES` in `rides.py`** — move to a seeded table (unlocks #6/#14).
- ✅ **Frontend `API` const duplicated** — centralized in `lib/api.ts` (`API`/`WS`/`API_BASE`, overridable via `NEXT_PUBLIC_API_URL`); all pages import from it. With this, switched everything to explicit IPv4 `127.0.0.1` (backend binds 127.0.0.1, CORS allows both `localhost:3000` and `127.0.0.1:3000`, tracking share URLs use `127.0.0.1`) — fixes the gecko-only failure caused by `localhost`→`::1` (IPv6) when the backend binds IPv4-only.
- ✅ **One-command launcher** — `./launch.py` / `./launch.sh` / `launch.bat`: starts backend+frontend, renders the logo, opens the site fullscreen (F11 to toggle, `--windowed` to skip), auto-stops + WAL-checkpoints the DB when the browser closes, plus `--no-browser`/`--browser chrome|firefox`/`--detect`/`status`/`stop`. Cross-platform (pure stdlib; tested on Linux, code-reviewed for macOS/Windows).

### 6.4 Frontend bugs & UX (🟡)
- ✅ **Ride lifecycle had no UI at all** — `dashboard/rides/page.tsx`. `POST /rides/{id}/accept/{pid}`, `/start` and `/end` existed on the backend but had zero frontend callers, so a driver could not run a ride from the browser and six finished features (#5, #7, #10, #16, #18, #20) had no demonstrable path. Added driver-only **Manage Requests** (with a pending-count badge), **Accept**, **Start Ride** and **End Ride**, each gated on ride status. `GET /rides` now also returns `pending_requests` so a booking is visible without opening the ride.
- ✅ **Tracking page: duplicate point sources + leak on unmount** — `dashboard/page.tsx`. Single `recordPoint`, `sessionRef` guard, unmount cleanup, `headers` memoized.
- ❌ **Unbounded `points` array + DB bloat** — cap client points; add retention policy.
- ✅ **Ride chat link shown to non-participants** — `dashboard/rides/page.tsx`. Gated to `mine || ride.driver_id === me`.
- ✅ **Chat page: 4401/4403 gives no explanation** — `dashboard/chat/[rideId]/page.tsx`. Fatal error states shown.
- ✅ **Infinite spinners on failed fetches** — eco/rides/contacts pages now render error states.
- ✅ **`alert()` used for feedback** — rides/contacts now use inline notices.
- ✅ **Surge schedule endpoint unused** — rides page shows an hourly "upcoming peak" strip + current-hour marker (fulfils SRS #13).
- ✅ **Map re-centers on every GPS tick** — `TrackingMap.tsx`. Auto-follow only until the user interacts + "🎯 Re-center" button.
- ✅ **Track page polls after session ended** — `track/[token]/page.tsx`. Stops polling when `is_active=false`.
- ❌ **Multi-stop panel never renders (Feature 19)** — `dashboard/rides/page.tsx` guards on `ride.stop_details` and reads `stop.stop_order` / `stop.stop_name`, but the API returns `stops` with `sequence` / `place` (`rides.py` `_ser()` and `get_ride()`). The driver's "Mark Reached / Mark Departed" controls are therefore unreachable. Also `getHotspotName(stop)` at the route-path line treats each stop as a string while the API sends an object.
- ❌ **Smart matching ignores its filters (Feature 6)** — the page requests `?pickup=&dropoff=&class_time=` but `match_rides()` declares `source`, `destination`, `scheduled_time`. FastAPI drops unknown query params, so all three arrive as `None` and the endpoint returns unfiltered results. Only `female_only` lines up.

## 7. Definition of Done (per feature)

- Backend endpoint(s) implemented + wired in `main.py`; Pydantic request models used.
- Schema changes (if any) in `database.py` `init_db()` (idempotent `IF NOT EXISTS`).
- Frontend page wired to the API with loading / empty / error states.
- `npm run lint`, `npx tsc --noEmit`, `npm run build` pass.
- Backend verified end-to-end (TestClient script on a throwaway DB).
- Acceptance criteria for the feature (from §3) demonstrably met.
- `PROJECT_PROGRESS.md` updated.

## 8. Standing conventions

- Update `PROJECT_PROGRESS.md` (and private `.arooohi-dev/PROGRESS.md`) on every shipped feature.
- Log each session in `.arooohi-dev/SESSION.md`; keep `.arooohi-dev/HISTORY.md` in sync.
- Never commit `.arooohi-dev/`, `backend/.venv/`, `__pycache__/`, `*.pyc`, or local DB churn.
- ⚠ Next.js 16 has breaking changes — read `node_modules/next/dist/docs/` before writing frontend code.
- The app is run via the launcher: `./launch.sh` (or `python3 launch.py` / `launch.bat` on Windows). It uses explicit IPv4 `127.0.0.1` everywhere (site at `http://127.0.0.1:3000`, API at `http://127.0.0.1:8000`) so it behaves identically in Chromium and Firefox. CORS allows both `localhost:3000` and `127.0.0.1:3000`.
