"""
Rutas del módulo de Screener / Escáner de Mercado.
Filtra el universo de tickers usando indicadores técnicos descargados en batch.
"""

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.services.screener import scan_market

router = APIRouter(prefix="/screener", tags=["Screener"])


class ScreenerFilters(BaseModel):
    rsi_below_40: bool = False
    macd_bullish: bool = False
    above_ema_200: bool = False
    rsi_above_70: bool = False


@router.post("/scan")
def run_screener(filters: ScreenerFilters):
    """
    Ejecuta un escaneo del mercado con los filtros técnicos seleccionados.

    Body (JSON):
        {
            "rsi_below_40": true,
            "macd_bullish": true,
            "above_ema_200": false,
            "rsi_above_70": false
        }

    Returns:
        {
            "count": 8,
            "results": [{"ticker", "current_price", "rsi", "macd_signal", "macd_value", "ema_200_diff_pct"}]
        }
    """
    try:
        return scan_market(filters.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Screener scan failed: {exc}") from exc
