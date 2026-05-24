"""
Rutas del módulo de Screener / Escáner de Mercado.
"""

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.services.screener import scan_market

router = APIRouter(prefix="/screener", tags=["Screener"])


class ScreenerFilters(BaseModel):
    specific_ticker: str | None = None
    rsi_operator: str | None = None    # '<=' o '>='
    rsi_value: float | None = None     # número libre (ej. 35, 65, 50)
    macd_signal: str | None = None     # 'Alcista', 'Bajista'
    ema_200: str | None = None         # 'Sobre', 'Bajo'
    pe_range: str | None = None        # '< 15', '15-30', '> 30'
    ps_range: str | None = None        # '< 2', '2-5', '> 5'
    market_cap_range: str | None = None  # '> 200B', '10B-200B', '< 10B'
    beta_range: str | None = None      # '< 1', '> 1'
    daily_change: str | None = None    # 'Positiva', 'Negativa'
    sector: str | None = None          # 'Technology', etc.
    volume_range: str | None = None    # '= 1', '< 1', '> 1.5'
    debt_to_equity_range: str | None = None  # '< 100', '100-200', '> 200'


@router.post("/scan")
def run_screener(filters: ScreenerFilters, offset: int = 0, limit: int = 30):
    """Ejecuta un escaneo del mercado con los filtros seleccionados."""
    try:
        return scan_market(filters.model_dump(), offset=offset, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Screener scan failed: {exc}") from exc
