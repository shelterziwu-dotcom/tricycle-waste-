from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, SessionLocal, engine, ensure_database
from app.realtime import manager
from app.routers import admin, auth, collector, pickups, reports
from app.security import user_from_token
from app.seed import seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_database(get_settings().database_url)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="TriCycle Waste API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, pickups.router, collector.router, collector.sites_router, admin.router, reports.router):
    app.include_router(r)


@app.get("/")
def health():
    return {"name": "TriCycle Waste API", "status": "ok", "docs": "/docs"}


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
