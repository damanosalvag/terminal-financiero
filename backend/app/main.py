import hmac
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.endpoints.analysis import router as analysis_router
from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.portfolio import router as portfolio_router
from app.api.endpoints.screener import router as screener_router
from app.api.endpoints.watchlist import router as watchlist_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.security import verify_access_token

logger = logging.getLogger(__name__)

# ── Rate limiting (en memoria, suficiente para single-user) ─────────
_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 900  # 15 minutos


def check_rate_limit(client_ip: str) -> None:
    """Permite máximo 5 intentos de login por IP en 15 minutos."""
    now = time.time()
    attempts = _login_attempts[client_ip]
    # Limpiar intentos fuera de la ventana de tiempo
    _login_attempts[client_ip] = [t for t in attempts if now - t < _RATE_LIMIT_WINDOW]
    if len(_login_attempts[client_ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos. Espera {_RATE_LIMIT_WINDOW // 60} minutos.",
        )
    _login_attempts[client_ip].append(now)


def clear_rate_limit(client_ip: str) -> None:
    """Limpia los intentos fallidos tras un login exitoso."""
    _login_attempts.pop(client_ip, None)


# ── Public paths que no requieren JWT ───────────────────────────────
_public_paths = {"/", "/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect"}


def verify_auth(request: Request) -> None:
    """
    Dependencia global de autenticación.
    Excluye rutas públicas, rutas /auth/* y preflight OPTIONS de CORS.
    """
    # CORS preflight: no debe verificar auth
    if request.method == "OPTIONS":
        return

    if request.url.path.startswith("/auth") or request.url.path in _public_paths:
        return

    auth_header: str | None = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing auth token")

    token: str = auth_header.split(" ", 1)[1]
    if not verify_access_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Crea las tablas en Supabase al iniciar la aplicación."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tables created successfully.")
    except Exception as exc:
        logger.warning("Could not create tables: %s", exc)
    yield


# ── CORS debe registrarse ANTES que cualquier router ────────────────
origins: list[str] = settings.ALLOWED_ORIGINS.split(",") if settings.ALLOWED_ORIGINS else ["*"]

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    dependencies=[Depends(verify_auth)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(analysis_router)
app.include_router(screener_router)


@app.get("/")
def root() -> dict[str, Any]:
    return {"status": "ok", "project": settings.PROJECT_NAME}
