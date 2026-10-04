"""Collector side: availability, location, job offers, collection and disposal."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db, utcnow
from app.models import (Collector, DisposalLog, DisposalSite, PickupRequest, RequestItem,
                        RequestStatus)
from app.realtime import manager
from app.routers.pickups import mark_collected, pickup_out
from app.schemas import (CollectIn, DisposalCheckIn, DisposalOut, DisposalSiteOut, LoadOut,
                         LocationIn, PickupOut)
from app.security import get_current_collector, get_current_user
from app.services import dispatch, geo, load

router = APIRouter(prefix="/collector", tags=["collector"])
sites_router = APIRouter(tags=["disposal"])


def assigned_request(db: Session, request_id: int, collector: Collector) -> PickupRequest:
    req = db.get(PickupRequest, request_id)
    if not req or collector.id not in (req.collector_id, req.offered_to_id):
        raise HTTPException(404, "Job not found")
    return req


@router.get("/load", response_model=LoadOut)
def my_load(db: Session = Depends(get_db), collector: Collector = Depends(get_current_collector)):
    return dispatch.load_summary(db, collector)


@router.post("/online", response_model=LoadOut)
def go_online(data: LocationIn, db: Session = Depends(get_db),
              collector: Collector = Depends(get_current_collector)):
    if not collector.verified:
        raise HTTPException(403, "Your account is waiting for verification by an administrator")
    now = utcnow()
    collector.is_online, collector.online_since = True, now
    collector.lat, collector.lng, collector.location_updated_at = data.lat, data.lng, now
    db.commit()
    dispatch.rematch_waiting(db)
    return dispatch.load_summary(db, collector)


@router.post("/offline")
def go_offline(db: Session = Depends(get_db), collector: Collector = Depends(get_current_collector)):
    collector.is_online = False
    for req in db.query(PickupRequest).filter_by(status=RequestStatus.OFFERED, offered_to_id=collector.id):
        dispatch.decline(req)
        dispatch.offer_next(db, req)
    db.commit()
    return {"message": "You are offline"}


@router.post("/location")
def update_location(data: LocationIn, db: Session = Depends(get_db),
                    collector: Collector = Depends(get_current_collector)):
    collector.lat, collector.lng, collector.location_updated_at = data.lat, data.lng, utcnow()
    db.commit()
    active = db.query(PickupRequest).filter(
        PickupRequest.collector_id == collector.id,
        PickupRequest.status.in_([RequestStatus.ACCEPTED, RequestStatus.AWAITING_APPROVAL])).all()
    for req in active:
        manager.notify(req.user_id, "collector_location", request_id=req.id, lat=data.lat, lng=data.lng)
    return {"message": "Location updated"}


@router.get("/offers", response_model=list[PickupOut])
def offers(db: Session = Depends(get_db), collector: Collector = Depends(get_current_collector)):
    dispatch.expire_offers(db)
    reqs = db.query(PickupRequest).filter_by(status=RequestStatus.OFFERED, offered_to_id=collector.id)
    return [pickup_out(r) for r in reqs]


@router.get("/jobs", response_model=list[PickupOut])
def active_jobs(db: Session = Depends(get_db), collector: Collector = Depends(get_current_collector)):
    reqs = db.query(PickupRequest).filter(
        PickupRequest.collector_id == collector.id,
        PickupRequest.status.in_([RequestStatus.ACCEPTED, RequestStatus.AWAITING_APPROVAL,
                                  RequestStatus.COLLECTED])).order_by(PickupRequest.accepted_at)
    return [pickup_out(r) for r in reqs]


@router.post("/jobs/{request_id}/accept", response_model=PickupOut)
def accept(request_id: int, db: Session = Depends(get_db),
           collector: Collector = Depends(get_current_collector)):
    dispatch.expire_offers(db)
    req = assigned_request(db, request_id, collector)
    if req.status != RequestStatus.OFFERED or req.offered_to_id != collector.id:
        raise HTTPException(409, "This offer has expired")
    t = collector.tricycle
    if not load.can_accept(req.declared_units, t.capacity_units, t.load_units,
                           dispatch.reserved_units(db, collector.id)):
        raise HTTPException(409, "Not enough space on your tricycle for this job")
    req.status, req.collector_id, req.accepted_at = RequestStatus.ACCEPTED, collector.id, utcnow()
    req.offered_to_id = req.offer_expires_at = None
    db.commit()
    manager.notify(req.user_id, "collector_assigned", request_id=req.id, collector=collector.user.name)
    return pickup_out(req)


@router.post("/jobs/{request_id}/decline", response_model=PickupOut)
def decline(request_id: int, db: Session = Depends(get_db),
            collector: Collector = Depends(get_current_collector)):
    req = assigned_request(db, request_id, collector)
    if req.status != RequestStatus.OFFERED or req.offered_to_id != collector.id:
        raise HTTPException(409, "No open offer to decline")
    dispatch.decline(req)
    dispatch.offer_next(db, req)
    db.commit()
    return pickup_out(req)


@router.post("/jobs/{request_id}/collect", response_model=PickupOut)
def collect(request_id: int, data: CollectIn, db: Session = Depends(get_db),
            collector: Collector = Depends(get_current_collector)):
    """Collector confirms the rubbers actually handed over, with a photo."""
    req = assigned_request(db, request_id, collector)
    if req.status != RequestStatus.ACCEPTED or req.collector_id != collector.id:
        raise HTTPException(409, "This job is not ready for collection")

    resolved = dispatch.resolve_items(db, data.items)
    units = dispatch.units_of(resolved)
    t = collector.tricycle
    reserved_by_others = dispatch.reserved_units(db, collector.id) - req.declared_units
    if not load.can_accept(units, t.capacity_units, t.load_units, max(reserved_by_others, 0)):
        raise HTTPException(409, "Not enough space on your tricycle. Go to a disposal site first.")

    by_size = {item.size_id: item for item in req.items}
    for item in req.items:
        item.quantity_confirmed = 0
    for size, qty in resolved:
        if size.id in by_size:
            by_size[size.id].quantity_confirmed = qty
        else:
            req.items.append(RequestItem(size_id=size.id, quantity_declared=0, quantity_confirmed=qty))
    req.confirmed_units = units
    req.collection_photo_url = data.photo_url

    if units == req.declared_units:
        mark_collected(req, req.quoted_price)
        event = "collected"
    else:
        req.proposed_price = dispatch.quote(db, units, req.waste_type, req.quote_distance_km).total
        req.status = RequestStatus.AWAITING_APPROVAL
        event = "count_changed"
    db.commit()
    manager.notify(req.user_id, event, request_id=req.id,
                   price=str(req.final_price or req.proposed_price))
    summary = dispatch.load_summary(db, collector)
    if summary["status"] == load.LoadStatus.FULL.value:
        manager.notify(collector.user_id, "tricycle_full", fill_percent=summary["fill_percent"])
    return pickup_out(req)


@router.post("/disposal-checkin", response_model=DisposalOut)
def disposal_checkin(data: DisposalCheckIn, db: Session = Depends(get_db),
                     collector: Collector = Depends(get_current_collector)):
    """Load is reset and earnings released only inside an approved site's geofence."""
    site = db.get(DisposalSite, data.site_id)
    if not site or not site.active:
        raise HTTPException(404, "Disposal site not found")
    t = collector.tricycle
    if t.load_units <= 0:
        raise HTTPException(409, "Your tricycle is already empty")

    distance = geo.distance_m(data.lat, data.lng, site.lat, site.lng)
    if distance > site.radius_m:
        return DisposalOut(verified=False, distance_m=round(distance), units_disposed=0, jobs_released=0,
                           message=f"You are {round(distance)} m from {site.name}. "
                                   f"Check in from inside the site (within {round(site.radius_m)} m).")

    log = DisposalLog(collector_id=collector.id, tricycle_id=t.id, site_id=site.id,
                      units_disposed=t.load_units, lat=data.lat, lng=data.lng,
                      distance_m=round(distance, 1), photo_url=data.photo_url)
    db.add(log)
    db.flush()
    jobs = db.query(PickupRequest).filter(
        PickupRequest.collector_id == collector.id, PickupRequest.disposal_log_id.is_(None),
        PickupRequest.status.in_([RequestStatus.COLLECTED, RequestStatus.PAID])).all()
    for job in jobs:
        job.disposal_log_id = log.id
        job.payout_released = job.status == RequestStatus.PAID
    units = t.load_units
    t.load_units = 0
    db.commit()
    dispatch.rematch_waiting(db)
    return DisposalOut(verified=True, distance_m=round(distance), units_disposed=units,
                       jobs_released=len(jobs), message=f"Disposal verified at {site.name}. Load reset.")


@sites_router.get("/disposal-sites", response_model=list[DisposalSiteOut])
def disposal_sites(lat: float | None = None, lng: float | None = None,
                   db: Session = Depends(get_db), _=Depends(get_current_user)):
    sites = db.query(DisposalSite).filter_by(active=True).all()
    if lat is not None and lng is not None:
        sites.sort(key=lambda s: geo.distance_m(lat, lng, s.lat, s.lng))
    return sites
