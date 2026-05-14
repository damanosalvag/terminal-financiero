"""Dependency de FastAPI para autenticación JWT."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verify_access_token

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> None:
    """Valida el token JWT. Lanza 401 si es inválido o expirado."""
    if not verify_access_token(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
