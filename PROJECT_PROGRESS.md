# Arooohi — Progress Report

> SRS source: `Misc./Arooohi_Complete_SRS_Report.pdf`. Roadmap + backlog: [`PROJECT_PLAN.md`](./PROJECT_PLAN.md).
> Statuses: ✅ done · 🔶 partial · ❌ not started. Updated 2026-09-01 (Sprint 4 in progress).

## 1. Overall

**18 / 20 SRS features complete (90%).** Auth, safety, Ornab's 5 modules (cost
splitter, trusted contacts, ride chat, eco tracker, peak-hour surge) and the
Sprint 2/3 completion pass (female-only mode, smart matching, scheduled booking,
multi-stop, hotspots) are shipped. The remaining 2 features are all additive on
the existing rides core and are scheduled per `PROJECT_PLAN.md` §4.

**Sprint status: Sprints 1-4 are now fully closed** (2/2, 4/4, 5/5, 5/5).
#9 Wallet & bKash, #16 Driver Earnings and #10 Ride History all landed
2026-09-01, completing Sprint 4. **Sprint 5 is now current at 2/4** — #17
Complaints and #20 Eco were delivered early, leaving **#7 Driver Rating** and
**#18 Cancellation Policy** as the only remaining SRS features. Note that two Sprint-5 features (#17 Admin Complaint Panel,
#20 Eco Tracker) were also delivered ahead of sequence; nothing from an earlier
sprint is outstanding, so no downstream work is blocked.

## 2. Feature status

| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | BRACU Student Verification | ✅ | `@g.bracu.ac.bd` + 6-digit OTP (demo: OTP shown in UI/console) |
| 2 | Live GPS Ride Tracking | ✅ | 5s polling via `/track/[token]`, share link + live map |
| 3 | Female-Only Ride Mode | ✅ | Driver creation & passenger join/search gender filtering + verified gating |
| 4 | In-App SOS Button | ✅ | `sos_alerts` table; mock notification; admin resolve |
| 5 | Ride Cost Splitter | ✅ | `GET /api/rides/{id}/split` — fare × surge, seat-weighted largest-remainder split (sums exactly to total) |
| 6 | Campus Zone Smart Matching | ✅ | `/api/rides/match` multi-factor scoring (route, timetable, intermediate stops, female-only) |
| 7 | Driver Rating & Review | ❌ | No `reviews` table |
| 8 | Scheduled Ride Booking | ✅ | `rides.scheduled_at` field + advance booking validation & UI selector |
| 9 | Wallet & bKash Integration | ✅ | Prepaid `wallets` + append-only `transactions` ledger; simulated bKash tokenized checkout behind a `PaymentGateway` interface (no live client — credentials need merchant onboarding); auto-settlement at ride end; cash-out; reconciliation endpoint |
| 10 | Ride History & Receipt Log | ✅ | Both-role trip log + per-ride receipt (print-to-PDF and `.txt` download); ledger-backed amounts; participants-only |
| 11 | Driver Vehicle Verification | ✅ | Doc upload + admin approve/reject + role flip |
| 12 | Trusted Contact Sharing | ✅ | DB-backed CRUD; auto-share on tracking start (mock delivery) |
| 13 | Peak Hour Surge Indicator | ✅ | Seeded 24h + live ride-volume bump; Asia/Dhaka timezone |
| 14 | Campus Pickup Hotspots | ✅ | Categorized hotspots (Gates, Academic, Transit) + `/api/rides/hotspots` API + Interactive TrackingMap & selector UI |
| 15 | Ride Chat (In-App Messaging) | ✅ | WS `/ws/chat/{ride_id}` + REST history + UI |
| 16 | Driver Earnings Dashboard | ✅ | Reads the wallet ledger (`ride_credit`); 8-week Asia/Dhaka bar chart, per-ride breakdown, unsettled rides surfaced separately, payout-ready balance |
| 17 | Admin Complaint Panel | ✅ | Full CRUD + statuses + stats + admin notes |
| 18 | Ride Cancellation Policy & Penalty | ❌ | `cancelled` status reserved; no penalty logic |
| 19 | Multi-Stop Ride Support | ✅ | `ride_stops` table + waypoint status tracking + passenger pickup/drop-off stop joining |
| 20 | Eco/Footprint Tracker | ✅ | CO₂ saved vs solo, trees + fuel equivalents, gamified UI |

## 3. Sprint completion (SRS §7 mapping)

| Sprint | Score | Detail |
|--------|-------|--------|
| 1 — Auth | 2/2 ✅ | Verification (#1), Driver verification (#11) |
| 2 — Matching & Logistics | 4/4 ✅ | Hotspots (#14), Matching (#6), Scheduled (#8), Multi-Stop (#19) complete |
| 3 — Tracking & Safety | 5/5 ✅ | GPS (#2), SOS (#4), Contacts (#12), Chat (#15), Female-Only (#3) complete |
| 4 — Payments & Earnings | 5/5 ✅ | Splitter (#5), Surge (#13), Wallet & bKash (#9), Driver Earnings (#16), Ride History (#10) — **sprint complete** |
| 5 — Admin & Quality | 2/4 🔶 | 🚩 **CURRENT** — Complaints (#17), Eco (#20) done; reviews (#7), cancellation (#18) missing |

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

### Sprint 2/3 completion pass (after 2026-08-03) — 5 features closed
- **#3 Female-Only Ride Mode** — `rides.female_only` column + migration; only female
  drivers may create such a ride, only female riders may join; `/api/rides/match` and the
  ride listing filter them out for everyone else; UI toggle on the rides page.
- **#6 Campus Zone Smart Matching** — `GET /api/rides/match` multi-factor scorer
  (exact pickup +50, ≤1.5 km haversine proximity +35, direct destination +50,
  intermediate-stop match +45, ±30 min class-time +15; <50 dropped when both filters set),
  returning `match_score` + human-readable `match_reasons`.
- **#8 Scheduled Ride Booking** — `rides.scheduled_at` with ISO parsing, past-time
  rejection on create, and class-time window matching.
- **#14 Campus Pickup Hotspots** — promoted from 🔶 to ✅: `GET /api/rides/hotspots`
  serves 12 categorized points (gates / academic / residential / transit) whose
  coordinates also drive #6's proximity scoring.
- **#19 Multi-Stop Ride Support** — `ride_stops` (`sequence`, `status` pending/reached/
  departed) + per-passenger `pickup_stop`/`dropoff_stop` on join + driver-only stop-progress
  endpoint; columns added idempotently via `_ensure_column()`.
- **First committed tests** — `backend/tests/test_campus_features.py`, 5 pytest cases
  covering exactly these features against an isolated throwaway DB.

### Feature 9 — Wallet & bKash Integration (2026-09-01)
- **Schema:** `wallets` (cached balance), `transactions` (append-only signed ledger with
  `platform_fee`), `bkash_payments` (one row per checkout attempt), plus three unique
  indexes that enforce idempotency.
- **Gateway layer:** `app/payments/` — `base.py` (interface), `mock_bkash.py` (simulated,
  deterministic test numbers), `factory.py` (returns it, and raises if `DEMO_MODE=0`
  rather than pretending a simulator handles real money). No live client is included:
  bKash issues credentials only through merchant onboarding.
- **Simulated checkout page:** served by the BACKEND at `/bkash/checkout/{paymentID}` so the
  browser genuinely leaves Arooohi to authenticate, exactly as a real gateway forces.
  Mounted only when `DEMO_MODE=1`.
- **Settlement:** `end_ride` debits each accepted passenger their seat-weighted share and
  credits the driver — atomically and idempotently — reusing the exact numbers `/split`
  displays. `rides.py::_split_total` now delegates to `wallet_service.split_total`, which
  also clears the duplication flagged in PLAN §6.3.
- **Join gating:** joining now returns **402** with the exact shortfall when the wallet
  cannot cover the projected share.
- **Verified:** 20+ live checks — full 4-step top-up; redirect-alone-credits-nothing;
  double execute (idempotent); all four failure test-numbers; balance gate; settlement
  matching the splitter exactly; re-settlement no-op; cash-out plus overdraft refusal;
  reconciliation balanced for both parties. Full browser run of the UI flow with 0 console
  errors. `npx tsc --noEmit` clean; `npm run build` clean (19 routes).
- **Post-build audit (22 adversarial checks, all passing):** input validation, forged
  callback, cross-user payment theft, 6-way concurrent execute, 5-way concurrent
  `end_ride`, spend-down-after-join, and ledger reconciliation for every party.
  **One real bug found and fixed:** the simulated gateway held state only in memory, so
  an authorised-but-unexecuted payment became permanently unexecutable after a restart
  (and `--reload` restarts on every edit). It now rehydrates from `bkash_payments`.
- **Known demo-only weakness:** `/bkash/checkout/{id}/confirm|cancel` are unauthenticated
  by design (they stand in for a third party), so anyone who learns a paymentID can
  cancel a *pending* top-up. They cannot credit or steal anything — crediting still
  requires the owner's authenticated execute. A real gateway solves this with a
  single-use signed checkout URL.
- **Out of scope by design:** refunds / cancellation penalties belong to #18; the `refund`
  ledger kind is reserved for it.

### Feature 16 — Driver Earnings Dashboard (2026-09-01)
- **No new schema.** Reads `transactions.kind = 'ride_credit'` — the wallet ledger — so the
  earnings figure and the wallet balance are the same number by construction. The
  `rides`-recomputation approach originally sketched in PLAN §4 was dropped for this reason.
- **Endpoints:** `GET /api/earnings/summary`, `/weekly?weeks=8` (1-26), `/rides?limit=25`.
- **Unsettled rides surfaced, not hidden:** completed rides with no credit (pre-wallet, or a
  passenger who could not pay) get their own warning band with the uncollected amount and are
  excluded from all totals. The demo DB has exactly one such ride, which is what made this
  case obvious.
- **Weeks bucketed in Asia/Dhaka**, Monday start, empty weeks preserved so idle stretches
  read as idle.
- **Chart:** single-series bars; fill `#00a888` chosen because `--primary` failed the
  dark-mode lightness band (L 0.775 vs the 0.48-0.67 band) in the palette validator. Round
  axis ticks, direct labels only on peak + current week, hover tooltip on every bar, and a
  table toggle for non-visual reading.
- **Verified:** 19 backend checks — totals matching the sum of credits, unsettled excluded,
  payout == wallet balance, weekly bucketing with gaps, one current week, weekly total ==
  summary total, riders see an empty dashboard rather than an error, unauthenticated 401.
  Browser run: 8 bars rendered, hover tooltip works, table toggle shows 8 rows, 0 console
  errors. `tsc --noEmit` clean; `npm run build` clean (20 routes).

### Feature 10 — Ride History & Receipt Log (2026-09-01) — closes Sprint 4
- **No new schema.** Reads `rides`, `ride_passengers`, `ride_stops`, `transactions`.
- **Both roles:** `GET /api/history?role=all|driver|passenger&status=completed|all`,
  `GET /api/history/summary` (lifetime trips / spent / earned / net / distance), and
  `GET /api/history/{ride_id}/receipt`.
- **Ledger-backed amounts**, matching #9 and #16 — settled rides report the real
  transaction; unsettled ones report the amount *owed* and are flagged, never shown as 0.
- **Shared receipt number** `ARH-YYYYMMDD-XXXXXX`, deterministic from the ride id, so a
  driver and rider quoting the same trip quote the same number — with role-appropriate
  lines on each side.
- **Downloadable:** `window.print()` + a print stylesheet that hides the sidebar and
  action buttons, plus a Blob `.txt` download named after the receipt number.
- **Verified:** 27 backend checks — riders' shares summing exactly to the driver's credit
  and the splitter total, a 2-seat rider paying exactly double a 1-seat rider, per-passenger
  pickup/drop-off stops on the receipt, unsettled rides flagged with the owed amount,
  non-participant 403, unknown ride 404, unauthenticated 401, role filters, lifetime
  summary. Browser run confirmed the print view hides the chrome and the `.txt` download
  produces a correct file. 0 console errors; `tsc --noEmit` clean; `npm run build` clean
  (21 routes).
- **One bug found by rendering it:** `issued_at` carries a `+06:00` offset while ledger
  timestamps are naive UTC; the formatter appended `Z` unconditionally and printed
  "Invalid Date". Both history pages now detect an existing offset before normalising.

### Sprint 4 cross-feature audit (2026-09-01)
Audited #9, #16 and #10 together, since the interesting failures are three features
disagreeing about the same money. **Zero disagreements** — wallet balance, earnings
total, weekly series, per-ride nets and history totals all reconcile exactly, and both
parties' ledgers stayed balanced throughout. **Three real issues found and fixed**, all
one family: *partial settlement was invisible.*

- **Earnings under-reported uncollected fares (bug).** `_unsettled()` tested
  `NOT EXISTS (... ride_credit)` — all-or-nothing. A ride where one passenger paid and
  another could not HAS a credit row, so its shortfall vanished: a driver owed 400 who
  received 200 saw `unsettled_value = 0`. Replaced with `_uncollected()`, which compares
  the splitter's expected total against what was actually credited (gross of fee, so a
  commission is never mistaken for a shortfall) and reports the difference. Summary now
  also splits `fully_unpaid_rides` vs `partially_paid_rides`.
- **Receipts claimed "Paid" on a partially settled ride.** Added `fully_paid` and
  `shortfall`; the badge now reads "Partially settled", the payment method is qualified,
  and both the HTML and `.txt` receipts state how much was never received.
- **Receipts were issued for rides that had not happened.** `GET /history/{id}/receipt`
  served a document for `scheduled`/`active` rides — proof of payment for a trip that
  never occurred. Now **400** with a clear message.

Verified after the fixes: owed(400) == received(200) + uncollected(200); all three earlier
suites re-run green (#9 22 checks, #16 19, #10 27) with no regressions; `npm run build`
clean (21 routes).

## 6. Known gaps & accepted deviations

| Area | Gap | Mitigation / plan |
|------|-----|-------------------|
| Real-time tracking | GPS is 5s polling, not WebSockets (NFR-1 <2s) | Reuse chat WS as template; planned in `PROJECT_PLAN.md` §4 |
| Database | SQLite (SRS: PostgreSQL/PostGIS/MongoDB) | Accepted for demo; add WAL + FK indexes now |
| Payments | Simulated gateway only; a live bKash client needs merchant credentials + an HTTPS callback | Routes depend on the `PaymentGateway` interface, so a live client can be added without touching routes, tables or pages |
| Notifications | SOS + auto-share mocked (console log) | Centralize into a notifications service |
| Verification | Manual doc review (SRS: manual/automated) | Accepted; OCR automation out of scope |
| Mobile | Web only (SRS: React Native) | Future work |
| Tests | Partial: `backend/tests/test_campus_features.py` only (5 cases, features #3/#6/#8/#14/#19). `pytest`+`httpx` absent from `requirements.txt`; suite hardcodes POSIX `/tmp/test_arooohi.db` so it will not run on Windows | Add the pins, derive the temp path from `tempfile.gettempdir()`, and port the 54-check regression script + Playwright e2e harness |

## 7. Not-yet-fixed defects (tracked in PROJECT_PLAN.md §6)

The 🔴 security/correctness backlog from the Session-8 audit was cleared in the
Session-9 hardening pass (see §5). Remaining gaps are the accepted deviations in
§6: console-mock notifications (SOS + auto-share), 5s polling tracking (NFR-1 <2s),
only a partial pytest suite (and one that cannot run from `requirements.txt` as-is),
SQLite instead of PostgreSQL/PostGIS, and the 5 missing features in §2.

## 8. Next actions (priority order)

1. ✅ Done (Sessions 9–13) — see HISTORY/PLAN. Live-browser tests 45/45 (Session 10);
   cross-platform launcher + IPv4 fix (Session 12); desktop-installer attempt reverted (Session 13).
2. Commit the Session-12 launcher + IPv4 work (currently uncommitted) when the team is ready.
3. **Sprint 4 is closed.** Sprint 5 remains: **#7 Driver Rating & Review** (needs a
   `reviews` table) and **#18 Ride Cancellation Policy & Penalty** (the `cancelled` status
   exists in the CHECK constraint but no route sets it; the `refund` ledger kind is already
   reserved for its reversals).
4. Make the committed test suite runnable: add `pytest` + `httpx` to `requirements.txt`
   and replace the hardcoded `/tmp/test_arooohi.db` with `tempfile.gettempdir()`.
5. Extend coverage: port the 54-check regression script (`/tmp/opencode/test_backend.py`)
   and the Playwright e2e harness (`/tmp/opencode/e2e/live-test.js`); run against BOTH engines.
6. Upgrade live tracking to WebSockets (NFR-1).
7. Then Sprint 5: Driver Rating (#7) and Cancellation Policy (#18) per `PROJECT_PLAN.md` §4.
