"""User side of a pickup: quote, request, approve a changed count, pay, rate, track."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db, utcnow
from app.models import (Collector, PickupRequest, Payment, Rating, RequestStatus, Role, RubberSize,
                        User, WasteType)
from app.realtime import manager
from app.schemas import (PaymentIn, PickupIn, PickupOut, QuoteIn, QuoteOut, RatingIn, RubberSizeOut)
from app.security import get_current_user, require_role
from app.services import dispatch, geo, load

router = APIRouter(tags=["pickups"])

RECYCLING_POINTS_PER_UNIT = 10


def pickup_out(req: PickupRequest) -> PickupOut:
    return PickupOut(
        id=req.id, status=req.status, waste_type=req.waste_type, lat=req.lat, lng=req.lng,
        address=req.address, declared_units=req.declared_units, confirmed_units=req.confirmed_units,
        quoted_price=req.quoted_price, proposed_price=req.proposed_price, final_price=req.final_price,
        collector_id=req.collector_id,
        collector_name=req.collector.user.name if req.collector else None,
        offer_expires_at=req.offer_expires_at, created_at=req.created_at,
        items=[{"size_code": i.size.code, "load_units": i.size.load_units,
                "quantity_declared": i.quantity_declared, "quantity_confirmed": i.quantity_confirmed}
               for i in req.items],
    )


def own_request(db: Session, request_id: int, user: User) -> PickupRequest:
    req = db.get(PickupRequest, request_id)
    if not req:
        raise HTTPException(404, "Pickup not found")
    allowed = (user.role == Role.ADMIN or req.user_id == user.id
               or (user.collector and user.collector.id == req.collector_id))
    if not allowed:
        raise HTTPException(404, "Pickup not found")
    return req


@router.get("/rubber-sizes", response_model=list[RubberSizeOut])
def rubber_sizes(db: Session = Depends(get_db)):
    return db.query(RubberSize).order_by(RubberSize.load_units).all()


@router.post("/quote", response_model=QuoteOut)
def get_quote(data: QuoteIn, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    resolved = dispatch.resolve_items(db, data.items)
    units = dispatch.units_of(resolved)
    ranked = dispatch.best_match(db, data.lat, data.lng, units)
    distance = ranked[0].distance_km if ranked else None
    q = dispatch.quote(db, units, data.waste_type, distance or 0)
    return QuoteOut(**q.__dict__, distance_km=distance, collectors_available=len(ranked))


@router.post("/pickups", response_model=PickupOut, status_code=201)
def create_pickup(data: PickupIn, db: Session = Depends(get_db),
                  user: User = Depends(require_role(Role.USER))):
    if db.query(PickupRequest).filter(PickupRequest.user_id == user.id,
                                      PickupRequest.status.in_(RequestStatus.ACTIVE)).count():
        raise HTTPException(409, "You already have a pickup in progress")
    dispatch.expire_offers(db)
    resolved = dispatch.resolve_items(db, data.items)
    units = dispatch.units_of(resolved)
    ranked = dispatch.best_match(db, data.lat, data.lng, units)
    distance = ranked[0].distance_km if ranked else 0
    q = dispatch.quote(db, units, data.waste_type, distance)

    req = PickupRequest(user_id=user.id, lat=data.lat, lng=data.lng, address=data.address,
                        waste_type=data.waste_type, declared_units=units, quoted_price=q.total,
                        quote_distance_km=distance, user_photo_url=data.photo_url,
                        declined_collector_ids=[])
    dispatch.build_items(req, resolved)
    db.add(req)
    db.flush()
    dispatch.offer_next(db, req)
    db.commit()
    return pickup_out(req)


@router.get("/pickups", response_model=list[PickupOut])
def my_pickups(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(PickupRequest)
    if user.role == Role.USER:
        query = query.filter_by(user_id=user.id)
    elif user.role == Role.COLLECTOR:
        query = query.filter_by(collector_id=user.collector.id)
    return [pickup_out(r) for r in query.order_by(PickupRequest.created_at.desc()).limit(100)]


@router.get("/pickups/{request_id}", response_model=PickupOut)
def get_pickup(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dispatch.expire_offers(db)
    return pickup_out(own_request(db, request_id, user))


@router.post("/pickups/{request_id}/cancel", response_model=PickupOut)
def cancel_pickup(request_id: int, db: Session = Depends(get_db),
                  user: User = Depends(require_role(Role.USER))):
    req = own_request(db, request_id, user)
    if req.status not in (RequestStatus.SEARCHING, RequestStatus.OFFERED, RequestStatus.ACCEPTED):
        raise HTTPException(409, "This pickup can no longer be cancelled")
    collector = req.collector or (db.get(Collector, req.offered_to_id) if req.offered_to_id else None)
    req.status = RequestStatus.CANCELLED
    req.offered_to_id = req.offer_expires_at = None
    db.commit()
    if collector:
        manager.notify(collector.user_id, "pickup_cancelled", request_id=req.id)
    dispatch.rematch_waiting(db)
    return pickup_out(req)


@router.post("/pickups/{request_id}/approve", response_model=PickupOut)
def approve_count(request_id: int, db: Session = Depends(get_db),
                  user: User = Depends(require_role(Role.USER))):
    """User accepts the collector's corrected rubber count and the new price."""
    req = own_request(db, request_id, user)
    if req.status != RequestStatus.AWAITING_APPROVAL:
        raise HTTPException(409, "Nothing to approve")
    tricycle = req.collector.tricycle
    reserved_by_others = dispatch.reserved_units(db, req.collector_id) - req.declared_units
    if not load.can_accept(req.confirmed_units, tricycle.capacity_units, tricycle.load_units,
                           max(reserved_by_others, 0)):
        raise HTTPException(409, "The tricycle no longer has space for this load")
    mark_collected(req, req.proposed_price)
    db.commit()
    manager.notify(req.collector.user_id, "count_approved", request_id=req.id)
    return pickup_out(req)


@router.post("/pickups/{request_id}/reject", response_model=PickupOut)
def reject_count(request_id: int, db: Session = Depends(get_db),
                 user: User = Depends(require_role(Role.USER))):
    req = own_request(db, request_id, user)
    if req.status != RequestStatus.AWAITING_APPROVAL:
        raise HTTPException(409, "Nothing to reject")
    req.status = RequestStatus.CANCELLED
    db.commit()
    manager.notify(req.collector.user_id, "count_rejected", request_id=req.id)
    dispatch.rematch_waiting(db)
    return pickup_out(req)


def mark_collected(req: PickupRequest, price) -> None:
    req.status = RequestStatus.COLLECTED
    req.final_price = price
    req.collected_at = utcnow()
    req.collector.tricycle.load_units += req.confirmed_units
    req.collector.last_job_at = req.collected_at


@router.post("/pickups/{request_id}/pay", response_model=PickupOut)
def pay(request_id: int, data: PaymentIn, db: Session = Depends(get_db),
        user: User = Depends(require_role(Role.USER))):
    """Sandbox payment: records the payment without moving real money."""
    req = own_request(db, request_id, user)
    if req.status != RequestStatus.COLLECTED:
        raise HTTPException(409, "Payment is only possible after collection")
    if data.method == "momo" and not data.phone:
        raise HTTPException(422, "Mobile money number is required")
    db.add(Payment(request_id=req.id, amount=req.final_price, method=data.method, phone=data.phone,
                   provider_ref=f"SANDBOX-{uuid.uuid4().hex[:12].upper()}", status="successful"))
    req.status = RequestStatus.PAID
    # Earnings stay held until the waste is verified at a disposal site.
    req.payout_released = req.disposal_log_id is not None
    if req.waste_type == WasteType.RECYCLABLE:
        user.reward_points += req.confirmed_units * RECYCLING_POINTS_PER_UNIT
    db.commit()
    manager.notify(req.collector.user_id, "payment_received", request_id=req.id,
                   amount=str(req.final_price))
    return pickup_out(req)


@router.post("/pickups/{request_id}/rate", status_code=201)
def rate(request_id: int, data: RatingIn, db: Session = Depends(get_db),
         user: User = Depends(require_role(Role.USER))):
    req = own_request(db, request_id, user)
    if req.status != RequestStatus.PAID:
        raise HTTPException(409, "You can rate after paying")
    if db.query(Rating).filter_by(request_id=req.id).first():
        raise HTTPException(409, "Already rated")
    db.add(Rating(request_id=req.id, stars=data.stars, comment=data.comment))
    c = req.collector
    c.rating = round((c.rating * c.rating_count + data.stars) / (c.rating_count + 1), 2)
    c.rating_count += 1
    db.commit()
    return {"message": "Thank you for your rating", "collector_rating": c.rating}


@router.get("/pickups/{request_id}/track")
def track(request_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    req = own_request(db, request_id, user)
    c = req.collector
    if not c or req.status not in (RequestStatus.ACCEPTED, RequestStatus.AWAITING_APPROVAL):
        raise HTTPException(409, "No collector on the way")
    distance = geo.distance_km(c.lat, c.lng, req.lat, req.lng) if c.lat is not None else None
    return {"collector_name": c.user.name, "plate_number": c.tricycle.plate_number,
            "lat": c.lat, "lng": c.lng, "updated_at": c.location_updated_at,
            "distance_km": round(distance, 2) if distance is not None else None}
