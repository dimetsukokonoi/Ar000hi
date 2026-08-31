# Arooohi — Project Plan & Roadmap

> SRS source: `Misc./Arooohi_Complete_SRS_Report.pdf` (Section 7 = Development Plan).
> Companion doc: [`PROJECT_PROGRESS.md`](./PROJECT_PROGRESS.md) for current status.
> This file is commit-friendly and team-facing. Private working notes live in `.arooohi-dev/` (git-ignored).
> **Status column last synced with the codebase: 2026-09-01** (Sprint 4 in progress).

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
| Payments | bKash API | Prepaid wallet ledger + simulated tokenized checkout | ⚠ Live gateway needs merchant onboarding; `real_bkash.py` is the swap-in |

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
| 6 | Campus Zone Smart Matching | ✅ | Riders to the same destination zone (Gate/Library/etc.) are grouped in a matching list. *(`GET /api/rides/match` — multi-factor score: exact pickup +50, ≤1.5 km haversine proximity +35, direct destination +50, intermediate-stop match +45, ±30 min class-time +15; rides scoring <50 are dropped when both filters are given.)* |
| 14 | Campus Pickup Hotspots | ✅ | Hotspot pins + dropdown in the ride form; `GET /api/rides/hotspots` returns 12 categorized points (campus gates / academic / residential / transit hubs) with coordinates that also power the proximity matching in #6. |
| 8 | Scheduled Ride Booking | ✅ | Ride can be created for a future time; listing filters by scheduled time. *(`rides.scheduled_at` + ISO parsing, past-time rejection on create, class-time window matching in `/match`.)* |
| 19 | Multi-Stop Ride Support | ✅ | A ride can have >1 drop-off; route shows ordered stops. *(`ride_stops` table with `sequence` + `status` pending/reached/departed; per-passenger `pickup_stop`/`dropoff_stop` on join; driver-only stop-progress endpoint.)* |

### Sprint 3 — Tracking & Safety (weeks 5-6)
| # | Feature | Status | Acceptance criteria |
|---|---------|--------|---------------------|
| 2 | Live GPS Ride Tracking | ✅ | Coordinates update ≤3s; share link shows live position (currently 5s polling, not WS). |
| 3 | Female-Only Ride Mode | ✅ | Female users can toggle; male riders/drivers fully hidden from matches. *(`rides.female_only`; only female drivers may create, only female riders may join, and `/match` + ride listing filter them out for everyone else.)* |
| 4 | In-App SOS Button | ✅ | SOS dispatches mock alerts to saved contacts + campus security with lat/lng; admin can resolve. |
| 12 | Trusted Contact Sharing | ✅ | Contacts persist in DB; auto-share mocks delivery of ride/tracking link; SOS reads contacts from DB. |
| 15 | Ride Chat (In-App Messaging) | ✅ | Driver + accepted passengers chat in real time (WS); messages persist; non-participants rejected (4403). |

### Sprint 4 — Payments & Earnings (weeks 7-8) — ✅ **COMPLETE (5/5)**
| # | Feature | Status | Acceptance criteria |
|---|---------|--------|---------------------|
| 5 | Ride Cost Splitter | ✅ | total = base_fare × surge; split across accepted passengers **weighted by seats** (largest-remainder rounding at paisa resolution, so shares sum exactly to `total`); breakdown shown. |
| 13 | Peak Hour Surge Indicator | ✅ | Surge reflects current hour (Asia/Dhaka) + live ride volume; badge shown on booking screen. |
| 9 | Wallet & bKash Integration | ✅ | Prepaid wallet (`wallets` + append-only `transactions` ledger); top-up runs bKash's real tokenized-checkout flow (grant → create → redirect → execute → query) against a simulated gateway selected by `DEMO_MODE`; seat-weighted fare auto-settles rider → driver at `end_ride`; driver cash-out; `/api/wallet/reconcile` proves balance == SUM(ledger). |
| 10 | Ride History & Receipt Log | ✅ | Past trips list + downloadable receipt. *(Both roles — driver and rider. Receipt is print-to-PDF plus a `.txt` download, amounts read from the ledger, participants-only.)* |
| 16 | Driver Earnings Dashboard | ✅ | Weekly earnings from completed rides, ride count, upcoming payouts. *(Reads `transactions.kind='ride_credit'` — the wallet ledger — so the dashboard and the wallet cannot disagree. 8-week bar chart bucketed in Asia/Dhaka, per-ride breakdown, and completed-but-unsettled rides surfaced separately instead of being silently dropped.)* |

### Sprint 5 — Quality & Admin Controls (weeks 9-10) — 🚩 **CURRENT SPRINT**
| # | Feature | Status | Acceptance criteria |
|---|---------|--------|---------------------|
| 7 | Driver Rating & Review | ❌ | Post-ride 1-5 star + comment; average shown on driver profile. |
| 17 | Admin Complaint Panel | ✅ | File complaint; admin review + notes + statuses + stats. |
| 18 | Ride Cancellation Policy & Penalty | ❌ | Cancel before dispatch = free; after dispatch = penalty shown as warning. |
| 20 | Eco/Footprint Tracker | ✅ | CO₂ saved per completed ride vs solo; aggregated totals + trees/fuel equivalents. |

## 4. Recommended build order for the remaining 2 features

Four items from the original nine (#3 Female-Only, #8 Scheduled, #6 Matching, #19 Multi-Stop)
shipped in the Sprint 2/3 completion pass and have been removed from this list.

Ordering rule changed: the previous list was strictly cheap → expensive, which is what pulled
Sprint-5 work ahead of unfinished Sprint-4 work. It is now **sprint-first, then cheap → expensive
within a sprint**, so Sprint 4 closes before Sprint 5 opens.

### Sprint 4 (current) — must close first
~~1. **Driver Earnings Dashboard (#16)**~~ — ✅ **DONE (2026-09-01).** Built on the wallet
   ledger rather than the `rides` re-aggregation originally sketched here — see §4.2.
~~2. **Ride History & Receipt Log (#10)**~~ — ✅ **DONE (2026-09-01).** Closes Sprint 4.
   See §4.3.
~~3. **Wallet & bKash Integration (#9)**~~ — ✅ **DONE (2026-09-01).** Prepaid ledger +
   simulated bKash tokenized checkout. Architecture in §4.1 below.

### Sprint 5 — after Sprint 4 is green
4. **Driver Rating & Review (#7)** — add `reviews` table (ride_id, reviewer_id, reviewee_id, stars, comment); post-ride prompt on ride detail; avg rating on the driver listing. *(≈1 day)*
5. **Ride Cancellation Policy & Penalty (#18)** — `rides.status` already accepts `'cancelled'` in its CHECK constraint but **no route ever sets it**; add the cancel flow + penalty fee (rider cancels after driver accepted → fee) + frontend warning modal. *(≈1 day)*

**Real-time GPS upgrade (recommended, high value):** convert `/track/[token]` + dashboard tracking to a WebSocket (the chat WS in `backend/app/routes/chat.py` is a ready template). Meets NFR-1 (<2s SOS/live updates) and SRS 3.3.4.

### 4.1 Wallet architecture as built (#9)

**Money model — prepaid ledger.** The gateway is touched only at the edges (top-up in,
cash-out out); ride settlement is an internal wallet-to-wallet transfer, so a ride can
always settle even with no network.

**Gateway — simulated, real flow.** `app/payments/` defines a `PaymentGateway` interface
with two implementations chosen by `DEMO_MODE`: `mock_bkash.py` (local, deterministic test
numbers) and `real_bkash.py` (live `tokenized.sandbox.bka.sh` calls via stdlib urllib, so
no new dependency). Switching to the live gateway changes **no route, table or page** —
only which class the factory returns. Credentials come from `BKASH_APP_KEY`,
`BKASH_APP_SECRET`, `BKASH_USERNAME`, `BKASH_PASSWORD` and are never committed.

**Safety properties enforced in `wallet_service.py`:**
- *Append-only ledger.* `transactions` is never UPDATEd or DELETEd; a correction is a new
  opposing row. `wallets.balance` is a cached mirror, verified by `/api/wallet/reconcile`.
- *Atomicity.* Rider debit + driver credit run inside one `BEGIN IMMEDIATE` transaction.
- *Idempotency.* `uq_transactions_ride_leg(ride_id, user_id, kind)` makes a second
  settlement a no-op; `uq_transactions_payment(payment_id)` makes a re-executed top-up a
  no-op. Both are exercised by the verification run.
- *No invented money.* A passenger who cannot pay is recorded as unsettled and the driver
  is simply not credited for that leg.
- *Trust boundary.* The gateway redirect carries `?status=`, which is **ignored**; only the
  server-side `execute_payment()` can credit a wallet.
- *Gateway durability.* The simulated gateway rehydrates any unknown paymentID from its
  `bkash_payments` row. Found in the post-build audit: with purely in-memory state an
  authorised-but-unexecuted payment became permanently unexecutable after a restart, and
  `uvicorn --reload` restarts on every code edit. Fixed and regression-tested.

**Commission.** `transactions.platform_fee` exists and is populated, with
`PLATFORM_COMMISSION_RATE` defaulting to `0.0` — enabling a cut later is a config change,
not a migration plus backfill.

**Deliberately out of scope:** refunds and cancellation penalties, which belong to Sprint 5
#18 Ride Cancellation Policy. The `refund` ledger kind is reserved so #18 can post
reversals without a schema change.

### 4.2 Driver Earnings as built (#16)

**Source of truth: the ledger, not a recomputation.** This item originally proposed
re-deriving earnings from `base_fare × surge_multiplier`. Once #9 landed that became the
wrong call: a driver earned exactly what was credited to them, so the dashboard reads
`transactions.kind = 'ride_credit'`. Deriving the number a second way would let the
earnings screen and the wallet disagree — the classic way a payments UI loses trust.

**Endpoints** (`/api/earnings`): `summary` (lifetime net, ride count, this week vs last,
payout ready, distance, passengers), `weekly?weeks=8` (per-ISO-week series), and
`rides?limit=25` (per-ride breakdown).

**Unsettled rides are reported, not hidden.** A completed ride with no `ride_credit` row
— it finished before wallets existed, or a passenger could not pay — appears in its own
warning band with the amount that was never received, and is excluded from every total.
Silently dropping those rides would under-report; folding them in would over-report.

**Weeks are bucketed in Asia/Dhaka** (matching the surge schedule) with empty weeks kept,
so an idle stretch reads as idle instead of compressing the time axis.

**Chart.** One series, so no legend — the heading names it. Fill `#00a888`, a deeper step
of the brand teal: `--primary` (#00d4aa) sits at OKLCH L 0.775, outside the 0.48–0.67
dark-mode band, and was rejected by the palette validator. Axis ticks are snapped to
round values, values are direct-labelled only on the peak and the current week, all bars
carry a hover tooltip, and a table toggle exposes the same data non-visually.

### 4.3 Ride History & Receipts as built (#10)

**Both roles, one log.** #16 answers "what did I earn as a driver"; this answers "where
have I been and what did it cost me" for riders too. A rider with no driver profile still
gets a full trip list and a receipt for every ride.

**No new schema**, as planned — reads `rides`, `ride_passengers`, `ride_stops` and
`transactions`.

**Amounts come from the ledger**, consistent with #9 and #16: a settled ride reports its
actual `ride_debit` / `ride_credit` row; an unsettled one reports what was *owed* and is
flagged unpaid, rather than showing a misleading zero. The receipt shows expected vs
actual side by side in that case.

**One receipt, two views.** Driver and rider on the same ride get the **same receipt
number** (`ARH-YYYYMMDD-XXXXXX`, deterministic from the ride id) but role-appropriate
lines: the driver sees "Fare received from passengers", the rider sees "Your share of the
fare". Verified: the riders' shares sum exactly to the driver's credit and to the
splitter's total.

**Downloadable two ways**, both dependency-free: `window.print()` with a print stylesheet
that strips the sidebar and buttons (the "frontend print/PDF" route the plan proposed),
and a Blob `.txt` download named after the receipt number.

**Access control:** receipts are participants-only — a non-participant gets 403, an unknown
ride 404.

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
>
> **Update (2026-08-31, start of Sprint 4):** the Sprint 2/3 completion pass landed after
> the note above — features #3, #6, #8, #14 and #19 are now implemented, and a first
> pytest file (`backend/tests/test_campus_features.py`) is committed. §3's status column
> and §4's build order have been re-synced with the codebase; §6.3's test items updated.

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
- ❌ **`requirements.txt` stale** — refresh pins to the tested versions. Also: `passlib` is listed but never imported (only referenced in an `auth.py` comment), while `bcrypt` — imported directly by `app/auth.py` and `app/database.py` — is pulled in only as a transitive extra of `passlib[bcrypt]`. Pin `bcrypt` explicitly and drop `passlib`. `pytest` and `httpx` are absent entirely.
- 🔶 **Test suite partially committed** — `backend/tests/test_campus_features.py` is now in the repo (5 pytest cases covering #14 hotspots, #3 female-only, #19 multi-stop, #6 matching, #8 scheduled; isolated throwaway DB via `DATABASE_PATH`). Still to port: the 54-check backend regression script (`/tmp/opencode/test_backend.py`) and coverage for auth / tracking / SOS / chat / eco / complaints.
- ❌ **Committed test suite cannot run as-is** — `requirements.txt` lists neither `pytest` nor `httpx` (required by FastAPI's `TestClient`), and `test_campus_features.py` hardcodes the POSIX path `/tmp/test_arooohi.db`, which does not resolve on Windows. Add both pins and derive the temp DB path from `tempfile.gettempdir()`.
- ⏳ **Live e2e harness not committed (Session 10)** — Playwright suite at `/tmp/opencode/e2e/live-test.js` (45 checks, 45/45 green); port into a `backend/` or `e2e/` folder for CI.
- ⏳ **Cross-engine e2e (Session 11 to-do)** — the UI stack is engine-agnostic (Next.js/React/Leaflet/WebSockets; no Chrome-only APIs — only standard `navigator.geolocation`/`clipboard`). Both engines are already testable via `./launch.sh --browser chrome|firefox` (chromium at `/opt/helium/chrome`, gecko = Zen via flatpak). TODO: run the Playwright suite against BOTH engines to prove it, and add the frontend feature-map as a `/demo` page.
- ❌ **Mock notifications scattered** — consolidate into a `notifications.py` service.
- ❌ **Hardcoded `ZONES` in `rides.py`** — move to a seeded table (unlocks #6/#14).
- ✅ **Frontend `API` const duplicated** — centralized in `lib/api.ts` (`API`/`WS`/`API_BASE`, overridable via `NEXT_PUBLIC_API_URL`); all pages import from it. With this, switched everything to explicit IPv4 `127.0.0.1` (backend binds 127.0.0.1, CORS allows both `localhost:3000` and `127.0.0.1:3000`, tracking share URLs use `127.0.0.1`) — fixes the gecko-only failure caused by `localhost`→`::1` (IPv6) when the backend binds IPv4-only.
- ✅ **One-command launcher** — `./launch.py` / `./launch.sh` / `launch.bat`: starts backend+frontend, renders the logo, opens the site fullscreen (F11 to toggle, `--windowed` to skip), auto-stops + WAL-checkpoints the DB when the browser closes, plus `--no-browser`/`--browser chrome|firefox`/`--detect`/`status`/`stop`. Cross-platform (pure stdlib; tested on Linux, code-reviewed for macOS/Windows).

### 6.4 Frontend bugs & UX (🟡)
- ✅ **Tracking page: duplicate point sources + leak on unmount** — `dashboard/page.tsx`. Single `recordPoint`, `sessionRef` guard, unmount cleanup, `headers` memoized.
- ❌ **Unbounded `points` array + DB bloat** — cap client points; add retention policy.
- ✅ **Ride chat link shown to non-participants** — `dashboard/rides/page.tsx`. Gated to `mine || ride.driver_id === me`.
- ✅ **Chat page: 4401/4403 gives no explanation** — `dashboard/chat/[rideId]/page.tsx`. Fatal error states shown.
- ✅ **Infinite spinners on failed fetches** — eco/rides/contacts pages now render error states.
- ✅ **`alert()` used for feedback** — rides/contacts now use inline notices.
- ✅ **Surge schedule endpoint unused** — rides page shows an hourly "upcoming peak" strip + current-hour marker (fulfils SRS #13).
- ✅ **Map re-centers on every GPS tick** — `TrackingMap.tsx`. Auto-follow only until the user interacts + "🎯 Re-center" button.
- ✅ **Track page polls after session ended** — `track/[token]/page.tsx`. Stops polling when `is_active=false`.

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
