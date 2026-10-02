from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Collector, Role, User

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user: User) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(UTC) + timedelta(hours=settings.token_hours),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def user_from_token(token: str, db: Session) -> User | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return db.get(User, int(payload["sub"]))


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    user = user_from_token(credentials.credentials, db) if credentials else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in")
    return user


def require_role(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this action")
        return user
    return checker


def get_current_collector(user: User = Depends(require_role(Role.COLLECTOR)),
                          db: Session = Depends(get_db)) -> Collector:
    collector = db.query(Collector).filter_by(user_id=user.id).one()
    return collector
