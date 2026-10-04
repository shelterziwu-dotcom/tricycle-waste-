"""Administrator tools: verification, capacity, prices, disposal sites, live map, reports."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (Collector, DisposalLog, DisposalSite, DumpingReport, PickupRequest,
                        PricingSetting, RequestStatus, Role, User)
from app.schemas import (CollectorAdminIn, DisposalSiteIn, DisposalSiteOut, DumpingReportOut,
                         DumpingStatusIn, LiveTricycle, PricingIn, PricingOut)
from app.security import require_role
from app.services import dispatch, load

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role(Role.ADMIN))])


def live_row(db: Session, c: Collector) -> LiveTricycle:
    t = c.tricycle
    return LiveTricycle(
        collector_id=c.id, name=c.user.name, plate_number=t.plate_number if t else None,
        verified=c.verified, is_online=c.is_online, lat=c.lat, lng=c.lng,
        capacity_units=t.capacity_units if t else None, load_units=t.load_units if t else None,
        fill_percent=load.fill_percent(t.load_units, t.capacity_units) if t else None,
        status=load.load_status(t.load_units, t.capacity_units).value if t else None,
    )


@router.get("/collectors", response_model=list[LiveTricycle])
def collectors(db: Session = Depends(get_db)):
    return [live_row(db, c) for c in db.query(Collector).all()]


@router.patch("/collectors/{collector_id}", response_model=LiveTricycle)
def update_collector(collector_id: int, data: CollectorAdminIn, db: Session = Depends(get_db)):
    c = db.get(Collector, collector_id)
    if not c:
        raise HTTPException(404, "Collector not found")
    if data.verified is not None:
        c.verified = data.verified
    if data.capacity_units is not None:
        c.tricycle.capacity_units = data.capacity_units
    db.commit()
    return live_row(db, c)


@router.get("/live", response_model=list[LiveTricycle])
def live_map(db: Session = Depends(get_db)):
    """Online tricycles with location and load status, for the colour-coded map."""
    return [live_row(db, c) for c in db.query(Collector).filter_by(is_online=True).all()]


@router.get("/pricing", response_model=PricingOut)
def get_pricing(db: Session = Depends(get_db)):
    return db.query(PricingSetting).first()


@router.put("/pricing", response_model=PricingOut)
def set_pricing(data: PricingIn, db: Session = Depends(get_db)):
    s = db.query(PricingSetting).first()
    s.base_fee, s.rate_per_unit = data.base_fee, data.rate_per_unit
    s.rate_per_km, s.free_radius_km = data.rate_per_km, data.free_radius_km
    s.waste_type_factors = {k: str(v) for k, v in data.waste_type_factors.items()}
    db.commit()
    return s


@router.get("/disposal-sites", response_model=list[DisposalSiteOut])
def all_sites(db: Session = Depends(get_db)):
    return db.query(DisposalSite).all()


@router.post("/disposal-sites", response_model=DisposalSiteOut, status_code=201)
def add_site(data: DisposalSiteIn, db: Session = Depends(get_db)):
    site = DisposalSite(**data.model_dump())
    db.add(site)
    db.commit()
    return site


@router.patch("/disposal-sites/{site_id}", response_model=DisposalSiteOut)
def toggle_site(site_id: int, active: bool, db: Session = Depends(get_db)):
    site = db.get(DisposalSite, site_id)
    if not site:
        raise HTTPException(404, "Site not found")
    site.active = active
    db.commit()
    return site


@router.get("/dumping-reports", response_model=list[DumpingReportOut])
def dumping_reports(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(DumpingReport)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(DumpingReport.created_at.desc()).all()


@router.patch("/dumping-reports/{report_id}", response_model=DumpingReportOut)
def update_report(report_id: int, data: DumpingStatusIn, db: Session = Depends(get_db)):
    report = db.get(DumpingReport, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    report.status = data.status
    db.commit()
    return report


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    done = db.query(PickupRequest).filter(
        PickupRequest.status.in_([RequestStatus.COLLECTED, RequestStatus.PAID]))
    units_collected = done.with_entities(func.coalesce(func.sum(PickupRequest.confirmed_units), 0)).scalar()
    units_disposed = db.query(func.coalesce(func.sum(DisposalLog.units_disposed), 0)).scalar()
    revenue = db.query(func.coalesce(func.sum(PickupRequest.final_price), 0)).filter(
        PickupRequest.status == RequestStatus.PAID).scalar()
    return {
        "users": db.query(User).filter_by(role=Role.USER).count(),
        "collectors": db.query(Collector).count(),
        "collectors_online": db.query(Collector).filter_by(is_online=True).count(),
        "pickups_completed": done.count(),
        "pickups_waiting": db.query(PickupRequest).filter_by(status=RequestStatus.SEARCHING).count(),
        "units_collected": units_collected,
        "units_disposed_verified": units_disposed,
        # Share of collected waste confirmed at an approved site.
        "disposal_compliance_percent": round(100 * units_disposed / units_collected, 1) if units_collected else None,
        "revenue": str(Decimal(revenue).quantize(Decimal("0.01"))),
        "open_dumping_reports": db.query(DumpingReport).filter_by(status="open").count(),
    }
