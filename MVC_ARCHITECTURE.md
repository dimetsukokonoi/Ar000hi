# Arooohi MVC architecture — demonstration guide

## What to say

“Arooohi uses API-based web MVC. React pages are the View, FastAPI request
handlers are the Controllers, and Python business rules plus SQLite persistence
form the Model. Controllers authenticate and validate incoming requests, call
models, and return results. React displays those results. Models do not import
FastAPI or depend on the user interface.”

This is a separate React frontend with an MVC backend, not a traditional
server-template application. React itself is not an MVC framework. Forms,
display formatting, local UI state, and API calls remain in the frontend;
authoritative booking permissions, matching, and payment rules run in the Model.

## Where each responsibility lives

| Part | Files | Responsibility |
| --- | --- | --- |
| Model | [`backend/app/models/`](backend/app/models/) | Business rules, calculations, permissions tied to domain data, database queries and transactions. |
| Controller | [`backend/app/controllers/`](backend/app/controllers/) | HTTP/WebSocket endpoints, request parameters, authentication dependencies, status codes, redirects and response dispatch. No SQL here. |
| View | [`frontend/app/`](frontend/app/), [`frontend/components/`](frontend/components/) | Pages, forms, maps, tables and user interaction. |
| Server-generated views | [`backend/app/views/receipts.py`](backend/app/views/receipts.py), [`checkout.py`](backend/app/views/checkout.py) | Turn prepared data into PDF receipts or the mock gateway's HTML page. No database queries. |
| Request schemas | [`backend/app/schemas/`](backend/app/schemas/) | Pydantic classes describing and validating input. Shared data contracts, not HTTP handlers or database tables. |
| Application setup | [`backend/app/main.py`](backend/app/main.py) | Create FastAPI app, initialize database, register controllers/error handler, configure CORS and static uploads. |
| Infrastructure | [`backend/app/payments/`](backend/app/payments/) | Payment gateway interface and simulator used by models. |

The Model does **not** require Django models or SQLAlchemy classes. Here, functions
and SQLite queries implement that responsibility. A class inheriting Pydantic's
`BaseModel` is an input schema; its name alone does not make it the MVC Model.

## Trace one booking during the demonstration

```text
React ride form (View)
  → POST /api/rides/{ride_id}/join
  → controllers/rides.py: join_ride (Controller)
  → models/rides.py: join_ride (Model)
  → SQLite ride_passengers table
  → result returned through Controller as JSON
  → React shows requested seat / top-up notice (View)
```

1. Open [`frontend/app/dashboard/rides/page.tsx`](frontend/app/dashboard/rides/page.tsx).
   The UI collects the selected seat count and pickup/drop-off choices.
2. Open [`backend/app/controllers/rides.py`](backend/app/controllers/rides.py).
   `@router.post(...)` connects the URL to `join_ride`. `Depends(get_current_user_id)`
   obtains the authenticated user. `JoinRideRequest` validates the JSON body.
3. The controller calls `model.join_ride(...)` with ordinary values and the schema.
   It contains no booking SQL or fare calculations.
4. Open [`backend/app/models/rides.py`](backend/app/models/rides.py).
   `join_ride` checks ride availability, female-only eligibility, capacity,
   duplicate requests and stop order; estimates the share; inserts the request.
   An insufficient wallet balance produces a top-up notice rather than preventing
   this reservation request.
5. The returned dictionary becomes JSON. The frontend displays the result. A
   request is still `requested` until the driver accepts it.

Important: the `passenger_id` returned by join and used in the accept URL is the
**ride-passenger request row ID**, not the user's account ID.

## Your five features

All five use [`controllers/rides.py`](backend/app/controllers/rides.py),
[`models/rides.py`](backend/app/models/rides.py), and the rides page above.

| Feature | Controller entry point | Model implementation to explain |
| --- | --- | --- |
| Campus Zone Smart Matching | `GET /api/rides/match` → `match_rides` | `ZONES`, `_haversine_km`, and `match_rides`: route/nearby-zone matching, timing and eligibility filtering, then match scoring. |
| Multi-Stop Ride Support | `create_ride`, `join_ride`, `update_stop_status` | Persist ordered `ride_stops`; validate pickup before drop-off; record stop progress. |
| Female-Only Ride Mode | `create_ride`, `join_ride`, `match_rides`, `list_rides` | Check stored user gender and the ride's `female_only` flag. Enforcement happens in the backend, not only through the UI toggle. |
| Scheduled Ride Booking | `create_ride`, `match_rides`, `list_rides` | Validate a future ISO timestamp, persist `scheduled_at`, return it for display and use timing filters when matching. Scheduling does not introduce an automatic-start background worker. |
| Campus Pickup Hotspots | `GET /api/rides/hotspots` → `get_hotspots` | Return `HOTSPOTS`; React renders selectors and [`TrackingMap.tsx`](frontend/components/TrackingMap.tsx) markers. |

To edit hotspot names or coordinates, now edit `HOTSPOTS` in
`backend/app/models/rides.py`. Also check the explicit `ZONES` aliases below it:
some override coordinates derived from `HOTSPOTS`. Your existing locations and
map configuration were retained during the move.

## FastAPI pieces, briefly

- `APIRouter()`: groups one controller's endpoints; `include_router` mounts them
  under prefixes such as `/api/rides` without changing their public URLs.
- `Depends(...)`: runs an authentication/authorization dependency before the
  handler. [`controllers/dependencies.py`](backend/app/controllers/dependencies.py)
  reads HTTP credentials; [`models/identity.py`](backend/app/models/identity.py)
  verifies tokens and checks active/admin accounts.
- Pydantic schema annotation: parses and validates the request body. Invalid
  fields still produce HTTP 422. `Query(...)` constrains query parameters.
- `Form`, `File`, `UploadFile`: parse multipart form submissions. The driver
  controller converts uploads into framework-neutral `UploadedDocument` objects;
  the driver model validates and stores their contents.
- `DomainError`: a model failure without a FastAPI dependency.
  [`controllers/errors.py`](backend/app/controllers/errors.py) translates its
  status/detail into the existing `{"detail": "..."}` error response.
- Returning a dictionary: FastAPI serializes it as JSON. `Response`,
  `HTMLResponse`, and `RedirectResponse` handle PDFs, HTML and checkout redirects.
- WebSocket controller: owns live connections and sends/receives messages.
  [`models/chat.py`](backend/app/models/chat.py) owns participant lookup, rate
  limits, message length limits and persistence.

For money, [`models/ledger.py`](backend/app/models/ledger.py) centralizes splitting
and all-or-nothing transactions. The receipt model loads/calculates data; the
PDF view only formats it. This is a second concrete example of MVC separation.

## Compatibility and verification

`backend/app/routes/*.py`, `app/database.py`, `app/auth.py` and
`app/wallet_service.py` remain as compatibility imports, so existing router,
seed-script and helper imports can still resolve. They are not a second set of
implementations. Make future logic changes in `models/` and endpoint changes in
`controllers/`.

Verification after the refactor:

- **52 backend tests passed**, including the original five-feature tests, API
  read endpoints, auth/OTP, uploads, moderation, tracking, chat, booking,
  cancellation, mock payments, settlement, reviews and PDF downloads.
- The complete generated OpenAPI document is identical to the pre-refactor
  snapshot: **67 paths**, including parameter schemas and operation IDs.
- Architecture tests reject HTTP/controller imports inside models, SQL execution
  inside controllers, and database/model imports inside PDF/HTML views.
- `npm run build` passed, including TypeScript checking.

Run backend tests from the repository root:

```bash
backend/.venv/bin/python -m pytest backend/tests -q
```

Development test dependencies are listed in `backend/requirements-dev.txt`.
Tests create a unique temporary database and use the mock payment gateway;
they do not book rides or settle payments in your demonstration database.

Restart the backend once after this reorganization (the launch target is still
`app.main:app`). Future Python edits reload automatically only if Uvicorn runs
with `--reload`; otherwise restart it. Refresh/re-fetch the page to load updated
hotspot data. No frontend rebuild is required merely because an API's returned
data changed.

These checks cover the refactor; they are not a claim that every pre-existing
behavior or production integration is complete. Payments and notification
delivery retain their existing demo limitations.
