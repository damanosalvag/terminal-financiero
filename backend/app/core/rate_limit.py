"""Rate limiting en memoria para el endpoint de login (single-user)."""

import time
from collections import defaultdict

from fastapi import HTTPException

_login_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW = 900  # 15 minutos


def check_rate_limit(client_ip: str) -> None:
    """Permite máximo 5 intentos de login por IP en 15 minutos."""
    now = time.time()
    _login_attempts[client_ip] = [t for t in _login_attempts[client_ip] if now - t < _RATE_LIMIT_WINDOW]
    if len(_login_attempts[client_ip]) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos. Espera {_RATE_LIMIT_WINDOW // 60} minutos.",
        )
    _login_attempts[client_ip].append(now)


def clear_rate_limit(client_ip: str) -> None:
    """Limpia intentos fallidos tras un login exitoso."""
    _login_attempts.pop(client_ip, None)
