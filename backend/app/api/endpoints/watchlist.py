"""
Rutas del módulo de Watchlist / Radar.
Fetch paralelo con ThreadPoolExecutor — una sola llamada a yf.Ticker(t).info
por ticker (contiene precio, target y sector). Se añade get_historical_prices
solo para el RSI, también en paralelo.
"""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import random
import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.infrastructure.market_data import YahooFinanceClient
from app.models.watchlist import WatchlistTicker
from app.schemas.watchlist import WatchlistCreate, WatchlistResponse
from app.services.finance_math import calculate_rsi

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])
market_client = YahooFinanceClient()


def _fetch_ticker_data(entry: WatchlistTicker) -> WatchlistResponse | None:
    """
    Consolida las 3 llamadas anteriores en 2:
      1. yf.Ticker(t).info → precio actual + target (una sola sesión HTTP)
      2. history(period='1y') → cierres para RSI
    El throttle se aplica DESPUÉS de .info para que los workers del ThreadPoolExecutor
    disparen sus requests inmediatamente en paralelo, y solo duerman antes de la segunda call.
    """
    try:
        t = yf.Ticker(entry.ticker)
        info = t.info
        # Throttle tras la primera call: espaciar la segunda request (history)
        # sin bloquear el inicio paralelo de otros workers.
        time.sleep(0.3 + random.uniform(0, 0.4))

        # Precio actual — prefiere regularMarketPrice, cae en currentPrice
        current_price: float | None = None
        raw_price = info.get("regularMarketPrice") or info.get("currentPrice")
        if raw_price is not None:
            current_price = float(raw_price)

        # Si info no trae precio, intentar con history de 1 día
        if current_price is None:
            hist_day = t.history(period="1d")
            if not hist_day.empty:
                current_price = float(hist_day["Close"].iloc[-1])

        if current_price is None:
            return None

        # Target price (mismo info object, sin llamada extra)
        target_price: float | None = None
        raw_target = info.get("targetMeanPrice")
        if raw_target is not None:
            target_price = float(raw_target)

        # RSI a 1 año — segunda y única llamada de red separada
        hist = t.history(period="1y")
        current_rsi: float | None = None
        if not hist.empty:
            closing_prices = [float(v) for v in hist["Close"].tolist()]
            current_rsi = calculate_rsi(closing_prices)

        margin_of_safety: float | None = None
        if target_price is not None and current_price > 0:
            margin_of_safety = round(((target_price - current_price) / target_price) * 100.0, 2)

        return WatchlistResponse(
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
    except Exception:
        return None


@router.post("/", response_model=WatchlistResponse, status_code=201)
def add_watchlist_ticker(payload: WatchlistCreate, db: Session = Depends(get_db)) -> WatchlistResponse:
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
def remove_watchlist_ticker(watchlist_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    entry = db.get(WatchlistTicker, watchlist_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Watchlist ticker not found: {watchlist_id}")
    db.delete(entry)
    db.commit()


@router.get("/", response_model=list[WatchlistResponse])
def list_watchlist(db: Session = Depends(get_db)) -> list[WatchlistResponse]:
    """
    Devuelve todos los tickers del radar en paralelo.
    Cada ticker hace 2 llamadas HTTP en lugar de 3, y todas se ejecutan
    concurrentemente con ThreadPoolExecutor(max_workers=8).
    """
    entries = (
        db.query(WatchlistTicker)
        .order_by(WatchlistTicker.added_date.desc())
        .all()
    )
    if not entries:
        return []

    with ThreadPoolExecutor(max_workers=3) as executor:
        responses = list(executor.map(_fetch_ticker_data, entries))

    return [r for r in responses if r is not None]


@router.get("/check/{ticker}")
def check_watchlist_ticker(ticker: str, db: Session = Depends(get_db)):
    exists = db.query(WatchlistTicker).filter(
        WatchlistTicker.ticker == ticker.strip().upper()
    ).first()
    return {"is_in_watchlist": exists is not None}

