import os
import tempfile

# Tests use a throwaway SQLite file. Set TEST_DATABASE_URL to run them against MySQL instead.
_db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_db_file}")
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-bytes"
os.environ["ADMIN_PASSWORD"] = "admin-pass"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine, ensure_database  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

# Pickup point and a nearby collector in Accra (about 0.5 km apart)
HOME = (5.6145, -0.2057)
NEAR = (5.6180, -0.2030)
FAR = (5.7000, -0.1000)  # well outside the matching radius
SITE = (5.6037, -0.1870)  # seeded example disposal site


@pytest.fixture(autouse=True)
def fresh_db():
    ensure_database(os.environ["DATABASE_URL"])
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client):
    r = client.post("/auth/login", json={"phone": "0000000000", "password": "admin-pass"})
    return auth(r.json()["token"])


@pytest.fixture
def make_user(client):
    def _make(phone="0241111111", name="Ama Mensah"):
        r = client.post("/auth/register", json={"name": name, "phone": phone, "password": "secret1"})
        assert r.status_code == 201, r.text
        return auth(r.json()["token"])
    return _make


@pytest.fixture
def make_collector(client, admin):
    def _make(phone="0552222222", plate="GR 2104-24", location=NEAR, capacity=40, online=True):
        r = client.post("/auth/register-collector", json={
            "name": f"Collector {phone[-3:]}", "phone": phone, "password": "secret1",
            "id_number": f"GHA-{phone}", "plate_number": plate})
        assert r.status_code == 201, r.text
        headers = auth(r.json()["token"])
        cid = client.get("/auth/me", headers=headers).json()["collector"]["id"]
        client.patch(f"/admin/collectors/{cid}", headers=admin,
                     json={"verified": True, "capacity_units": capacity})
        if online:
            r = client.post("/collector/online", headers=headers, json={"lat": location[0], "lng": location[1]})
            assert r.status_code == 200, r.text
        return headers
    return _make


def pickup_body(items=(("small", 2), ("large", 1)), waste_type="general", at=HOME):
    return {"lat": at[0], "lng": at[1], "waste_type": waste_type,
            "items": [{"size_code": s, "quantity": q} for s, q in items]}
