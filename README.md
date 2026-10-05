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

### Windows with WAMP (easiest)

WAMP's Apache **cannot** run this project (it only runs PHP). WAMP is used only for its MySQL database;
the Python API runs in its own window.

1. Install **Python 3.11+** from https://www.python.org/downloads/ and tick **"Add python.exe to PATH"**.
2. Start **WAMP** and wait until its tray icon is **green** (MySQL running).
3. Open the `backend` folder and double-click **`start.bat`**.
   The first run creates a Python environment and installs packages (needs internet, takes a few minutes).
4. Open **http://localhost:8000** in your browser for the **admin dashboard** (note the `:8000`;
   plain `http://localhost` is WAMP's page). Sign in with phone `0000000000` and the `ADMIN_PASSWORD` from `.env`
   (default `change-me-admin`). The API documentation is at http://localhost:8000/docs.
5. To see the system in action, keep `start.bat` running and double-click **`simulate.bat`**: sample collectors
   drive around Accra, take jobs, fill up and go to disposal sites while the dashboard map updates.

The `tricycle_waste` database and its tables are created automatically, so you will see them in phpMyAdmin.
If your MySQL `root` user has a password, or you use WAMP's MariaDB (port 3307), edit `backend/.env`.

### Any system (manual)

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # set DATABASE_URL (MySQL or SQLite) and SECRET_KEY
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000/docs to see and try every endpoint.
Default data (rubber sizes, prices, an example disposal site, an admin account) is created on first start.
`--host 0.0.0.0` lets a phone on the same Wi-Fi reach the API at `http://<your-PC-IP>:8000`.

### Admin dashboard

http://localhost:8000/dashboard (served by the API, no extra installation):

- **Overview**: key figures (including disposal compliance) and a live map of tricycles coloured by load
  (empty / partly loaded / nearly full / full), waiting pickups, dumping reports and disposal-site geofences
- **Collectors**: verify new collectors and set each tricycle's capacity in load units
- **Pickups**: latest requests with rubbers, units and prices
- **Pricing**: edit rates and waste-type factors, with a price checker
- **Disposal sites**: add sites by clicking the map, activate or deactivate them
- **Dumping reports**: review and update reports from residents

### Live simulation

`python simulate.py` (or `simulate.bat`) drives sample users and collectors through the real API.
It adds sample accounts (phones starting 0209 / 0509) and two sample disposal sites to the database in use.
Options: `--collectors 8 --users 20 --minutes 10 --tick 1`. Useful for demos and for the evaluation chapter
(e.g. compliance and waiting figures over a simulated period).

### See a complete pickup in one go

Double-click **`backend/demo.bat`** (or run `python demo.py`). It plays a whole story using a temporary
database: rubber-based quote, matching, collection, a full tricycle being skipped, a refused and a verified
disposal check-in, and the admin figures.

### Trying it in the browser

On the `/docs` page, use **POST /auth/login** with phone `0000000000` and the admin password from `.env`,
copy the `token`, click **Authorize** (top right) and paste it. Then try any endpoint with **Try it out**.

### Tests

```bash
cd backend
pytest                                                          # SQLite
TEST_DATABASE_URL=mysql+pymysql://root:@localhost/tricycle_test pytest   # MySQL
```

## Using the app without installing Flutter

The backend also serves a browser version of the app at **http://localhost:8000/app** (open it while
`start.bat` is running). It is the same Flutter app, compiled for the web. Use two browser windows (or a normal
and a private window) to be a household and a collector at the same time. Allow location when asked; for
photos use the **Gallery** button. After changing the app's code, rebuild it with `mobile\build_web.bat`.

## Running the mobile app (Flutter)

The app in `mobile/` has two modes, chosen by the account type:

- **Household / shop:** book a pickup by tapping rubbers (price shown upfront), track the collector on a map,
  approve a changed count, pay (test mode), rate, report illegal dumping.
- **Tricycle collector:** go online, see the load meter (Empty → Full), accept or decline job offers with a
  30-second countdown, count rubbers and take a photo, and check in at a disposal site to empty the tricycle.

### One-time setup (Windows)

1. Install **Flutter**: https://docs.flutter.dev/get-started/install/windows/mobile (follow "Android" setup).
2. Install **Android Studio** (the Flutter guide links it), then in Android Studio open
   **More Actions → Virtual Device Manager → Create device** (e.g. Pixel 7) to get an emulator.
3. In a terminal: `flutter doctor` until Android shows a green tick.

### Run it

1. Start the backend (`backend\start.bat`) and keep it running.
2. In a terminal:
   ```
   cd mobile
   flutter pub get
   flutter run
   ```
   Pick the emulator (or a phone connected by USB with developer mode on).
3. On the first screen, enter the **server address**:
   - Android emulator on the same laptop: `http://10.0.2.2:8000`
   - Real phone: same Wi-Fi as the laptop, and the address printed by `start.bat`
     (e.g. `http://192.168.1.20:8000`). If it can't connect, allow Python through Windows Firewall
     for private networks.
4. Create a household account, and a collector account. Verify the collector and set its capacity on the
   dashboard (Collectors page) before it can go online.

### Demo tips

- To show a disposal check-in on the emulator, move the emulator's location to the site:
  emulator **⋮ (Extended controls) → Location**, search or enter the site's coordinates, **Set location**.
  Checking in from anywhere else is refused, which is the point.
- Run the household and collector on two devices (emulator + phone), or log out and in to switch.
- `flutter build apk --release` creates an installable APK in `mobile/build/app/outputs/flutter-apk/`.

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
- [x] Flutter mobile app (users and collectors)
- [x] Admin web dashboard with live map
- [x] Live simulation for demos
- [x] Photo uploads
- [ ] Real mobile money gateway, USSD, rubber-detection model
