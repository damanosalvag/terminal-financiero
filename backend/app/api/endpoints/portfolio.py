"""
Rutas del módulo de Portafolio.
Orquesta las llamadas entre la base de datos, los servicios de matemática financiera
y el cliente de datos de mercado. La lógica de negocio vive en /services, no aquí.
"""

import time
import uuid
from datetime import datetime, timezone

import random
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.infrastructure.market_data import YahooFinanceClient
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

# Cliente de mercado instanciado a nivel de módulo.
# Si se cambia de proveedor, solo se reemplaza esta línea.
market_client = YahooFinanceClient()

# Caché de sectores exitosos en memoria (los sectores rara vez cambian).
# Solo se cachean éxitos — los fallos NO se cachean para permitir reintentos.
_sector_cache: dict[str, str] = {}


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
        return PositionResponse.model_validate(existing)

    # Ticker nuevo: crear posición normalmente
    data = payload.model_dump()
    data["ticker"] = ticker_upper
    position = PortfolioPosition(**data)
    db.add(position)
    db.commit()
    db.refresh(position)
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


@router.get("/summary", response_model=PortfolioSummaryResponse)
def portfolio_summary(
    db: Session = Depends(get_db),
) -> PortfolioSummaryResponse:
    """
    Analiza el portafolio completo: calcula capital invertido total, valor actual
    total y el porcentaje de utilidad global ponderada.

    Itera sobre todas las posiciones activas. Si un ticker falla al consultar
    el precio de mercado, se omite esa posición individual sin detener el resumen.
    """
    positions = (
        db.query(PortfolioPosition)
        .filter(PortfolioPosition.is_active.is_(True))
        .order_by(PortfolioPosition.buy_date.desc())
        .all()
    )

    analyzed: list[PositionAnalysisResponse] = []
    total_invested = 0.0
    total_current = 0.0
    now = datetime.now(timezone.utc)

    for i, position in enumerate(positions):
        # Throttle con jitter entre tickers: se salta el primero para no añadir
        # latencia innecesaria al inicio de la carga del portafolio.
        if i > 0:
            time.sleep(0.5 + random.uniform(0, 0.5))

        try:
            current_price = market_client.get_current_price(position.ticker)
            dividends_per_share = market_client.get_dividends_since(
                position.ticker, position.buy_date
            )
            historical_close = market_client.get_historical_prices(position.ticker, period="1y")
            current_rsi = calculate_rsi(historical_close)
        except ValueError:
            continue

        # Daily change: diferencia porcentual entre el último y penúltimo cierre
        daily_change_pct: float | None = None
        if historical_close and len(historical_close) >= 2:
            prev = historical_close[-2]
            last = historical_close[-1]
            if prev > 0:
                daily_change_pct = round(((last - prev) / prev) * 100, 2)

        # Una sola llamada a .info obtiene sector, target y beta.
        # get_info_batch() usa caché de sector exitoso y degrada elegantemente.
        ticker_info = market_client.get_info_batch(position.ticker, current_price=current_price)
        sector = ticker_info["sector"]
        # Cachear solo sectores válidos (no "Unknown") para evitar contaminación de caché
        if sector and sector != "Unknown":
            _sector_cache[position.ticker] = sector
        elif position.ticker in _sector_cache:
            sector = _sector_cache[position.ticker]

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

        invested = position.buy_price * position.quantity + position.commission
        current_value = current_price * position.quantity + dividends_per_share * position.quantity

        total_invested += invested
        total_current += current_value

        # Probabilidad de alcanzar el precio objetivo (modelo híbrido log-normal + penalización analistas)
        target_mean_price: float | None = ticker_info["target_mean_price"]
        beta_val: float | None = ticker_info["beta"]

        # Régimen de volatilidad: heartbeat + sigma dinámico basado en anomalías
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

        analyzed.append(
            PositionAnalysisResponse(
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
        )

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

    # Comisiones de TODAS las posiciones (activas + cerradas)
    total_commissions = db.query(PortfolioPosition).with_entities(
        PortfolioPosition.commission
    ).all()
    total_commissions_paid = round(sum(float(c[0]) for c in total_commissions), 2)

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
