"""
Rutas del módulo de Watchlist / Radar.
Fetch paralelo con ThreadPoolExecutor usando el singleton market_client,
que comparte caches (precio 120s, info 6h, history 10min) con el endpoint de portafolio.
Si un ticker ya fue consultado por /portfolio/summary dentro de los TTLs,
las requests a Yahoo se evitan completamente.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response_cache import cached_response, invalidate_endpoint
from app.infrastructure.market_data import market_client
from app.models.watchlist import WatchlistTicker
from app.schemas.watchlist import WatchlistCreate, WatchlistResponse
from app.services.finance_math import calculate_rsi

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


def _fetch_ticker_data(entry: WatchlistTicker) -> WatchlistResponse | None:
    """
    Usa el singleton market_client para que el watchlist comparta caches con portfolio:
      - get_current_price (cache 120s)
      - get_info_batch    (cache 6h — sector/target/beta)
      - get_historical_prices para RSI (cache 10min)

    Si el mismo ticker ya fue consultado por el portfolio dentro del TTL, esta llamada
    no genera ninguna request HTTP a Yahoo.
    """
    try:
        # 1) Precio actual — usa cache 120s
        try:
            current_price = market_client.get_current_price(entry.ticker)
        except ValueError:
            return None

        # 2) Info batch — target_mean_price + sector + beta (cache 6h)
        info_batch = market_client.get_info_batch(entry.ticker, current_price=current_price)
        target_price: float | None = info_batch.get("target_mean_price")

        # 3) Historical 1y para RSI (cache 10min)
        try:
            closing_prices = market_client.get_historical_prices(entry.ticker, period="1y")
            current_rsi: float | None = calculate_rsi(closing_prices) if closing_prices else None
        except ValueError:
            current_rsi = None

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
    invalidate_endpoint("watchlist")
    return WatchlistResponse.model_validate(entry)


@router.delete("/{watchlist_id}", status_code=204)
def remove_watchlist_ticker(watchlist_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    entry = db.get(WatchlistTicker, watchlist_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Watchlist ticker not found: {watchlist_id}")
    db.delete(entry)
    db.commit()
    invalidate_endpoint("watchlist")


@router.get("/", response_model=list[WatchlistResponse])
@cached_response(open_ttl=30, closed_ttl=300)
def list_watchlist(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> list[WatchlistResponse]:
    """
    Devuelve todos los tickers del radar en paralelo.
    Cada ticker hace 2 llamadas HTTP (.info + history(1y)) y se ejecutan
    concurrentemente con ThreadPoolExecutor(max_workers=3) — respeta el límite
    del .cursorrules para Render (512MB RAM).
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

