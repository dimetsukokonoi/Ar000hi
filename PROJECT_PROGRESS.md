# Arooohi — Progress Report

> SRS source: `Misc./Arooohi_Complete_SRS_Report.pdf`. Roadmap + backlog: [`PROJECT_PLAN.md`](./PROJECT_PLAN.md).
> Statuses: ✅ done · 🔶 partial · ❌ not started. Updated 2026-08-03.

## 1. Overall

**10 / 20 SRS features complete (≈50%).** Auth, safety, and Ornab's 5 modules
(cost splitter, trusted contacts, ride chat, eco tracker, peak-hour surge) are
shipped and verified. The remaining 9 features are all additive on the existing
rides core and are scheduled per `PROJECT_PLAN.md` §4.

## 2. Feature status

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | BRACU Student Verification | ✅ | `@g.bracu.ac.bd` + 6-digit OTP (demo: OTP shown in UI/console) |
| 2 | Live GPS Ride Tracking | ✅ | 5s polling via `/track/[token]`, share link + live map |
| 3 | Female-Only Ride Mode | ✅ | Driver creation & passenger join/search gender filtering + verified gating |
| 4 | In-App SOS Button | ✅ | `sos_alerts` table; mock notification; admin resolve |
| 5 | Ride Cost Splitter | ✅ | `GET /api/rides/{id}/split` — fare × surge, even split |
| 6 | Campus Zone Smart Matching | ✅ | `/api/rides/match` multi-factor scoring (route, timetable, intermediate stops, female-only) |
| 7 | Driver Rating & Review | ✅ | `reviews` table, UNIQUE(ride,reviewer,reviewee); post-ride prompt + profile average |
| 8 | Scheduled Ride Booking | ✅ | `rides.scheduled_at` field + advance booking validation & UI selector |
| 9 | Wallet & bKash Integration | ✅ | `wallets` + append-only `wallet_transactions` ledger; mock bKash top-up |
| 10 | Ride History & Receipt Log | ✅ | `/api/history` + `/api/history/{id}/receipt`; printable receipt modal |
| 11 | Driver Vehicle Verification | ✅ | Doc upload + admin approve/reject + role flip |
| 12 | Trusted Contact Sharing | ✅ | DB-backed CRUD; auto-share on tracking start (mock delivery) |
| 13 | Peak Hour Surge Indicator | ✅ | Seeded 24h + live ride-volume bump; Asia/Dhaka timezone |
| 14 | Campus Pickup Hotspots | ✅ | Categorized hotspots (Gates, Academic, Transit) + `/api/rides/hotspots` API + Interactive TrackingMap & selector UI |
| 15 | Ride Chat (In-App Messaging) | ✅ | WS `/ws/chat/{ride_id}` + REST history + UI |
| 16 | Driver Earnings Dashboard | ✅ | `/api/earnings/summary` weekly buckets + `/payout` sweep into wallet |
| 17 | Admin Complaint Panel | ✅ | Full CRUD + statuses + stats + admin notes |
| 18 | Ride Cancellation Policy & Penalty | ✅ | Free before dispatch; 20% fee after (floor 20, ceiling 150 BDT) charged to wallet |
| 19 | Multi-Stop Ride Support | ✅ | `ride_stops` table + waypoint status tracking + passenger pickup/drop-off stop joining |
| 20 | Eco/Footprint Tracker | ✅ | CO₂ saved vs solo, trees + fuel equivalents, gamified UI |

## 3. Sprint completion (SRS §7 mapping)

| Sprint | Score | Detail |
|--------|-------|--------|
| 1 — Auth | 2/2 ✅ | Verification (#1), Driver verification (#11) |
| 2 — Matching & Logistics | 4/4 ✅ | Hotspots (#14), Matching (#6), Scheduled (#8), Multi-Stop (#19) complete |
| 3 — Tracking & Safety | 5/5 ✅ | GPS (#2), SOS (#4), Contacts (#12), Chat (#15), Female-Only (#3) complete |
| 4 — Payments & Earnings | 5/5 ✅ | Splitter (#5), Surge (#13), Wallet (#9), History (#10), Earnings (#16) |
| 5 — Admin & Quality | 4/4 ✅ | Complaints (#17), Eco (#20), Reviews (#7), Cancellation (#18) |

## 4. Verification evidence (2026-07-31)

### Backend
- `import app.main` boots cleanly; `init_db()` idempotent (tables + surge seed + admin).
- Full API flow verified end-to-end (throwaway DB): register/verify → contacts CRUD +
  auto-share + share history → surge current/schedule (with `is_current`) → ride
  create (w/ `total_seats`)/join (capacity-checked)/accept/start/end → seat-weighted
  split (sums exactly to total) → WS chat broadcast + persistence → 4401/4403/4429
  close codes → eco for driver AND rider → leaderboard → SOS resolve 404 → tracking
  ownership/token → complaints + rate limiting.
- Session-9 test pass: **backend 54/54 checks** (TestClient, throwaway DB) + **live API
  smoke** (register, surge `is_current`, total_seats, 32-hex token, share history,
  login rate-limit 429).

### Frontend (Node v24.18.0, user-local)
- `npm run lint` — **0 problems**.
- `npx tsc --noEmit` — **clean**.
- `npm run build` — **success, all routes compile**.

### Runtime state (checked recent sessions)
- **One-command launcher (Session 12):** `./launch.py` / `./launch.sh` / `launch.bat`
  boot backend + frontend, render the Arooohi logo, open the site fullscreen in the
  default browser, and auto-stop + WAL-checkpoint the DB when the browser closes.
  The app uses explicit IPv4 `127.0.0.1` (`frontend/lib/api.ts` `API`/`WS`/`API_BASE`;
  CORS allows `localhost:3000` + `127.0.0.1:3000`) — fixes a gecko/Firefox
  `localhost`→IPv6-`::1` failure. Desktop-installer attempt (Session 13) was reverted.
- Backend `:8000` (with `--reload`) and frontend `:3000` were **running**; the app is
  started/stopped with the launcher.
- `arooohi.db`: carries live user/test data (driver approved, completed ride,
  resolved SOS/complaint) — kept for the demo; pre-test backup at
  `Misc./arooohi.db.backup-20260731-214145`.
- `git status` — working tree has Session-12 work **uncommitted** (HEAD `ba43984`):
  `launch.py`/`launch.sh`/`launch.bat`, `scripts/ascii_logo.py`,
  `frontend/lib/api.ts` + the 15 page edits, `frontend/package.json`, backend CORS +
  tracking share-URL changes, and `PROJECT_PLAN.md` notes.

### Live browser test (Session 10, Playwright)
- Full end-to-end run of the live UI on both running servers: **45/45 passed,
  0 failed** across auth, contacts, GPS tracking, SOS, rides, cost splitter,
  surge, chat, driver verification, complaints, eco, and security gates.
- One bug found + fixed during the run: chat spam-guard path closed with HTTP
  403 instead of WS close code 4429 — now `await websocket.close(4429)` +
  `break` (`routes/chat.py`), matching `API.md`.
- Harness: `/tmp/opencode/e2e/live-test.js` (Playwright, `--headed`,
  executablePath `/opt/helium/chrome`); machine-readable report at
  `/tmp/opencode/e2e/report.json`; runtime logs `backend.log`/`frontend.log`.
- 34 screenshots captured → committed to `demo/live-test-screenshots/`.
- Test accounts (all `secret1/2/3`): `driver.live@g.bracu.ac.bd` (Test Driver),
  `rider.live@g.bracu.ac.bd` (Rider Person), `intruder.live@g.bracu.ac.bd`
  (Nosy User); admin `admin@g.bracu.ac.bd` / `admin123`.

## 5. Recent fixes (already applied)

- **Surge timezone bug**: hour lookup was UTC, seed is BD-local (UTC+6) → now `Asia/Dhaka` (`surge.py`).
- **Ride detail permission leak**: `GET /api/rides/{id}` now 403s non-participants (`rides.py`).
- **Chat WS close codes**: server now accepts-then-closes so 4401/4403 reach clients
  (was HTTP 403 → frontend retried forever) (`chat.py`).
- **Chat spam-guard close (Session 10)**: rate-limit path now uses WS close
  `4429` + `break` instead of HTTP 403, so the code the frontend/API.md expect
  actually reaches the client (`chat.py`).
- **Frontend reconnect**: auto-reconnect on WS drop, no retry on 4401/4403 (`chat/[rideId]/page.tsx`).
- **TypeScript/lint cleanup**: `any` → interfaces across 17 frontend files.

### Session 9 hardening pass (2026-07-31) — security + correctness
- **Auth**: default-secret fail-fast (when `DEMO_MODE!=1`); OTP hint only in DEMO_MODE;
  per-IP+email rate limiting for login/OTP (5/5 min → 429); inactive/nonexistent
  accounts rejected in `get_current_user_id`; password min 6 chars.
- **Tracking**: 32-hex share token; owner-only session read; stop on inactive → 404;
  frontend stops polling when ride ends; map auto-follow + re-center.
- **Surge**: `/schedule` now flags one `is_current` hour; live bump applies only to it.
- **Splitter**: seat-weighted shares, largest-remainder paisa rounding (sums exactly);
  join enforces capacity via `total_seats` (default 4).
- **Rides**: `end_ride` uses the FULL path length of the most recent inactive session.
- **Contacts**: BD phone validation; auto-share persists to `contact_shares` + share history.
- **Eco**: NULL-distance guard; top-10 leaderboard.
- **Chat**: spam guard (20 msgs/10s → 4429) + 500-char cap.
- **SOS/complaints/drivers**: 404 on missing resolve; `reported_id` existence check;
  `?status=` filter for pending drivers; upload ext from MIME.
- **DB**: WAL mode + FK indexes; `rides.total_seats` migration; `contact_shares` table.
- **Frontend**: rides page rewritten (surge schedule strip, seats, inline errors,
  participant-gated chat); eco/contacts/chat/admin error states; dashboard GPS
  double-post + interval-leak fixed.

## 6. Known gaps & accepted deviations

| Area | Gap | Mitigation / plan |
|------|-----|-------------------|
| Real-time tracking | GPS is 5s polling, not WebSockets (NFR-1 <2s) | Reuse chat WS as template; planned in `PROJECT_PLAN.md` §4 |
| Database | SQLite (SRS: PostgreSQL/PostGIS/MongoDB) | Accepted for demo; add WAL + FK indexes now |
| Payments | bKash mocked (console log) | Keep mock wallet; swap real API later |
| Notifications | SOS + auto-share mocked (console log) | Centralize into a notifications service |
| Verification | Manual doc review (SRS: manual/automated) | Accepted; OCR automation out of scope |
| Mobile | Web only (SRS: React Native) | Future work |
| Tests | No committed test suite | Add `backend/tests/` pytest suite |

## 7. Not-yet-fixed defects (tracked in PROJECT_PLAN.md §6)

The 🔴 security/correctness backlog from the Session-8 audit was cleared in the
Session-9 hardening pass (see §5). Remaining gaps are the accepted deviations in
§6: console-mock notifications (SOS + auto-share), 5s polling tracking (NFR-1 <2s),
no committed pytest suite, SQLite instead of PostgreSQL/PostGIS, and the missing
features in §2.

## 8. Next actions (priority order)

1. ✅ Done (Sessions 9–13) — see HISTORY/PLAN. Live-browser tests 45/45 (Session 10);
   cross-platform launcher + IPv4 fix (Session 12); desktop-installer attempt reverted (Session 13).
2. Commit the Session-12 launcher + IPv4 work (currently uncommitted) when the team is ready.
3. Ship the cheap wins: Female-Only Mode (#3), Earnings (#16), Ride History (#10).
4. Add a committed pytest suite (regression script at `/tmp/opencode/test_backend.py`)
   and the Playwright e2e harness (`/tmp/opencode/e2e/live-test.js`); run it against BOTH engines.
5. Upgrade live tracking to WebSockets (NFR-1).
6. Continue remaining features per `PROJECT_PLAN.md` §4.
