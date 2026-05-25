"""
Rutas del módulo de Portafolio.
Orquesta las llamadas entre la base de datos, los servicios de matemática financiera
y el cliente de datos de mercado. La lógica de negocio vive en /services, no aquí.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response_cache import cached_response, invalidate_endpoint
from app.infrastructure.market_data import market_client
from app.models.portfolio import PortfolioPosition
from app.schemas.portfolio import (
    PortfolioSummaryResponse,
    PositionAnalysisResponse,
    PositionClose,
    PositionCreate,
    PositionHistoryItem,
    PositionHistoryResponse,
    PositionResponse,
)
from app.services.finance_math import (
    calculate_current_utility_percentage,
    calculate_days_held,
    calculate_rsi,
    calculate_target_exit_price,
    calculate_target_probability,
    calculate_volatility_regime,
)
try:
    from app.services.llm_advisor import analyze_portfolio_news
except ImportError:
    analyze_portfolio_news = None  # type: ignore[assignment]

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


@router.post("/", response_model=PositionResponse, status_code=201)
def create_position(
    payload: PositionCreate,
    db: Session = Depends(get_db),
    response: Response = None,  # type: ignore[assignment]
) -> PositionResponse:
    """
    Crea una nueva posición.
    Si ya existe una posición activa con el mismo ticker, promedia el precio
    de compra de forma ponderada por cantidad y acumula la posición existente.
    El buy_date se mantiene como el más antiguo.
    """
    ticker_upper = payload.ticker.strip().upper()
    existing = (
        db.query(PortfolioPosition)
        .filter(
            PortfolioPosition.ticker == ticker_upper,
            PortfolioPosition.is_active.is_(True),
        )
        .first()
    )

    if existing:
        # Precio promedio ponderado por cantidad
        total_qty = existing.quantity + payload.quantity
        weighted_price = (
            (existing.buy_price * existing.quantity + payload.buy_price * payload.quantity)
            / total_qty
        )
        existing.buy_price = round(weighted_price, 6)
        existing.quantity = total_qty
        existing.commission = existing.commission + (payload.commission or 0.0)
        # Actualizar parámetros financieros con los nuevos valores
        existing.estimated_inflation = payload.estimated_inflation
        existing.target_annual_yield = payload.target_annual_yield
        # buy_date conserva el más antiguo (el existente)
        db.commit()
        db.refresh(existing)
        if response is not None:
            response.status_code = 200
        invalidate_endpoint("portfolio")
        return PositionResponse.model_validate(existing)

    # Ticker nuevo: crear posición normalmente
    data = payload.model_dump()
    data["ticker"] = ticker_upper
    position = PortfolioPosition(**data)
    db.add(position)
    db.commit()
    db.refresh(position)
    invalidate_endpoint("portfolio")
    return PositionResponse.model_validate(position)


@router.get("/", response_model=list[PositionResponse])
def list_positions(
    db: Session = Depends(get_db),
) -> list[PositionResponse]:
    """Devuelve todas las posiciones activas del portafolio."""
    positions = (
        db.query(PortfolioPosition)
        .filter(PortfolioPosition.is_active.is_(True))
        .order_by(PortfolioPosition.buy_date.desc())
        .all()
    )
    return [PositionResponse.model_validate(p) for p in positions]


def _analyze_one_position(
    position: PortfolioPosition,
    historical_close: list[float],
    now: datetime,
) -> PositionAnalysisResponse | None:
    """
    Procesa una posición: usa OHLCV pre-cargado del batch, y consulta en paralelo
    info_batch (sector/target/beta) + dividends_since. Calcula todas las métricas.

    Retorna None si no hay suficientes datos para esa posición.
    """
    if not historical_close or len(historical_close) < 2:
        return None

    # Precio actual: durante mercado abierto, history(1y) ya incluye la barra del día
    # con su Close actualizado. Si el cache de precio intradía está fresco, lo preferimos
    # (más actualizado que la barra diaria intradía durante horario de mercado).
    try:
        current_price = market_client.get_current_price(position.ticker)
    except ValueError:
        # Fallback: usar el último cierre del batch (puede ser de ayer si pre-market)
        current_price = historical_close[-1]

    # Las dos llamadas restantes son independientes — ejecutar en paralelo:
    # - get_dividends_since: cache 6h
    # - get_info_batch:      cache 6h
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_div = ex.submit(market_client.get_dividends_since, position.ticker, position.buy_date)
        fut_info = ex.submit(
            market_client.get_info_batch, position.ticker, current_price
        )
        try:
            dividends_per_share: float = fut_div.result()
        except Exception:
            dividends_per_share = 0.0
        try:
            ticker_info: dict = fut_info.result()
        except Exception:
            ticker_info = {"sector": "Unknown", "target_mean_price": None, "beta": None}

    current_rsi = calculate_rsi(historical_close)

    # Daily change %
    daily_change_pct: float | None = None
    prev = historical_close[-2]
    last = historical_close[-1]
    if prev > 0:
        daily_change_pct = round(((last - prev) / prev) * 100, 2)

    commission_per_share = position.commission / position.quantity
    days_held = calculate_days_held(position.buy_date, now)

    target_exit = calculate_target_exit_price(
        buy_price=position.buy_price,
        commission=commission_per_share,
        target_annual_yield=position.target_annual_yield,
        days_held=days_held,
        estimated_inflation=position.estimated_inflation,
        dividends_collected=dividends_per_share,
    )

    utility_pct = calculate_current_utility_percentage(
        buy_price=position.buy_price,
        current_price=current_price,
        commission=commission_per_share,
        estimated_inflation=position.estimated_inflation,
        days_held=days_held,
        dividends_collected=dividends_per_share,
    )

    target_mean_price: float | None = ticker_info.get("target_mean_price")
    beta_val: float | None = ticker_info.get("beta")
    sector: str = ticker_info.get("sector", "Unknown") or "Unknown"

    heartbeat_days, sigma = calculate_volatility_regime(historical_close)
    volatility_window: int = int(max(21, 2 * heartbeat_days))

    target_probability = calculate_target_probability(
        target_exit_price=target_exit,
        current_price=current_price,
        target_mean_price=target_mean_price,
        days_held=heartbeat_days,
        beta=beta_val,
        sigma=sigma,
    )

    return PositionAnalysisResponse(
        id=position.id,
        ticker=position.ticker,
        quantity=position.quantity,
        buy_price=position.buy_price,
        currency=position.currency,
        buy_date=position.buy_date,
        commission=position.commission,
        estimated_inflation=position.estimated_inflation,
        target_annual_yield=position.target_annual_yield,
        is_active=position.is_active,
        exit_price=position.exit_price,
        exit_date=position.exit_date,
        current_price=current_price,
        dividends_collected=dividends_per_share,
        days_held=days_held,
        target_exit_price=target_exit,
        current_utility_percentage=utility_pct,
        current_rsi=current_rsi,
        sector=sector,
        daily_change_pct=daily_change_pct,
        target_probability=target_probability,
        heartbeat_days=heartbeat_days,
        volatility_window=volatility_window,
    )


@router.get("/summary", response_model=PortfolioSummaryResponse)
@cached_response(open_ttl=30, closed_ttl=300)
def portfolio_summary(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> PortfolioSummaryResponse:
    """
    Analiza el portafolio completo: calcula capital invertido total, valor actual
    total y el porcentaje de utilidad global ponderada.

    Optimizaciones:
    1. Batch OHLCV: una sola request a yf.download() trae 1y de todas las posiciones.
    2. Singleton client: caches compartidas con watchlist y analysis.
    3. ThreadPoolExecutor(max_workers=3) procesa N posiciones concurrentemente.
       Cada posición a su vez paraleliza dividends + info_batch internamente.

    Si un ticker falla, se omite sin detener el resumen del resto.
    """
    positions = (
        db.query(PortfolioPosition)
        .filter(PortfolioPosition.is_active.is_(True))
        .order_by(PortfolioPosition.buy_date.desc())
        .all()
    )

    if not positions:
        return PortfolioSummaryResponse(
            total_invested_capital=0.0,
            total_current_value=0.0,
            global_utility_percentage=0.0,
            positions=[],
        )

    now = datetime.now(timezone.utc)

    # 1) BATCH OHLCV: una sola request HTTP trae 1y de TODOS los tickers.
    #    Reemplaza N × get_historical_prices secuenciales por 1 batch.
    unique_tickers = list({p.ticker for p in positions})
    batch_ohlcv = market_client.download_batch_history(unique_tickers, period="1y")

    # 2) Procesar cada posición en paralelo (max 3 workers).
    #    Cada worker reusa el OHLCV pre-cargado y hace solo 2 calls extra
    #    (dividends + info_batch), también en paralelo internamente.
    def process(position: PortfolioPosition) -> PositionAnalysisResponse | None:
        try:
            return _analyze_one_position(
                position=position,
                historical_close=batch_ohlcv.get(position.ticker, []),
                now=now,
            )
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(process, positions))

    analyzed: list[PositionAnalysisResponse] = [r for r in results if r is not None]

    total_invested = 0.0
    total_current = 0.0
    for r in analyzed:
        invested = r.buy_price * r.quantity + r.commission
        current_value = r.current_price * r.quantity + r.dividends_collected * r.quantity
        total_invested += invested
        total_current += current_value

    global_utility = (
        ((total_current - total_invested) / total_invested * 100.0)
        if total_invested > 0
        else 0.0
    )

    return PortfolioSummaryResponse(
        total_invested_capital=round(total_invested, 2),
        total_current_value=round(total_current, 2),
        global_utility_percentage=round(global_utility, 2),
        positions=analyzed,
    )


@router.get("/history", response_model=PositionHistoryResponse)
def position_history(
    db: Session = Depends(get_db),
) -> PositionHistoryResponse:
    """
    Devuelve el historial de posiciones cerradas con utilidad realizada
    y métricas agregadas avanzadas (mejor/peor trade, win rate, comisiones totales).
    No consume APIs externas: usa exit_price y exit_date guardados en la base de datos.
    """
    closed = (
        db.query(PortfolioPosition)
        .filter(PortfolioPosition.is_active.is_(False))
        .order_by(PortfolioPosition.buy_date.desc())
        .all()
    )

    # Comisiones de TODAS las posiciones (activas + cerradas) — agregado SQL,
    # evita traer cada fila a Python para sumar.
    total_commissions_sum: float | None = db.query(
        func.sum(PortfolioPosition.commission)
    ).scalar()
    total_commissions_paid = round(float(total_commissions_sum or 0.0), 2)

    history_items: list[PositionHistoryItem] = []
    total_realized = 0.0

    best_ticker: str | None = None
    best_profit: float | None = None
    worst_ticker: str | None = None
    worst_loss: float | None = None
    winning_trades = 0

    for position in closed:
        # Una posición cerrada siempre debe tener exit_price y exit_date.
        # Si por algún motivo no los tiene, se omite del historial.
        if position.exit_price is None or position.exit_date is None:
            continue

        invested = position.buy_price * position.quantity + position.commission
        exit_value = position.exit_price * position.quantity
        realized_profit = exit_value - invested
        realized_pct = (realized_profit / invested * 100.0) if invested > 0 else 0.0

        # Días reales entre compra y cierre (sin forzar mínimo, puede ser 0)
        buy_dt = position.buy_date.replace(tzinfo=None)
        exit_dt = position.exit_date.replace(tzinfo=None)
        actual_days = abs((exit_dt - buy_dt).days)

        total_realized += realized_profit

        if realized_profit > 0:
            winning_trades += 1

        # Joya de la Corona / Agujero Negro
        if best_profit is None or realized_profit > best_profit:
            best_profit = realized_profit
            best_ticker = position.ticker
        if worst_loss is None or realized_profit < worst_loss:
            worst_loss = realized_profit
            worst_ticker = position.ticker

        history_items.append(
            PositionHistoryItem(
                id=position.id,
                ticker=position.ticker,
                quantity=position.quantity,
                buy_price=position.buy_price,
                currency=position.currency,
                buy_date=position.buy_date,
                commission=position.commission,
                estimated_inflation=position.estimated_inflation,
                target_annual_yield=position.target_annual_yield,
                is_active=position.is_active,
                exit_price=position.exit_price,
                exit_date=position.exit_date,
                realized_profit_currency=round(realized_profit, 2),
                realized_utility_percentage=round(realized_pct, 2),
                actual_days_held=actual_days,
            )
        )

    total_trades = len(history_items)
    win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

    return PositionHistoryResponse(
        total_realized_profit=round(total_realized, 2),
        total_closed_positions=total_trades,
        positions=history_items,
        best_trade_ticker=best_ticker,
        best_trade_profit=round(best_profit, 2) if best_profit is not None else None,
        worst_trade_ticker=worst_ticker,
        worst_trade_loss=round(worst_loss, 2) if worst_loss is not None else None,
        win_rate_percentage=round(win_rate, 2),
        total_commissions_paid=total_commissions_paid,
    )


@router.get("/{position_id}/analysis", response_model=PositionAnalysisResponse)
def analyze_position(
    position_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> PositionAnalysisResponse:
    """
    Endpoint orquestador: combina datos de la base de datos, precios de mercado
    en tiempo real y cálculos financieros para devolver una vista completa de la posición.

    1. Recupera la posición desde la DB (404 si no existe).
    2. Consulta el precio actual y dividendos acumulados vía YahooFinanceClient.
    3. Calcula días transcurridos, precio de salida objetivo y utilidad real neta.
    4. Retorna la posición con todas las métricas dinámicas.
    """
    position = db.get(PortfolioPosition, position_id)
    if position is None:
        raise HTTPException(status_code=404, detail=f"Position not found: {position_id}")

    # Obtener datos de mercado. Si el ticker es inválido o la API falla, se propaga como 400.
    try:
        current_price = market_client.get_current_price(position.ticker)
        dividends_per_share = market_client.get_dividends_since(
            position.ticker, position.buy_date
        )
        historical_close = market_client.get_historical_prices(position.ticker, period="1y")
        current_rsi = calculate_rsi(historical_close)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Convertir valores totales a valores por título para el servicio de matemática
    commission_per_share = position.commission / position.quantity

    # Métricas financieras (servicio puro, sin efectos secundarios)
    now = datetime.now(timezone.utc)
    days_held = calculate_days_held(position.buy_date, now)

    target_exit = calculate_target_exit_price(
        buy_price=position.buy_price,
        commission=commission_per_share,
        target_annual_yield=position.target_annual_yield,
        days_held=days_held,
        estimated_inflation=position.estimated_inflation,
        dividends_collected=dividends_per_share,
    )

    utility_pct = calculate_current_utility_percentage(
        buy_price=position.buy_price,
        current_price=current_price,
        commission=commission_per_share,
        estimated_inflation=position.estimated_inflation,
        days_held=days_held,
        dividends_collected=dividends_per_share,
    )

    return PositionAnalysisResponse(
        id=position.id,
        ticker=position.ticker,
        quantity=position.quantity,
        buy_price=position.buy_price,
        currency=position.currency,
        buy_date=position.buy_date,
        commission=position.commission,
        estimated_inflation=position.estimated_inflation,
        target_annual_yield=position.target_annual_yield,
        is_active=position.is_active,
        current_price=current_price,
        dividends_collected=dividends_per_share,
        days_held=days_held,
        target_exit_price=target_exit,
        current_utility_percentage=utility_pct,
        current_rsi=current_rsi,
    )


@router.patch("/{position_id}/close", response_model=PositionResponse)
def close_position(
    position_id: uuid.UUID,
    payload: PositionClose,
    db: Session = Depends(get_db),
) -> PositionResponse:
    """
    Cierra una posición activa: registra el precio y fecha de salida,
    y la marca como inactiva (is_active = False).

    Retorna 404 si la posición no existe.
    """
    position = db.get(PortfolioPosition, position_id)
    if position is None:
        raise HTTPException(status_code=404, detail=f"Position not found: {position_id}")

    position.exit_price = payload.exit_price
    position.exit_date = payload.exit_date
    position.is_active = False

    db.commit()
    db.refresh(position)
    invalidate_endpoint("portfolio")
    return PositionResponse.model_validate(position)


@router.get("/news-intel")
def get_news_intel(db: Session = Depends(get_db)):
    """
    Inteligencia de noticias para el portafolio activo.
    Para cada ticker activo, obtiene noticias recientes y las analiza con IA (DeepSeek).
    """
    if analyze_portfolio_news is None:
        raise HTTPException(status_code=503, detail="LLM advisor not available.")

    positions = (
        db.query(PortfolioPosition)
        .filter(PortfolioPosition.is_active.is_(True))
        .all()
    )

    unique_tickers = list({p.ticker for p in positions})
    if not unique_tickers:
        return {"count": 0, "results": []}

    def analyze_one(ticker: str):
        try:
            news = market_client.get_recent_news(ticker)
            llm_result = analyze_portfolio_news(ticker, news) if news else None
            return {
                "ticker": ticker,
                "llm_analysis": llm_result,
                "news": news[:3] if news else [],
            }
        except Exception:
            return {
                "ticker": ticker,
                "llm_analysis": None,
                "news": [],
            }

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(analyze_one, unique_tickers))

    return {"count": len(results), "results": results}
