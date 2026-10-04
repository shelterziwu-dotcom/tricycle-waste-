from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow

Money = Numeric(10, 2)


class Role:
    USER = "user"
    COLLECTOR = "collector"
    ADMIN = "admin"


class RequestStatus:
    SEARCHING = "searching"            # waiting for a collector with space
    OFFERED = "offered"                # offered to one collector, awaiting reply
    ACCEPTED = "accepted"              # collector on the way
    AWAITING_APPROVAL = "awaiting_approval"  # rubber count differed; user must approve new price
    COLLECTED = "collected"            # on the tricycle, awaiting payment
    PAID = "paid"
    CANCELLED = "cancelled"

    ACTIVE = (SEARCHING, OFFERED, ACCEPTED, AWAITING_APPROVAL)


class WasteType:
    GENERAL = "general"
    ORGANIC = "organic"
    RECYCLABLE = "recyclable"
    BULKY = "bulky"
    ALL = (GENERAL, ORGANIC, RECYCLABLE, BULKY)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.USER)
    reward_points: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    collector: Mapped["Collector | None"] = relationship(back_populates="user", uselist=False)


class Collector(Base):
    __tablename__ = "collectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    id_number: Mapped[str] = mapped_column(String(50))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[float] = mapped_column(Float, default=4.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    location_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_job_at: Mapped[datetime | None] = mapped_column(DateTime)
    online_since: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[User] = relationship(back_populates="collector")
    tricycle: Mapped["Tricycle | None"] = relationship(back_populates="collector", uselist=False)


class Tricycle(Base):
    __tablename__ = "tricycles"

    id: Mapped[int] = mapped_column(primary_key=True)
    collector_id: Mapped[int] = mapped_column(ForeignKey("collectors.id"), unique=True)
    plate_number: Mapped[str] = mapped_column(String(20), unique=True)
    capacity_units: Mapped[int] = mapped_column(Integer)
    load_units: Mapped[int] = mapped_column(Integer, default=0)

    collector: Mapped[Collector] = relationship(back_populates="tricycle")


class RubberSize(Base):
    __tablename__ = "rubber_sizes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(200))
    load_units: Mapped[int] = mapped_column(Integer)


class PricingSetting(Base):
    __tablename__ = "pricing_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    base_fee: Mapped[Decimal] = mapped_column(Money)
    rate_per_unit: Mapped[Decimal] = mapped_column(Money)
    rate_per_km: Mapped[Decimal] = mapped_column(Money)
    free_radius_km: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    waste_type_factors: Mapped[dict] = mapped_column(JSON)


class PickupRequest(Base):
    __tablename__ = "pickup_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    collector_id: Mapped[int | None] = mapped_column(ForeignKey("collectors.id"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    address: Mapped[str | None] = mapped_column(String(200))
    waste_type: Mapped[str] = mapped_column(String(20))
    declared_units: Mapped[int] = mapped_column(Integer)
    confirmed_units: Mapped[int | None] = mapped_column(Integer)
    quoted_price: Mapped[Decimal] = mapped_column(Money)
    quote_distance_km: Mapped[float] = mapped_column(Float, default=0)
    proposed_price: Mapped[Decimal | None] = mapped_column(Money)
    final_price: Mapped[Decimal | None] = mapped_column(Money)
    status: Mapped[str] = mapped_column(String(20), default=RequestStatus.SEARCHING, index=True)
    offered_to_id: Mapped[int | None] = mapped_column(ForeignKey("collectors.id"))
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    declined_collector_ids: Mapped[list] = mapped_column(JSON, default=list)
    user_photo_url: Mapped[str | None] = mapped_column(String(300))
    collection_photo_url: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime)
    disposal_log_id: Mapped[int | None] = mapped_column(ForeignKey("disposal_logs.id"))
    payout_released: Mapped[bool] = mapped_column(Boolean, default=False)

    items: Mapped[list["RequestItem"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    collector: Mapped[Collector | None] = relationship(foreign_keys=[collector_id])


class RequestItem(Base):
    __tablename__ = "request_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("pickup_requests.id"))
    size_id: Mapped[int] = mapped_column(ForeignKey("rubber_sizes.id"))
    quantity_declared: Mapped[int] = mapped_column(Integer)
    quantity_confirmed: Mapped[int | None] = mapped_column(Integer)

    request: Mapped[PickupRequest] = relationship(back_populates="items")
    size: Mapped[RubberSize] = relationship()


class DisposalSite(Base):
    __tablename__ = "disposal_sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class DisposalLog(Base):
    __tablename__ = "disposal_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    collector_id: Mapped[int] = mapped_column(ForeignKey("collectors.id"), index=True)
    tricycle_id: Mapped[int] = mapped_column(ForeignKey("tricycles.id"))
    site_id: Mapped[int] = mapped_column(ForeignKey("disposal_sites.id"))
    units_disposed: Mapped[int] = mapped_column(Integer)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    distance_m: Mapped[float] = mapped_column(Float)
    photo_url: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("pickup_requests.id"), unique=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    method: Mapped[str] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(20))
    provider_ref: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    paid_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("pickup_requests.id"), unique=True)
    stars: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)


class DumpingReport(Base):
    __tablename__ = "dumping_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    photo_url: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
