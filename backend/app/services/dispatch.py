"""Database side of matching, load tracking and disposal.

The pure rules live in pricing.py, load.py, matching.py and geo.py; this module
loads the data they need and applies their decisions.
"""
from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import utcnow
from app.models import (Collector, DisposalSite, PickupRequest, PricingSetting, RequestItem,
                        RequestStatus, RubberSize, Tricycle)
from app.realtime import manager
from app.services import geo, load, matching, pricing


# ---------- pricing ----------
def pricing_config(db: Session) -> pricing.PricingConfig:
    s = db.query(PricingSetting).first()
    return pricing.PricingConfig(
        base_fee=Decimal(s.base_fee), rate_per_unit=Decimal(s.rate_per_unit),
        rate_per_km=Decimal(s.rate_per_km), free_radius_km=Decimal(s.free_radius_km),
        waste_type_factors={k: Decimal(str(v)) for k, v in s.waste_type_factors.items()},
    )


def resolve_items(db: Session, items) -> list[tuple[RubberSize, int]]:
    sizes = {s.code: s for s in db.query(RubberSize).all()}
    resolved = []
    for item in items:
        if item.size_code not in sizes:
            raise HTTPException(422, f"Unknown rubber size: {item.size_code}")
        if item.quantity:
            resolved.append((sizes[item.size_code], item.quantity))
    if not resolved:
        raise HTTPException(422, "Add at least one rubber")
    return resolved


def units_of(resolved: list[tuple[RubberSize, int]]) -> int:
    return pricing.total_units([(size.load_units, qty) for size, qty in resolved])


def quote(db: Session, units: int, waste_type: str, distance_km: float) -> pricing.Quote:
    try:
        return pricing.calculate_price(units, waste_type, distance_km, pricing_config(db))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


# ---------- load ----------
def reserved_units(db: Session, collector_id: int) -> int:
    """Units of jobs accepted (or awaiting approval) but not yet loaded."""
    return db.query(func.coalesce(func.sum(PickupRequest.declared_units), 0)).filter(
        PickupRequest.collector_id == collector_id,
        PickupRequest.status.in_([RequestStatus.ACCEPTED, RequestStatus.AWAITING_APPROVAL]),
    ).scalar()


def load_summary(db: Session, collector: Collector) -> dict:
    t = collector.tricycle
    reserved = reserved_units(db, collector.id)
    status = load.load_status(t.load_units, t.capacity_units)
    summary = {
        "capacity_units": t.capacity_units,
        "load_units": t.load_units,
        "reserved_units": reserved,
        "available_units": load.available_units(t.capacity_units, t.load_units, reserved),
        "fill_percent": load.fill_percent(t.load_units, t.capacity_units),
        "status": status.value,
        "nearest_disposal_site": None,
    }
    if status in (load.LoadStatus.NEARLY_FULL, load.LoadStatus.FULL) and collector.lat is not None:
        summary["nearest_disposal_site"] = nearest_site(db, collector.lat, collector.lng)
    return summary


def nearest_site(db: Session, lat: float, lng: float) -> DisposalSite | None:
    sites = db.query(DisposalSite).filter_by(active=True).all()
    return min(sites, key=lambda s: geo.distance_m(lat, lng, s.lat, s.lng), default=None)


# ---------- matching ----------
def candidates(db: Session, exclude: set[int] = frozenset()) -> list[matching.Candidate]:
    settings = get_settings()
    now = utcnow()
    fresh_after = now - timedelta(minutes=settings.location_stale_minutes)
    busy_with_offer = {cid for (cid,) in db.query(PickupRequest.offered_to_id).filter(
        PickupRequest.status == RequestStatus.OFFERED).all()}

    rows = (db.query(Collector).join(Tricycle)
            .filter(Collector.verified.is_(True), Collector.is_online.is_(True),
                    Collector.lat.is_not(None), Collector.location_updated_at >= fresh_after)
            .all())
    result = []
    for c in rows:
        if c.id in exclude or c.id in busy_with_offer:
            continue
        since = c.last_job_at or c.online_since or now
        result.append(matching.Candidate(
            collector_id=c.id, lat=c.lat, lng=c.lng, rating=c.rating,
            minutes_waiting=(now - since).total_seconds() / 60,
            capacity_units=c.tricycle.capacity_units, load_units=c.tricycle.load_units,
            reserved_units=reserved_units(db, c.id),
        ))
    return result


def best_match(db: Session, lat: float, lng: float, units: int,
               exclude: set[int] = frozenset()) -> list[matching.RankedCandidate]:
    return matching.rank(lat, lng, units, candidates(db, exclude), get_settings().match_radius_km)


def offer_next(db: Session, req: PickupRequest) -> None:
    """Offer the request to the best eligible collector, or leave it searching."""
    ranked = best_match(db, req.lat, req.lng, req.declared_units, set(req.declined_collector_ids or []))
    if not ranked:
        req.status, req.offered_to_id, req.offer_expires_at = RequestStatus.SEARCHING, None, None
        return
    top = ranked[0]
    req.status = RequestStatus.OFFERED
    req.offered_to_id = top.collector_id
    req.offer_expires_at = utcnow() + timedelta(seconds=get_settings().offer_timeout_seconds)
    collector = db.get(Collector, top.collector_id)
    manager.notify(collector.user_id, "job_offer", request_id=req.id, units=req.declared_units,
                   distance_km=top.distance_km)


def expire_offers(db: Session) -> None:
    """Treat unanswered offers as declined and move them on."""
    expired = db.query(PickupRequest).filter(PickupRequest.status == RequestStatus.OFFERED,
                                             PickupRequest.offer_expires_at < utcnow()).all()
    for req in expired:
        decline(req)
        offer_next(db, req)
    if expired:
        db.commit()


def rematch_waiting(db: Session) -> None:
    """Retry requests still searching, oldest first (after a collector frees up space)."""
    waiting = (db.query(PickupRequest).filter_by(status=RequestStatus.SEARCHING)
               .order_by(PickupRequest.created_at).all())
    for req in waiting:
        offer_next(db, req)
    db.commit()


def decline(req: PickupRequest) -> None:
    if req.offered_to_id is not None:
        req.declined_collector_ids = [*(req.declined_collector_ids or []), req.offered_to_id]
    req.offered_to_id = None
    req.offer_expires_at = None


def build_items(req: PickupRequest, resolved: list[tuple[RubberSize, int]]) -> None:
    req.items = [RequestItem(size_id=size.id, quantity_declared=qty) for size, qty in resolved]
