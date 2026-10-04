from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Collector, Role, Tricycle, User
from app.schemas import Login, RegisterCollector, RegisterUser, TokenOut
from app.security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Placeholder until an admin measures the tricycle's cargo box at onboarding.
DEFAULT_CAPACITY_UNITS = 40


def _check_unique(db: Session, phone: str, email: str | None) -> None:
    if db.query(User).filter_by(phone=phone).first():
        raise HTTPException(409, "An account with this phone number already exists")
    if email and db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "An account with this email already exists")


def _token(user: User) -> TokenOut:
    return TokenOut(token=create_token(user), role=user.role, user_id=user.id, name=user.name)


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterUser, db: Session = Depends(get_db)):
    _check_unique(db, data.phone, data.email)
    user = User(name=data.name, phone=data.phone, email=data.email,
                password_hash=hash_password(data.password), role=Role.USER)
    db.add(user)
    db.commit()
    return _token(user)


@router.post("/register-collector", response_model=TokenOut, status_code=201)
def register_collector(data: RegisterCollector, db: Session = Depends(get_db)):
    _check_unique(db, data.phone, data.email)
    if db.query(Tricycle).filter_by(plate_number=data.plate_number).first():
        raise HTTPException(409, "This tricycle is already registered")
    user = User(name=data.name, phone=data.phone, email=data.email,
                password_hash=hash_password(data.password), role=Role.COLLECTOR)
    collector = Collector(user=user, id_number=data.id_number)
    db.add_all([user, collector,
                Tricycle(collector=collector, plate_number=data.plate_number,
                         capacity_units=DEFAULT_CAPACITY_UNITS)])
    db.commit()
    return _token(user)


@router.post("/login", response_model=TokenOut)
def login(data: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(phone=data.phone).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Wrong phone number or password")
    return _token(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    out = {"id": user.id, "name": user.name, "phone": user.phone, "email": user.email,
           "role": user.role, "reward_points": user.reward_points}
    if user.collector:
        out["collector"] = {"id": user.collector.id, "verified": user.collector.verified,
                            "rating": user.collector.rating, "is_online": user.collector.is_online}
    return out

