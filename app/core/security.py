from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import secrets

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

# ── Password Hashing ───────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Parolni bcrypt bilan hash qilish."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Parolni tekshirish."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT Tokens ─────────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Access token yaratish."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token() -> tuple[str, str]:
    """
    Refresh token yaratish.
    Returns: (raw_token, token_hash)
    """
    raw_token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def hash_token(raw_token: str) -> str:
    """Raw token ni SHA-256 bilan hash qilish."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def decode_access_token(token: str) -> Optional[dict]:
    """
    Access tokenni decode qilish.
    Returns: payload dict yoki None (xato bo'lsa)
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None
