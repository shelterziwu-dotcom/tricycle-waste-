"""End-to-end API tests of a pickup, from request to verified disposal."""
from app.config import get_settings
from tests.conftest import FAR, HOME, SITE, pickup_body


def first_offer(client, collector):
    offers = client.get("/collector/offers", headers=collector).json()
    assert len(offers) == 1
    return offers[0]


def test_quote_uses_rubber_units(client, make_user, make_collector):
    user = make_user()
    make_collector()
    r = client.post("/quote", headers=user, json=pickup_body())
    assert r.status_code == 200
    body = r.json()
    assert body["total_units"] == 6
    assert body["total"] == "23.00"  # within the free radius
    assert body["collectors_available"] == 1


def test_full_pickup_lifecycle(client, make_user, make_collector, admin):
    user, collector = make_user(), make_collector()

    pickup = client.post("/pickups", headers=user, json=pickup_body()).json()
    assert pickup["status"] == "offered"

    offer = first_offer(client, collector)
    r = client.post(f"/collector/jobs/{offer['id']}/accept", headers=collector)
    assert r.json()["status"] == "accepted"
    assert client.get("/collector/load", headers=collector).json()["reserved_units"] == 6
    assert client.get(f"/pickups/{pickup['id']}/track", headers=user).json()["distance_km"] < 1

    r = client.post(f"/collector/jobs/{pickup['id']}/collect", headers=collector, json={
        "items": [{"size_code": "small", "quantity": 2}, {"size_code": "large", "quantity": 1}],
        "photo_url": "photos/pickup-1.jpg"})
    assert r.json()["status"] == "collected"
    assert r.json()["final_price"] == "23.00"
    loaded = client.get("/collector/load", headers=collector).json()
    assert (loaded["load_units"], loaded["reserved_units"], loaded["status"]) == (6, 0, "partly_loaded")

    r = client.post(f"/pickups/{pickup['id']}/pay", headers=user, json={"method": "momo", "phone": "0241111111"})
    assert r.json()["status"] == "paid"
    assert client.post(f"/pickups/{pickup['id']}/rate", headers=user, json={"stars": 5}).status_code == 201

    # Checking in away from the site is refused and the load stays.
    r = client.post("/collector/disposal-checkin", headers=collector,
                    json={"site_id": 1, "lat": HOME[0], "lng": HOME[1], "photo_url": "x.jpg"}).json()
    assert r["verified"] is False
    assert client.get("/collector/load", headers=collector).json()["load_units"] == 6

    r = client.post("/collector/disposal-checkin", headers=collector,
                    json={"site_id": 1, "lat": SITE[0], "lng": SITE[1], "photo_url": "dump.jpg"}).json()
    assert r == {"verified": True, "distance_m": 0, "units_disposed": 6, "jobs_released": 1,
                 "message": "Disposal verified at Example transfer station. Load reset."}
    assert client.get("/collector/load", headers=collector).json()["status"] == "empty"

    stats = client.get("/admin/stats", headers=admin).json()
    assert stats["disposal_compliance_percent"] == 100.0
    assert stats["revenue"] == "23.00"


def test_changed_count_needs_user_approval(client, make_user, make_collector):
    user, collector = make_user(), make_collector()
    pickup = client.post("/pickups", headers=user, json=pickup_body()).json()
    client.post(f"/collector/jobs/{pickup['id']}/accept", headers=collector)

    # Collector finds 2 large rubbers instead of 1: 10 units instead of 6.
    r = client.post(f"/collector/jobs/{pickup['id']}/collect", headers=collector, json={
        "items": [{"size_code": "small", "quantity": 2}, {"size_code": "large", "quantity": 2}],
        "photo_url": "p.jpg"}).json()
    assert r["status"] == "awaiting_approval"
    assert r["proposed_price"] == "35.00"
    assert client.get("/collector/load", headers=collector).json()["load_units"] == 0

    r = client.post(f"/pickups/{pickup['id']}/approve", headers=user).json()
    assert (r["status"], r["final_price"], r["confirmed_units"]) == ("collected", "35.00", 10)
    assert client.get("/collector/load", headers=collector).json()["load_units"] == 10


def test_full_tricycle_is_not_matched(client, make_user, make_collector):
    user = make_user()
    small = make_collector(capacity=8)
    big = make_collector(phone="0553333333", plate="GR 5519-23", location=(5.6200, -0.2000))

    # First job (6 units) goes to the nearer, smaller tricycle.
    first = client.post("/pickups", headers=user, json=pickup_body()).json()
    assert client.get("/collector/offers", headers=small).json()[0]["id"] == first["id"]
    client.post(f"/collector/jobs/{first['id']}/accept", headers=small)
    client.post(f"/collector/jobs/{first['id']}/collect", headers=small, json={
        "items": [{"size_code": "small", "quantity": 2}, {"size_code": "large", "quantity": 1}],
        "photo_url": "p.jpg"})
    assert client.get("/collector/load", headers=small).json()["status"] == "nearly_full"

    # Second job (4 units) does not fit in the 2 units left, so it skips to the bigger tricycle.
    other = make_user(phone="0244444444")
    second = client.post("/pickups", headers=other, json=pickup_body(items=(("large", 1),))).json()
    assert client.get("/collector/offers", headers=small).json() == []
    assert client.get("/collector/offers", headers=big).json()[0]["id"] == second["id"]


def test_declined_offer_moves_to_next_collector(client, make_user, make_collector):
    user = make_user()
    a = make_collector()
    b = make_collector(phone="0553333333", plate="GR 5519-23", location=(5.6200, -0.2000))
    pickup = client.post("/pickups", headers=user, json=pickup_body()).json()
    first = client.get("/collector/offers", headers=a).json()
    second_holder = b if first else a
    holder = a if first else b
    client.post(f"/collector/jobs/{pickup['id']}/decline", headers=holder)
    assert client.get("/collector/offers", headers=holder).json() == []
    assert client.get("/collector/offers", headers=second_holder).json()[0]["id"] == pickup["id"]


def test_expired_offer_is_reassigned(client, make_user, make_collector, monkeypatch):
    monkeypatch.setattr(get_settings(), "offer_timeout_seconds", -1)
    user = make_user()
    a = make_collector()
    b = make_collector(phone="0553333333", plate="GR 5519-23", location=(5.6200, -0.2000))
    pickup = client.post("/pickups", headers=user, json=pickup_body()).json()
    # Both offers expire immediately; after each expiry the job moves on, then waits.
    client.get("/collector/offers", headers=a)
    client.get("/collector/offers", headers=b)
    assert client.get(f"/pickups/{pickup['id']}", headers=user).json()["status"] == "searching"


def test_no_collector_in_range_keeps_request_searching(client, make_user, make_collector):
    user = make_user()
    late = make_collector(location=FAR)
    pickup = client.post("/pickups", headers=user, json=pickup_body()).json()
    assert pickup["status"] == "searching"
    # When a collector comes online nearby, the waiting request is offered to them.
    client.post("/collector/online", headers=late, json={"lat": HOME[0], "lng": HOME[1]})
    assert client.get("/collector/offers", headers=late).json()[0]["id"] == pickup["id"]


def test_unverified_collector_cannot_go_online(client):
    r = client.post("/auth/register-collector", json={
        "name": "New Rider", "phone": "0559999999", "password": "secret1",
        "id_number": "GHA-1", "plate_number": "GN 1-26"})
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    r = client.post("/collector/online", headers=headers, json={"lat": HOME[0], "lng": HOME[1]})
    assert r.status_code == 403


def test_roles_are_enforced(client, make_user):
    user = make_user()
    assert client.get("/admin/stats", headers=user).status_code == 403
    assert client.get("/collector/load", headers=user).status_code == 403
    assert client.get("/pickups").status_code == 401


def test_recyclables_earn_reward_points(client, make_user, make_collector):
    user, collector = make_user(), make_collector()
    pickup = client.post("/pickups", headers=user, json=pickup_body(waste_type="recyclable")).json()
    assert pickup["quoted_price"] == "17.60"  # 5 + 6 x 3 x 0.7
    client.post(f"/collector/jobs/{pickup['id']}/accept", headers=collector)
    client.post(f"/collector/jobs/{pickup['id']}/collect", headers=collector, json={
        "items": [{"size_code": "small", "quantity": 2}, {"size_code": "large", "quantity": 1}],
        "photo_url": "p.jpg"})
    client.post(f"/pickups/{pickup['id']}/pay", headers=user, json={"method": "cash"})
    assert client.get("/auth/me", headers=user).json()["reward_points"] == 60


def test_dumping_report(client, make_user, admin):
    user = make_user()
    r = client.post("/dumping-reports", headers=user,
                    json={"lat": HOME[0], "lng": HOME[1], "photo_url": "dump.jpg", "description": "Drain blocked"})
    assert r.status_code == 201
    reports = client.get("/admin/dumping-reports?status=open", headers=admin).json()
    assert len(reports) == 1
    r = client.patch(f"/admin/dumping-reports/{reports[0]['id']}", headers=admin, json={"status": "cleared"})
    assert r.json()["status"] == "cleared"


def test_collector_receives_live_job_offer(client, make_user, make_collector):
    user, collector = make_user(), make_collector()
    token = collector["Authorization"].split()[1]
    with client.websocket_connect(f"/ws?token={token}") as ws:
        pickup = client.post("/pickups", headers=user, json=pickup_body()).json()
        event = ws.receive_json()
    assert event["type"] == "job_offer"
    assert event["request_id"] == pickup["id"]
    assert event["units"] == 6


def test_dashboard_is_served(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/dashboard/"
    page = client.get("/dashboard/")
    assert page.status_code == 200 and "TriCycle Waste Admin" in page.text
    assert client.get("/dashboard/vendor/leaflet/leaflet.js").status_code == 200


def test_photo_upload(client, make_user):
    user = make_user()
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100
    r = client.post("/uploads", headers=user, files={"file": ("rubbers.jpg", jpeg, "image/jpeg")})
    assert r.status_code == 201
    url = r.json()["url"]
    assert client.get(url).content == jpeg
    bad = client.post("/uploads", headers=user, files={"file": ("x.txt", b"hello", "text/plain")})
    assert bad.status_code == 415
