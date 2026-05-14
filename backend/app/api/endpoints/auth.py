"""Rutas de autenticación (single-user)."""

import hmac

from fastapi import APIRouter, HTTPException, Request, Response

from app.core.config import settings
from app.core.rate_limit import check_rate_limit, clear_rate_limit
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> TokenResponse:
    """
    Valida credenciales con comparación timing-safe.
    Aplica rate limiting de 5 intentos por IP en 15 minutos.
    Devuelve el token en el body JSON y como cookie HttpOnly.
    """
    client_ip: str = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    # hmac.compare_digest evita ataques de timing side-channel
    username_ok: bool = hmac.compare_digest(payload.username, settings.AUTH_USERNAME)
    password_ok: bool = hmac.compare_digest(payload.password, settings.AUTH_PASSWORD)

    if not username_ok or not password_ok:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clear_rate_limit(client_ip)
    token: str = create_access_token()

    # Cookie HttpOnly con SameSite=None para cross-domain (Render ↔ Vercel).
    # En desarrollo local (http://localhost) esto funciona porque el navegador
    # NO exige Secure para SameSite=None en localhost.
    response.set_cookie(
        key="token",
        value=token,
        max_age=86400,
        path="/",
        httponly=True,
        samesite="none",
        secure=settings.COOKIE_SECURE,
    )

    return TokenResponse(access_token=token)
