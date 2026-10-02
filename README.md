# TriCycle Waste

On-demand tricycle (aboboyaa) waste collection with rubber-based pricing,
real-time tricycle load tracking and verified disposal.

Final-year project: Isaac Akwantey & Shelter Deladem Ziwu, Regional Maritime University.

## Status (work in progress)

Backend (Python / FastAPI / SQLAlchemy, MySQL in production, SQLite for development):

- [x] `app/services/pricing.py`: rubber-based pricing (load units, waste-type factor, distance)
- [x] `app/services/load.py`: tricycle fill level and Empty / Partly loaded / Nearly full / Full status
- [x] `app/services/geo.py`: haversine distance and geofence check
- [x] `app/services/matching.py`: capacity-aware matching and nearest-only baseline
- [x] `app/models.py`: database tables
- [x] `app/security.py`: password hashing, JWT, role checks
- [x] `app/seed.py`: default rubber sizes, prices, admin account
- [ ] API routers (auth, pickup requests, collector, disposal, admin, dumping reports)
- [ ] WebSocket live updates
- [ ] Tests
- [ ] Flutter app and admin dashboard
