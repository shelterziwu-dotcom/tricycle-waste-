from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import WasteType

Lat = Field(ge=-90, le=90)
Lng = Field(ge=-180, le=180)


# ---------- auth ----------
class RegisterUser(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=9, max_length=20)
    email: EmailStr | None = None
    password: str = Field(min_length=6)


class RegisterCollector(RegisterUser):
    id_number: str = Field(min_length=3, max_length=50)
    plate_number: str = Field(min_length=3, max_length=20)


class Login(BaseModel):
    phone: str
    password: str


class TokenOut(BaseModel):
    token: str
    role: str
    user_id: int
    name: str


# ---------- catalogue ----------
class RubberSizeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: str
    load_units: int


class RubberItemIn(BaseModel):
    size_code: str
    quantity: int = Field(ge=0, le=100)


class QuoteIn(BaseModel):
    lat: float = Lat
    lng: float = Lng
    waste_type: str = Field(pattern="|".join(WasteType.ALL))
    items: list[RubberItemIn] = Field(min_length=1)


class QuoteOut(BaseModel):
    total_units: int
    base_fee: Decimal
    units_charge: Decimal
    distance_charge: Decimal
    total: Decimal
    distance_km: float | None
    collectors_available: int


# ---------- pickup requests ----------
class PickupIn(QuoteIn):
    address: str | None = Field(default=None, max_length=200)
    photo_url: str | None = None


class ItemOut(BaseModel):
    size_code: str
    load_units: int
    quantity_declared: int
    quantity_confirmed: int | None


class PickupOut(BaseModel):
    id: int
    status: str
    waste_type: str
    lat: float
    lng: float
    address: str | None
    declared_units: int
    confirmed_units: int | None
    quoted_price: Decimal
    proposed_price: Decimal | None
    final_price: Decimal | None
    collector_id: int | None
    collector_name: str | None
    offer_expires_at: datetime | None
    created_at: datetime
    items: list[ItemOut]


class CollectIn(BaseModel):
    items: list[RubberItemIn] = Field(min_length=1)
    photo_url: str = Field(min_length=1)


class PaymentIn(BaseModel):
    method: str = Field(pattern="momo|cash")
    phone: str | None = None


class RatingIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


# ---------- collector ----------
class LocationIn(BaseModel):
    lat: float = Lat
    lng: float = Lng


class LoadOut(BaseModel):
    capacity_units: int
    load_units: int
    reserved_units: int
    available_units: int
    fill_percent: float
    status: str
    nearest_disposal_site: "DisposalSiteOut | None" = None


class DisposalCheckIn(BaseModel):
    site_id: int
    lat: float = Lat
    lng: float = Lng
    photo_url: str = Field(min_length=1)


class DisposalOut(BaseModel):
    verified: bool
    distance_m: float
    units_disposed: int
    jobs_released: int
    message: str


# ---------- admin ----------
class DisposalSiteIn(BaseModel):
    name: str
    lat: float = Lat
    lng: float = Lng
    radius_m: float = Field(gt=0, le=2000)


class DisposalSiteOut(DisposalSiteIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    active: bool


class PricingIn(BaseModel):
    base_fee: Decimal = Field(ge=0)
    rate_per_unit: Decimal = Field(ge=0)
    rate_per_km: Decimal = Field(ge=0)
    free_radius_km: Decimal = Field(ge=0)
    waste_type_factors: dict[str, Decimal]


class PricingOut(PricingIn):
    model_config = ConfigDict(from_attributes=True)


class CollectorAdminIn(BaseModel):
    verified: bool | None = None
    capacity_units: int | None = Field(default=None, gt=0, le=500)


class LiveTricycle(BaseModel):
    collector_id: int
    name: str
    plate_number: str | None
    verified: bool
    is_online: bool
    lat: float | None
    lng: float | None
    capacity_units: int | None
    load_units: int | None
    fill_percent: float | None
    status: str | None


# ---------- dumping reports ----------
class DumpingReportIn(BaseModel):
    lat: float = Lat
    lng: float = Lng
    photo_url: str = Field(min_length=1)
    description: str | None = Field(default=None, max_length=500)


class DumpingReportOut(DumpingReportIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    created_at: datetime


class DumpingStatusIn(BaseModel):
    status: str = Field(pattern="open|assigned|cleared")


LoadOut.model_rebuild()
