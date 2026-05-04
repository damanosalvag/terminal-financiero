"""
Rutas del módulo de Análisis / Asset Cockpit.
Provee datos para gráficos de velas y métricas de activos individuales.
"""

from fastapi import APIRouter, HTTPException

from app.infrastructure.market_data import YahooFinanceClient

router = APIRouter(prefix="/analysis", tags=["Analysis"])

market_client = YahooFinanceClient()


@router.get("/{ticker}/chart")
def get_chart_data(ticker: str):
    """
    Devuelve datos OHLCV históricos para renderizar un gráfico de velas (candlestick).

    Args:
        ticker: Símbolo bursátil (ej. AAPL, TSLA).

    Returns:
        Lista de velas con date, open, high, low, close, volume.
    """
    try:
        candles = market_client.get_ohlcv_data(ticker, period="6mo")
        return candles
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
