import socket
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import Base, SessionLocal, engine, ensure_database
from app.realtime import manager
from app.routers import admin, auth, collector, pickups, reports, uploads
from app.security import user_from_token
from app.seed import seed


def lan_address() -> str | None:
    """This computer's Wi-Fi address, for phones on the same network."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # no data is sent; this just picks the network interface
            return s.getsockname()[0]
    except OSError:
        return None


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_database(get_settings().database_url)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    ip = lan_address()
    print("\n  Admin dashboard:      http://localhost:8000/dashboard")
    print("  App in the browser:   http://localhost:8000/app")
    if ip:
        print(f"  Server address for the phone app (same Wi-Fi): http://{ip}:8000\n")
    yield


app = FastAPI(title="TriCycle Waste API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, pickups.router, collector.router, collector.sites_router, admin.router, reports.router,
          uploads.router):
    app.include_router(r)


@app.exception_handler(RequestValidationError)
async def friendly_validation_error(_: Request, exc: RequestValidationError):
    """Turn form errors into one plain sentence, e.g. 'Password must have at least 6 characters'."""
    messages = []
    for err in exc.errors():
        field = next((str(p) for p in reversed(err.get("loc", ())) if isinstance(p, str) and p != "body"), "")
        label = field.replace("_", " ").capitalize() or "Value"
        msg = err.get("msg", "is not valid")
        msg = (msg.replace("String should have", "must have").replace("Value should", "must")
               .replace("Input should be", "must be").replace("Field required", "is required"))
        messages.append(f"{label} {msg[0].lower()}{msg[1:]}" if msg else label)
    return JSONResponse(status_code=422, content={"detail": ". ".join(dict.fromkeys(messages))})


DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"
app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")
# Browser version of the mobile app (built with: flutter build web --base-href /app/), for demos
# on a laptop without Flutter or a phone. Rebuild and copy with mobile/build_web.bat after app changes.
WEBAPP_DIR = Path(__file__).resolve().parent.parent / "webapp"
if WEBAPP_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=WEBAPP_DIR, html=True), name="webapp")
uploads.UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads.UPLOAD_DIR), name="uploads")


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/dashboard/")


@app.get("/health")
def health():
    return {"name": "TriCycle Waste API", "status": "ok", "dashboard": "/dashboard/", "docs": "/docs"}


@app.websocket("/ws")
async def websocket(ws: WebSocket, token: str):
    with SessionLocal() as db:
        user = user_from_token(token, db)
    if not user:
        await ws.close(code=4401)
        return
    await manager.connect(user.id, ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive pings from the app
    except WebSocketDisconnect:
        manager.disconnect(user.id, ws)
