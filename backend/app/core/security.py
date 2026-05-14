"""JWT token creation and verification for single-user authentication."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"
_TOKEN_DAYS = 1  # 1 día en producción


def create_access_token() -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=_TOKEN_DAYS)
    issued_at = datetime.now(timezone.utc)
    payload = {"sub": "admin", "exp": expire, "iat": issued_at}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def verify_access_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        return payload.get("sub") == "admin"
    except JWTError:
        return False
