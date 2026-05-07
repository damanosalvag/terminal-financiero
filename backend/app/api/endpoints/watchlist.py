"""
Rutas del módulo de Watchlist / Radar.
Permite monitorear tickers que aún no están en el portafolio, obteniendo
precio actual y RSI en tiempo real desde Yahoo Finance.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.infrastructure.market_data import YahooFinanceClient
from app.models.watchlist import WatchlistTicker
from app.schemas.watchlist import WatchlistCreate, WatchlistResponse
from app.services.finance_math import calculate_rsi

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])

market_client = YahooFinanceClient()


@router.post("/", response_model=WatchlistResponse, status_code=201)
def add_watchlist_ticker(
    payload: WatchlistCreate,
    db: Session = Depends(get_db),
) -> WatchlistResponse:
    """Agrega un nuevo ticker al watchlist (se guarda en mayúsculas)."""
    ticker_upper = payload.ticker.strip().upper()

    existing = db.query(WatchlistTicker).filter(WatchlistTicker.ticker == ticker_upper).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Ticker already in watchlist: {ticker_upper}")

    entry = WatchlistTicker(
        ticker=ticker_upper,
        importance_score=payload.importance_score,
        reason_note=payload.reason_note[:255] if payload.reason_note else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return WatchlistResponse.model_validate(entry)


@router.delete("/{watchlist_id}", status_code=204)
def remove_watchlist_ticker(
    watchlist_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    """Elimina un ticker del watchlist."""
    entry = db.get(WatchlistTicker, watchlist_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Watchlist ticker not found: {watchlist_id}")

    db.delete(entry)
    db.commit()


@router.get("/", response_model=list[WatchlistResponse])
def list_watchlist(
    db: Session = Depends(get_db),
) -> list[WatchlistResponse]:
    """
    Devuelve todos los tickers en watchlist con precio actual y RSI en tiempo real.
    Si un ticker falla al consultar Yahoo Finance, se omite del resultado.
    """
    entries = (
        db.query(WatchlistTicker)
        .order_by(WatchlistTicker.added_date.desc())
        .all()
    )

    result: list[WatchlistResponse] = []

    for entry in entries:
        try:
            current_price = market_client.get_current_price(entry.ticker)
            historical_close = market_client.get_historical_prices(entry.ticker, period="1y")
            current_rsi = calculate_rsi(historical_close)
            target_price = market_client.get_target_price(entry.ticker)
        except ValueError:
            # Ticker inválido o sin datos: se omite del resultado
            continue

        margin_of_safety: float | None = None
        if target_price is not None and current_price is not None and target_price > 0:
            margin_of_safety = round(((target_price - current_price) / target_price) * 100.0, 2)

        result.append(
            WatchlistResponse(
                id=entry.id,
                ticker=entry.ticker,
                added_date=entry.added_date,
                current_price=current_price,
                current_rsi=current_rsi,
                target_price=target_price,
                margin_of_safety=margin_of_safety,
                importance_score=entry.importance_score,
                reason_note=entry.reason_note,
            )
        )

    return result


@router.get("/check/{ticker}")
def check_watchlist_ticker(
    ticker: str,
    db: Session = Depends(get_db),
):
    """Verifica si un ticker ya está en el watchlist."""
    exists = db.query(WatchlistTicker).filter(
        WatchlistTicker.ticker == ticker.strip().upper()
    ).first()
    return {"is_in_watchlist": exists is not None}
