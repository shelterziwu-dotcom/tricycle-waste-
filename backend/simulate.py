"""Live simulation for demos and evaluation.

Pretend users request pickups and pretend collectors drive around Accra through the
real API: they accept jobs, collect rubbers, fill up and go to disposal sites. Watch it
on the dashboard (http://localhost:8000/dashboard). Start the API first, then run:

    python simulate.py                    # until Ctrl+C
    python simulate.py --minutes 5        # stop after 5 minutes

The sample accounts and sites are added to the database the API is using.
Sample phone numbers start with 0209 (users) and 0509 (collectors).
"""
import argparse
import math
import os
import random
import time

import httpx

CENTRE = (5.5800, -0.2050)   # around Kokomlemle / Nima
AREA_KM = 2.5                 # pickups appear within this distance of the centre
STEP_M = 180                  # how far a tricycle moves per tick
SAMPLE_SITES = [("Sample transfer station (Achimota)", 5.6125, -0.2270),
                ("Sample recycling point (Kaneshie)", 5.5650, -0.2330)]
SIZES = ["small", "medium", "large", "bulky"]
WASTE = ["general", "general", "general", "organic", "recyclable", "bulky"]
REPORTS = ["Rubbish dumped in the drain", "Pile of waste by the roadside", "Waste burning near houses",
           "Plastic bags blocking gutter"]


def random_point(centre=CENTRE, km=AREA_KM):
    r, a = km * math.sqrt(random.random()), random.uniform(0, 2 * math.pi)
    return centre[0] + r / 111 * math.cos(a), centre[1] + r / 111 * math.sin(a)


def move_towards(pos, target, step_m=STEP_M):
    dlat, dlng = target[0] - pos[0], target[1] - pos[1]
    dist_m = math.hypot(dlat, dlng) * 111_000
    if dist_m <= step_m:
        return target, True
    f = step_m / dist_m
    return (pos[0] + dlat * f, pos[1] + dlng * f), False


class Api:
    def __init__(self, base):
        self.http = httpx.Client(base_url=base, timeout=15)

    def call(self, verb, path, token=None, /, **body):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        r = self.http.request(verb, path, headers=headers, json=body or None)
        return r.status_code, (r.json() if r.content else None)

    def account(self, kind, name, phone, **extra):
        code, body = self.call("POST", "/auth/register" if kind == "user" else "/auth/register-collector",
                               name=name, phone=phone, password="sample123", **extra)
        if code == 409:
            code, body = self.call("POST", "/auth/login", phone=phone, password="sample123")
        if code >= 400:
            raise SystemExit(f"Could not create or log in sample account {phone}: {body}")
        return body["token"]


class Collector:
    def __init__(self, name, token, pos):
        self.name, self.token, self.pos = name, token, pos
        self.target, self.site = None, None


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def setup(api, admin, n_users, n_collectors):
    sites = {s["name"] for s in api.call("GET", "/admin/disposal-sites", admin)[1]}
    for name, lat, lng in SAMPLE_SITES:
        if name not in sites:
            api.call("POST", "/admin/disposal-sites", admin, name=name, lat=lat, lng=lng, radius_m=150)

    users = [api.account("user", f"Resident {i + 1}", f"02090000{i + 1:02d}") for i in range(n_users)]
    collectors = []
    names = ["Kofi", "Yaw", "Kwame", "Ama", "Esi", "Kojo", "Akosua", "Fiifi", "Abena", "Kwabena"]
    for i in range(n_collectors):
        name = names[i % len(names)]
        phone = f"05090000{i + 1:02d}"
        token = api.account("collector", f"{name} (sample)", phone, id_number=f"GHA-SAMPLE-{i + 1}",
                            plate_number=f"SAMPLE {i + 1:02d}")
        cid = api.call("GET", "/auth/me", token)[1]["collector"]["id"]
        api.call("PATCH", f"/admin/collectors/{cid}", admin, verified=True, capacity_units=random.choice([20, 24, 30, 40]))
        pos = random_point()
        api.call("POST", "/collector/online", token, lat=pos[0], lng=pos[1])
        collectors.append(Collector(name, token, pos))
    log(f"Ready: {len(users)} sample users, {len(collectors)} sample collectors online, "
        f"{len(SAMPLE_SITES)} sample disposal sites")
    return users, collectors


def tick_users(api, users, chance):
    for token in users:
        if random.random() > chance:
            continue
        lat, lng = random_point()
        items = [{"size_code": s, "quantity": random.randint(1, 3)}
                 for s in random.sample(SIZES[:3], random.randint(1, 2))]
        if random.random() < 0.1:
            items = [{"size_code": "bulky", "quantity": 1}]
        code, body = api.call("POST", "/pickups", token, lat=lat, lng=lng, waste_type=random.choice(WASTE), items=items)
        if code == 201:
            units = body["declared_units"]
            log(f"New pickup #{body['id']}: {units} units, GHS {body['quoted_price']} -> {body['status']}")

    # Users approve changed counts and pay for collected pickups.
    for token in users:
        _, mine = api.call("GET", "/pickups", token)
        for p in mine[:3]:
            if p["status"] == "awaiting_approval":
                api.call("POST", f"/pickups/{p['id']}/approve", token)
                log(f"Pickup #{p['id']}: user approved corrected count ({p['confirmed_units']} units)")
            elif p["status"] == "collected":
                api.call("POST", f"/pickups/{p['id']}/pay", token, method="momo", phone="0240000000")
                api.call("POST", f"/pickups/{p['id']}/rate", token, stars=random.choice([4, 5, 5]))


def tick_collector(api, c):
    _, load = api.call("GET", "/collector/load", c.token)
    _, jobs = api.call("GET", "/collector/jobs", c.token)
    pending = [j for j in jobs if j["status"] == "accepted"]

    # 1. Answer offers.
    _, offers = api.call("GET", "/collector/offers", c.token)
    for o in offers:
        if random.random() < 0.85:
            code, _ = api.call("POST", f"/collector/jobs/{o['id']}/accept", c.token)
            if code == 200:
                log(f"{c.name} accepted pickup #{o['id']} ({o['declared_units']} units)")
                pending.append(o)
        else:
            api.call("POST", f"/collector/jobs/{o['id']}/decline", c.token)
            log(f"{c.name} declined pickup #{o['id']} -> offered to next collector")

    # 2. Drive to the next pickup, or to a disposal site when full, or wander.
    if pending:
        job = pending[0]
        c.pos, arrived = move_towards(c.pos, (job["lat"], job["lng"]))
        if arrived:
            items = [{"size_code": i["size_code"], "quantity": i["quantity_declared"]} for i in job["items"]]
            if random.random() < 0.15:  # sometimes the user had an extra rubber
                items.append({"size_code": "small", "quantity": 1})
            code, body = api.call("POST", f"/collector/jobs/{job['id']}/collect", c.token, items=items,
                                  photo_url=f"sim/pickup-{job['id']}.jpg")
            if code == 200:
                log(f"{c.name} collected pickup #{job['id']} -> {body['status']}")
            else:
                log(f"{c.name} could not collect #{job['id']}: {body.get('detail')}")
    elif load["status"] in ("full", "nearly_full") and load["nearest_disposal_site"]:
        site = load["nearest_disposal_site"]
        if c.site != site["id"]:
            log(f"{c.name}'s tricycle is {load['status'].replace('_', ' ')} ({load['fill_percent']}%) "
                f"-> heading to {site['name']}")
            c.site = site["id"]
        c.pos, arrived = move_towards(c.pos, (site["lat"], site["lng"]))
        if arrived:
            _, r = api.call("POST", "/collector/disposal-checkin", c.token, site_id=site["id"],
                            lat=c.pos[0], lng=c.pos[1], photo_url="sim/disposal.jpg")
            log(f"{c.name} at {site['name']}: {r['message']}")
            c.site = None
    else:
        if not c.target or random.random() < 0.1:
            c.target = random_point()
        c.pos, arrived = move_towards(c.pos, c.target, STEP_M / 2)
        if arrived:
            c.target = None

    api.call("POST", "/collector/location", c.token, lat=c.pos[0], lng=c.pos[1])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--admin-password", default=os.environ.get("ADMIN_PASSWORD", "change-me-admin"))
    parser.add_argument("--users", type=int, default=12)
    parser.add_argument("--collectors", type=int, default=5)
    parser.add_argument("--tick", type=float, default=2.0, help="seconds between steps")
    parser.add_argument("--minutes", type=float, default=0, help="stop after this many minutes (0 = run until Ctrl+C)")
    args = parser.parse_args()

    api = Api(args.url)
    try:
        code, body = api.call("POST", "/auth/login", phone="0000000000", password=args.admin_password)
    except httpx.ConnectError:
        raise SystemExit(f"Cannot reach the API at {args.url}. Start it first (start.bat).")
    if code != 200:
        raise SystemExit("Admin login failed. Pass the password from .env with --admin-password.")
    admin = body["token"]

    users, collectors = setup(api, admin, args.users, args.collectors)
    # Occasional dumping reports for the map.
    for _ in range(3):
        lat, lng = random_point()
        api.call("POST", "/dumping-reports", random.choice(users), lat=lat, lng=lng,
                 photo_url="sim/dumping.jpg", description=random.choice(REPORTS))

    end = time.time() + args.minutes * 60 if args.minutes else None
    log("Simulation running. Open http://localhost:8000/dashboard  (Ctrl+C to stop)")
    try:
        while end is None or time.time() < end:
            tick_users(api, users, chance=0.04)
            for c in collectors:
                tick_collector(api, c)
            time.sleep(args.tick)
    except KeyboardInterrupt:
        pass
    finally:
        for c in collectors:
            api.call("POST", "/collector/offline", c.token)
        log("Simulation stopped; sample collectors set offline.")


if __name__ == "__main__":
    main()
