# TriCycle Waste

On-demand tricycle (aboboyaa) waste collection with **rubber-based pricing**,
**real-time tricycle load tracking** and **verified disposal**.

Final-year project by Isaac Akwantey and Shelter Deladem Ziwu, Regional Maritime University.

## How the system works

1. **Request:** the user enters their location, waste type and the number and size of their rubbers.
2. **Price:** each rubber size is worth a set number of load units
   (small = 1, medium = 2, large = 4, bulky = 6). The price is calculated upfront as
   `base fee + units × rate per unit × waste-type factor + distance charge`.
3. **Match:** the job is offered to the best nearby collector **whose tricycle has space for it**.
   If they don't accept within 30 seconds, it moves to the next collector.
4. **Collect:** the collector confirms the rubbers actually handed over, with a photo.
   If the count differs, the user must approve the new price. The units are added to the tricycle's load.
5. **Load status:** Empty → Partly loaded (1–59%) → Nearly full (60–89%) → Full (90%+).
   A full tricycle gets no new jobs and is directed to the nearest approved disposal site.
6. **Dispose:** the load only resets, and the collector's earnings are only released, after a
   GPS check-in inside an approved disposal site's geofence, with a photo.

## Project structure

```
backend/                 Python API (FastAPI + SQLAlchemy)
  app/services/          Business rules, no database code, fully unit-tested
    pricing.py           Rubber-based pricing
    load.py              Tricycle fill level and status
    matching.py          Capacity-aware matching (+ nearest-only baseline for evaluation)
    geo.py               Distance and geofence check
    dispatch.py          Applies the rules to the database (offers, expiry, reservations)
  app/routers/           API endpoints: auth, pickups, collector, admin, dumping reports
  app/models.py          Database tables
  app/realtime.py        WebSocket live updates
  tests/                 Unit and end-to-end tests
```

## Running the backend

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then edit SECRET_KEY etc.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/docs to see and try every endpoint.
Tables and default data (rubber sizes, prices, an example disposal site, an admin account)
are created automatically on first start. Use `--host 0.0.0.0` so a phone on the same Wi-Fi can reach it.

Run the tests:

```bash
cd backend
pytest
```

## Main API endpoints

| Who | Endpoint | Purpose |
|---|---|---|
| Anyone | `POST /auth/register`, `POST /auth/register-collector`, `POST /auth/login` | Accounts (log in with phone number) |
| User | `GET /rubber-sizes`, `POST /quote` | Rubber sizes and upfront price |
| User | `POST /pickups`, `GET /pickups/{id}`, `GET /pickups/{id}/track` | Request and track a pickup |
| User | `POST /pickups/{id}/approve` / `reject` | Respond to a changed rubber count |
| User | `POST /pickups/{id}/pay`, `POST /pickups/{id}/rate` | Pay (sandbox) and rate |
| Collector | `POST /collector/online`, `/offline`, `/location` | Availability and live location |
| Collector | `GET /collector/offers`, `POST /collector/jobs/{id}/accept` / `decline` / `collect` | Jobs |
| Collector | `GET /collector/load`, `POST /collector/disposal-checkin` | Load meter and verified disposal |
| Anyone | `POST /dumping-reports` | Report illegal dumping |
| Admin | `/admin/collectors`, `/admin/live`, `/admin/pricing`, `/admin/disposal-sites`, `/admin/dumping-reports`, `/admin/stats` | Verification, capacity, prices, map, reports |
| App | `WS /ws?token=...` | Live events: `job_offer`, `collector_assigned`, `collector_location`, `count_changed`, `tricycle_full`, ... |

## Before field testing

- Replace the placeholder prices (`/admin/pricing`) with rates based on a survey of current aboboyaa fees.
- Add the real approved disposal sites (`/admin/disposal-sites`) and remove the example site.
- Measure each tricycle's capacity in load units at onboarding and set it in `/admin/collectors/{id}`.
- Payments are in sandbox mode: no real money moves.

## Status

- [x] Backend API with pricing, load tracking, matching, disposal verification, dumping reports, admin tools
- [x] Live updates over WebSocket
- [x] Automated tests
- [ ] Flutter mobile app (users and collectors)
- [ ] Admin web dashboard
- [ ] Photo upload storage, real mobile money gateway, USSD, rubber-detection model
