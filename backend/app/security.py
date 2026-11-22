# backend/app/security.py
"""Authentication, hashing, JWT, and server-side RBAC dependencies."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

ROLES = ["citizen", "helper", "officer", "admin", "auditor"]
ALLOWED_SIGNUP_ROLES = ["citizen", "helper"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(user_id: int, role: str, name: str = "", username: str = "") -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "role": role,
        "name": name,
        "username": username,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_token(user: User) -> str:
    """Convenience alias accepting a User model."""
    return create_access_token(
        user_id=user.id,
        role=user.role,
        name=user.name or user.full_name,
        username=user.username or "",
    )


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    oauth_token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve current user from Bearer header or OAuth2 form token."""
    raw_token = None
    if credentials and credentials.scheme.lower() == "bearer":
        raw_token = credentials.credentials
    elif oauth_token:
        raw_token = oauth_token

    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not raw_token:
        raise cred_exc

    payload = decode_token(raw_token)
    if payload is None or "sub" not in payload:
        raise cred_exc

    user_id = payload.get("sub")
    try:
        user = db.get(User, int(user_id))
    except (ValueError, TypeError):
        raise cred_exc

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def require_role(*allowed_roles: str):
    """Dependency factory: require_role('officer', 'admin') -> 403 if forbidden."""
    allowed_set = set(allowed_roles)

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not allowed here; requires one of: {', '.join(allowed_roles)}",
            )
        return current_user

    return checker
