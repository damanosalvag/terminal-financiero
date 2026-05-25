"""
Response cache market-aware para endpoints de FastAPI.

Mecanismo:
- Dict en memoria con TTL dinámico según horario de mercado.
- Durante NYSE abierto (L-V 9:30am-4:00pm America/New_York): TTL corto (30s)
  para que los precios mostrados sean frescos para el trader.
- Fuera de mercado: TTL largo (5min) — los precios no cambian.
- Bypass del cache con query param `force=true`.

Uso:
    @router.get("/summary")
    @cached_response(open_ttl=30, closed_ttl=300)
    def portfolio_summary(...):
        ...

NOTA: el decorator debe envolver una función SIN async (sincrónica),
ya que todos los endpoints de este proyecto son síncronos.
"""

import json
import logging
import threading
import time
from datetime import datetime
from functools import wraps
from typing import Any, Callable
from zoneinfo import ZoneInfo

from fastapi import Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Zona horaria de NYSE
_NY_TZ = ZoneInfo("America/New_York")

# Festivos NYSE fijos básicos (mes, día). Se omiten festivos movibles como
# Memorial Day, Thanksgiving, etc. para simplificar — durante festivos movibles
# el cache devolverá TTL de "mercado abierto" pero como no hay datos nuevos
# el efecto es mínimo (sirve cache stale).
_FIXED_HOLIDAYS = {
    (1, 1),    # New Year
    (7, 4),    # Independence Day
    (12, 25),  # Christmas
}


def is_market_open_now() -> bool:
    """
    Determina si NYSE está abierto AHORA mismo.
    Returns True si es L-V 9:30-16:00 ET y no es festivo fijo conocido.
    """
    now_ny = datetime.now(_NY_TZ)

    # Fin de semana
    if now_ny.weekday() >= 5:  # 5=Sat, 6=Sun
        return False

    # Festivo conocido
    if (now_ny.month, now_ny.day) in _FIXED_HOLIDAYS:
        return False

    # Horario 9:30 - 16:00
    minutes_since_midnight = now_ny.hour * 60 + now_ny.minute
    market_open = 9 * 60 + 30   # 09:30
    market_close = 16 * 60       # 16:00
    return market_open <= minutes_since_midnight < market_close


# ── Cache storage ────────────────────────────────────────────────────
# Key: tuple (endpoint_path, hashable args), Value: (json_str, expires_at)
_cache: dict[tuple, tuple[str, float]] = {}
_cache_lock = threading.Lock()


def _make_key(endpoint: str, request: Request) -> tuple:
    """Genera la cache key a partir del path + query string."""
    # query_string es bytes; lo decodificamos
    qs = request.url.query or ""
    return (endpoint, qs)


def cached_response(open_ttl: int = 30, closed_ttl: int = 300) -> Callable:
    """
    Decorator para cachear respuestas de endpoints sincrónicos de FastAPI.

    Args:
        open_ttl: TTL en segundos cuando NYSE está abierto.
        closed_ttl: TTL en segundos cuando NYSE está cerrado.

    El endpoint decorado DEBE aceptar un parámetro `request: Request` para que
    el decorator pueda leer el query string. Si el query string incluye `force=true`,
    se bypasea el cache y se recomputa el valor.
    """
    def decorator(func: Callable) -> Callable:
        endpoint_name = f"{func.__module__}.{func.__name__}"

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            request: Request | None = kwargs.get("request")
            if request is None:
                # Fallback: buscar el Request en args posicionales
                for a in args:
                    if isinstance(a, Request):
                        request = a
                        break

            # Si no hay Request, no podemos cachear → ejecutar directo
            if request is None:
                return func(*args, **kwargs)

            force = request.query_params.get("force", "").lower() in ("1", "true", "yes")
            key = _make_key(endpoint_name, request)
            now = time.time()

            # Hit fresco: devolvemos JSONResponse con el body cacheado RAW.
            # Esto evita re-validar por Pydantic y re-serializar — el cache hit
            # es prácticamente instantáneo (<1ms).
            if not force:
                with _cache_lock:
                    entry = _cache.get(key)
                if entry is not None and entry[1] > now:
                    logger.debug("Response cache HIT %s", endpoint_name)
                    return Response(
                        content=entry[0],
                        media_type="application/json",
                        headers={"X-Cache": "HIT"},
                    )

            # Miss → ejecutar y cachear
            result = func(*args, **kwargs)

            # Serializar (Pydantic models se convierten con model_dump)
            try:
                if hasattr(result, "model_dump"):
                    payload = result.model_dump(mode="json")
                else:
                    payload = result
                json_str = json.dumps(payload, default=str)
                ttl = open_ttl if is_market_open_now() else closed_ttl
                with _cache_lock:
                    _cache[key] = (json_str, now + ttl)
                # Anotar headers en la response que FastAPI emitirá
                response = kwargs.get("response")
                if response is not None:
                    response.headers["X-Cache"] = "MISS"
                    response.headers["X-Cache-TTL"] = str(ttl)
            except Exception as exc:
                logger.warning("Failed to cache response for %s: %s", endpoint_name, exc)

            return result

        return wrapper
    return decorator


def invalidate_cache() -> None:
    """Borra todo el cache de respuestas. Útil tras mutaciones (create/close position)."""
    with _cache_lock:
        _cache.clear()
    logger.info("Response cache invalidated")


def invalidate_endpoint(endpoint_substring: str) -> None:
    """Borra entradas cuya cache_key contenga el substring dado (ej: 'portfolio')."""
    with _cache_lock:
        keys_to_drop = [k for k in _cache if endpoint_substring in k[0]]
        for k in keys_to_drop:
            _cache.pop(k, None)
    if keys_to_drop:
        logger.info("Response cache invalidated %d entries matching '%s'", len(keys_to_drop), endpoint_substring)
