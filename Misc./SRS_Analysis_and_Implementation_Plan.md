# Arooohi SRS Analysis and Implementation Plan

Date: 2026-07-31

## 1. SRS-to-Code Assessment Summary

The SRS defines a student-only ride-sharing platform with safety-first features such as:
- BRACU email verification
- live GPS ride tracking
- female-only matching mode
- in-app SOS
- ride cost splitter
- campus hotspot matching
- driver rating/review system
- scheduled booking and multi-stop rides
- wallet and bKash integration
- ride history/receipt logs
- driver vehicle verification
- trusted contact sharing
- peak-hour surge indicator
- ride chat
- driver earnings dashboard
- admin complaint panel
- eco/footprint tracking

The current codebase only demonstrates a significant subset of the requested functionality, but the implementation is mostly a demo MVP and not yet production-ready for all listed SRS features.

## 2. Feature-by-Feature Status

### 2.1 Strongly Implemented / Demo-Ready

#### Trusted Contact Sharing
- Backend:
  - [backend/app/routes/contacts.py](backend/app/routes/contacts.py)
  - CRUD endpoints for saving and removing contacts.
  - `POST /api/contacts/auto-share` returns a mock notification payload and prints the contacts to the console.
- Frontend:
  - [frontend/app/dashboard/contacts/page.tsx](frontend/app/dashboard/contacts/page.tsx)
- Status:
  - Good for a demo UI and backend persistence.
  - Not production-grade because no real SMS/email/push notification layer exists.

#### Peak Hour Surge Indicator
- Backend:
  - [backend/app/routes/surge.py](backend/app/routes/surge.py)
  - Uses a seeded 24-hour demand table plus live active-ride volume bump.
- Frontend:
  - [frontend/app/dashboard/rides/page.tsx](frontend/app/dashboard/rides/page.tsx)
- Status:
  - Good concept demonstration.
  - Needs stronger business rule validation, clearer schedule methodology, and better display of hourly insights.

#### Ride Cost Splitter
- Backend:
  - [backend/app/routes/rides.py](backend/app/routes/rides.py)
  - `GET /api/rides/{ride_id}/split` computes total fare from `base_fare * surge_multiplier` and evenly distributes it.
- Frontend:
  - [frontend/app/dashboard/rides/page.tsx](frontend/app/dashboard/rides/page.tsx)
- Status:
  - Demo-aligned and usable.
  - Missing important business logic such as per-seat pricing, seat occupancy validation, cancellation and refund rules, and driver payout split logic.

#### Ride Chat
- Backend:
  - [backend/app/routes/chat.py](backend/app/routes/chat.py)
  - WebSocket-based real-time ride chat with message persistence into `chat_messages`.
- Frontend:
  - [frontend/app/dashboard/chat/[rideId]/page.tsx](frontend/app/dashboard/chat/[rideId]/page.tsx)
- Status:
  - Good functional MVP.
  - Missing typing indicators, read receipts, message deletion/edited state, message size validation, moderation, and proper reconnect UX.

#### Eco/Footprint Tracker
- Backend:
  - [backend/app/routes/eco.py](backend/app/routes/eco.py)
  - Computes per-ride savings from distance and occupancy.
- Frontend:
  - [frontend/app/dashboard/eco/page.tsx](frontend/app/dashboard/eco/page.tsx)
- Status:
  - Valid demo metric.
  - Needs more credible model calibration and better accuracy for occupancy, fuel, and tree-equivalent reporting.

### 2.2 Partially Implemented or Mapped to a Placeholder

#### Live GPS Tracking & Share Link
- Backend:
  - [backend/app/routes/tracking.py](backend/app/routes/tracking.py)
  - Basic tracking session start/stop, point ingestion, public share token endpoint.
- Frontend:
  - [frontend/app/dashboard/page.tsx](frontend/app/dashboard/page.tsx)
- Status:
  - A strong demo foundation exists.
  - Missing geofencing, route privacy rules, better session lifecycle, and reliable push-to-trusted-contact notification integration.

#### SOS Flow
- Backend:
  - [backend/app/routes/sos.py](backend/app/routes/sos.py)
- Status:
  - Alerts and admin review exist.
  - The notification path is still a console/print mock; production delivery must be connected to SMS/push providers.

### 2.3 Not Properly Implemented in the Current Codebase

These SRS areas are either absent or too thin to be trusted for real production:
- Female-only ride mode
- Campus zone smart matching
- Scheduled ride booking and multi-stop support
- Driver verification with true document review workflow
- Wallet/bKash payment integration
- Driver rating & review system
- Ride cancellation policy and penalties
- Downloadable receipt log / earnings dashboard rich reporting
- Complaint moderation pipeline beyond a basic admin table UI
- Real database/provider alignment with the SRS target stack (PostgreSQL + PostGIS, cloud storage, push/SMS providers)

## 3. Code-Level Gaps and Improvements

### 3.1 Backend

#### Reliability / Correctness
- The ride splitter endpoint does not enforce participant-only access. Any authenticated user can request a split for any ride.
- The ride history and chat endpoints rely heavily on raw DB queries and status strings; they are missing rule guards such as seat capacity, driver-owned ride acceptance validation, and cancellation semantics.
- The eco endpoint currently uses a simplified occupancy calculation but does not strictly validate whether the ride is truly shared by the current user in a safe, auditable way.
- The chat WebSocket only checks whether the user is a ride driver or an accepted/completed passenger, but it does not protect against concurrent abuse, oversized payloads, or spam moderation.

#### Security
- The application is still demo-oriented and uses SQLite in [backend/app/database.py](backend/app/database.py); this deviates from the SRS target architecture.
- Real identity verification, trust lists, and sensitive data handling are not yet hardened for production.
- `auto-share` and SOS notification are still console-driven mocks, not external service integrations.

#### Structure / Maintainability
- The ride module mixes ride creation, acceptance, chat access, end-of-ride logic, and split break-down in one file. It should be separated into dedicated service/domain functions.
- The database schema is good for demo, but it lacks stronger constraints and migrations.
- The route layer is doing too much business logic directly; service/repository boundaries should be added.

### 3.2 Frontend

#### UX / Flow Quality
- The rides page is functional, but it does not tell the user when a ride is waiting for driver acceptance or when the cost-split data is unavailable.
- The chat page has no message typing feedback, optimistic UX, or typing/online indicators.
- The eco page is visually polished but should offer period filtering, comparative metrics, and a clearer explanation of what a “saved kg” value means scientifically.
- The trusted contacts page is strong, but the contact share action should be tied to a visible and tracked ride-sharing action rather than only happening during tracking start.

#### Data Consistency
- The rides UI relies on `localStorage` for token and user state and does not yet implement a central auth layer or proper redirect on expired session.
- The frontend currently lacks robust state synchronization across multi-tab or multi-device flows.

## 4. Recommended Implementation Order

### Phase 1 — Hardening the Current Demo
1. Lock down access to ride split and chat history routes.
2. Add proper validation and seat-capacity logic for ride join/accept.
3. Replace mock contact-share notifications with a proper provider interface.
4. Enforce safer and more descriptive ride lifecycle states.

### Phase 2 — Bring the Code Closer to the SRS
1. Add a proper female-only ride mode in ride listing and ride creation.
2. Add scheduled ride support and multi-stop discussion points in the data model.
3. Upgrade ride matching to include campus hotspot logic.
4. Connect eco and route data to a more trustworthy real-distance measurement system.

### Phase 3 — Productionization
1. Move from SQLite to PostgreSQL with PostGIS.
2. Add file storage for docs and profile verification.
3. Add a real notification provider for SMS/email/push.
4. Add audit logging, admin review workflows, and security controls.

## 5. Planned Delivery Milestones

### Milestone A — Backend Safety and Rule Integrity
- Participant-only split access
- Join/accept state validation
- Ride status progression guardrails
- Proper chat access and message sanitization

### Milestone B — UX/Feature Completeness
- Better ride detail card actions
- Better ride chat UI and reconnect handling
- Better eco metric interpretation
- Safe, visible trusted-contact sharing from ride and tracking flows

### Milestone C — SRS Alignment
- Matching and filtering rules
- Payment and wallet integration skeleton
- review/rating pipeline
- scheduled ride and multi-stop support

## 6. Progress Assessment

### Completed / Demonstrated
- ride creation
- ride join / accept flow
- cost-split calculation
- surge multiplier calculation
- basic real-time chat persistence
- eco summary calculation
- trusted contact persistence
- SOS trigger workflow
- tracking session and share token creation

### Needs Immediate Repair / Cleanup
- unauthorized access to split and ride details
- mock-only notification delivery
- insufficient participant/seat validation
- limited multi-step/proper ride lifecycle rules

### Needs Future Architectural Work
- real DB migration
- provider integrations
- advanced matching
- proper payment flow
- admin moderation and review
- strong reporting and analytics

## 7. Final Conclusion

The current repo already demonstrates a credible MVP for the SRS-driven feature set around ride sharing, trusted contact safety, surge, chat, and eco metrics. However, the code is still more of a functional prototype than a production-ready full SRS implementation.

The most valuable next move is not to add more UI only. The more impactful work is to harden the backend rules, enforce authorization and ride lifecycle consistency, and replace the mock notification layer with real integration points.
