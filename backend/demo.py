"""Walk through a complete TriCycle Waste pickup and print each step.

Run from the backend folder:   python demo.py
Uses a temporary database, so your real MySQL data is not touched.
"""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'demo.db')}"
os.environ.setdefault("SECRET_KEY", "demo-secret-key-at-least-32-characters-long")
os.environ["ADMIN_PASSWORD"] = "demo-admin"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

HOME = (5.6145, -0.2057)      # user's house
RIDER_A = (5.6180, -0.2030)   # ~0.5 km away, small tricycle
RIDER_B = (5.6200, -0.2000)   # ~0.9 km away, big tricycle
SITE = (5.6037, -0.1870)      # approved disposal site


def step(title):
    print(f"\n=== {title} " + "=" * max(0, 66 - len(title)))


def bar(load):
    filled = round(load["fill_percent"] / 5)
    return f"[{'#' * filled}{'.' * (20 - filled)}] {load['load_units']}/{load['capacity_units']} units " \
           f"({load['fill_percent']}%) -> {load['status'].replace('_', ' ').upper()}"


def main():
    with TestClient(app) as api:
        def post(path, headers=None, **body):
            r = api.post(path, headers=headers, json=body or None)
            assert r.status_code < 400, f"{path}: {r.status_code} {r.text}"
            return r.json()

        def get(path, headers):
            return api.get(path, headers=headers).json()

        def h(token):
            return {"Authorization": f"Bearer {token}"}

        admin = h(post("/auth/login", phone="0000000000", password="demo-admin")["token"])

        step("1. Accounts")
        ama = h(post("/auth/register", name="Ama Mensah", phone="0241111111", password="secret1")["token"])
        print("User registered:      Ama Mensah")
        riders = {}
        for name, phone, plate, cap, spot in [("Kofi", "0552222222", "GR 2104-24", 8, RIDER_A),
                                              ("Yaw", "0553333333", "GR 5519-23", 40, RIDER_B)]:
            tok = h(post("/auth/register-collector", name=name, phone=phone, password="secret1",
                         id_number=f"GHA-{phone}", plate_number=plate)["token"])
            cid = get("/auth/me", tok)["collector"]["id"]
            api.patch(f"/admin/collectors/{cid}", headers=admin, json={"verified": True, "capacity_units": cap})
            post("/collector/online", tok, lat=spot[0], lng=spot[1])
            riders[name] = tok
            print(f"Collector {name:<5} verified by admin, tricycle {plate}, capacity {cap} units, online")

        step("2. Rubber-based price quote")
        sizes = {s["code"]: s["load_units"] for s in get("/rubber-sizes", ama)}
        print("Load units per rubber:", ", ".join(f"{k} = {v}" for k, v in sizes.items()))
        order = {"lat": HOME[0], "lng": HOME[1], "waste_type": "general",
                 "items": [{"size_code": "small", "quantity": 2}, {"size_code": "large", "quantity": 1}]}
        q = post("/quote", ama, **order)
        print(f"Ama has 2 small + 1 large rubber = {q['total_units']} units")
        print(f"Price = base {q['base_fee']} + units {q['units_charge']} + distance {q['distance_charge']}"
              f" = GHS {q['total']}   ({q['collectors_available']} collectors with space nearby)")

        step("3. Request and capacity-aware matching")
        pickup = post("/pickups", ama, **order)
        offered = [n for n, t in riders.items() if get("/collector/offers", t)]
        print(f"Pickup #{pickup['id']} created, status: {pickup['status']}, offered to: {offered[0]} (nearest with space)")
        kofi = riders["Kofi"]
        post(f"/collector/jobs/{pickup['id']}/accept", kofi)
        track = get(f"/pickups/{pickup['id']}/track", ama)
        print(f"Kofi accepted. Ama can track him: {track['distance_km']} km away, plate {track['plate_number']}")

        step("4. Collection: collector confirms rubbers with a photo")
        done = post(f"/collector/jobs/{pickup['id']}/collect", kofi, items=order["items"], photo_url="photo1.jpg")
        print(f"Status: {done['status']}, final price GHS {done['final_price']}")
        print("Kofi's tricycle:", bar(get("/collector/load", kofi)))
        post(f"/pickups/{pickup['id']}/pay", ama, method="momo", phone="0241111111")
        post(f"/pickups/{pickup['id']}/rate", ama, stars=5)
        print("Ama paid by mobile money (sandbox) and rated 5 stars")

        step("5. Next job does not fit Kofi's tricycle")
        kwesi = h(post("/auth/register", name="Kwesi", phone="0244444444", password="secret1")["token"])
        second = post("/pickups", kwesi, lat=HOME[0], lng=HOME[1], waste_type="general",
                      items=[{"size_code": "large", "quantity": 1}])
        print(f"Kwesi requests 1 large rubber (4 units). Kofi only has "
              f"{get('/collector/load', kofi)['available_units']} units free.")
        print(f"Offer goes to: {'Yaw' if get('/collector/offers', riders['Yaw']) else 'nobody'} "
              f"(Kofi gets {len(get('/collector/offers', kofi))} offers)")
        site = get('/collector/load', kofi)["nearest_disposal_site"]
        print(f"Kofi is directed to the nearest disposal site: {site['name']}")

        step("6. Verified disposal")
        r = post("/collector/disposal-checkin", kofi, site_id=site["id"], lat=HOME[0], lng=HOME[1], photo_url="d.jpg")
        print(f"Check-in from the neighbourhood: verified={r['verified']} - {r['message']}")
        r = post("/collector/disposal-checkin", kofi, site_id=site["id"], lat=SITE[0], lng=SITE[1], photo_url="d.jpg")
        print(f"Check-in at the site:            verified={r['verified']} - {r['message']}")
        print(f"Earnings released for {r['jobs_released']} job(s)")
        print("Kofi's tricycle:", bar(get("/collector/load", kofi)))

        step("7. Admin dashboard figures")
        stats = get("/admin/stats", admin)
        for key in ("pickups_completed", "pickups_waiting", "units_collected", "units_disposed_verified",
                    "disposal_compliance_percent", "revenue"):
            print(f"{key.replace('_', ' '):<28} {stats[key]}")
        print(f"\nDemo finished. Second pickup #{second['id']} is with Yaw.")


if __name__ == "__main__":
    main()
