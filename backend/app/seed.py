"""Default data so a fresh database is usable straight away.

Prices are placeholders: replace them after surveying current aboboyaa fees.
"""
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DisposalSite, PricingSetting, Role, RubberSize, User
from app.security import hash_password

RUBBER_SIZES = [
    ("small", "Small", "Shopping-bag size, up to about 30 litres", 1),
    ("medium", "Medium", "Standard bin liner or small sack, about 50 litres", 2),
    ("large", "Large", "Large sack or full 100-litre bin", 4),
    ("bulky", "Bulky item", "Furniture, mattress or large debris (per item)", 6),
]

WASTE_TYPE_FACTORS = {"general": "1.0", "organic": "1.0", "recyclable": "0.7", "bulky": "1.5"}


def seed(db: Session) -> None:
    if not db.query(RubberSize).count():
        db.add_all(RubberSize(code=c, name=n, description=d, load_units=u) for c, n, d, u in RUBBER_SIZES)

    if not db.query(PricingSetting).count():
        db.add(PricingSetting(
            base_fee=Decimal("5.00"), rate_per_unit=Decimal("3.00"), rate_per_km=Decimal("1.00"),
            free_radius_km=Decimal("2.00"), waste_type_factors=WASTE_TYPE_FACTORS,
        ))

    if not db.query(DisposalSite).count():
        # Example only: confirm the real coordinates of approved sites before field testing.
        db.add(DisposalSite(name="Example transfer station", lat=5.6037, lng=-0.1870,
                            radius_m=get_settings().default_disposal_radius_m))

    settings = get_settings()
    if not db.query(User).filter_by(role=Role.ADMIN).count():
        db.add(User(name="Administrator", phone="0000000000", email=settings.admin_email,
                    password_hash=hash_password(settings.admin_password), role=Role.ADMIN))

    db.commit()
