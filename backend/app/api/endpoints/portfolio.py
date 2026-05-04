"""
Rutas del módulo de Portafolio.
Orquesta las llamadas entre la base de datos, los servicios de matemática financiera
y el cliente de datos de mercado. La lógica de negocio vive en /services, no aquí.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
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
    calculate_target_exit_price,
)

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

# Cliente de mercado instanciado a nivel de módulo.
# Si se cambia de proveedor, solo se reemplaza esta línea.
market_client = YahooFinanceClient()


@router.post("/", response_model=PositionResponse, status_code=201)
def create_position(
    payload: PositionCreate,
    db: Session = Depends(get_db),
) -> PositionResponse:
    """Crea una nueva posición en el portafolio."""
    position = PortfolioPosition(**payload.model_dump())
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

    for position in positions:
        try:
            current_price = market_client.get_current_price(position.ticker)
            dividends_per_share = market_client.get_dividends_since(
                position.ticker, position.buy_date
            )
        except ValueError:
            # Un ticker problemático no debe detener el análisis del resto del portafolio
            continue

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
    Devuelve el historial de posiciones cerradas con utilidad realizada.
    No consume APIs externas: usa exit_price y exit_date guardados en la base de datos.
    """
    closed = (
        db.query(PortfolioPosition)
        .filter(PortfolioPosition.is_active.is_(False))
        .order_by(PortfolioPosition.buy_date.desc())
        .all()
    )

    history_items: list[PositionHistoryItem] = []
    total_realized = 0.0

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

    return PositionHistoryResponse(
        total_realized_profit=round(total_realized, 2),
        total_closed_positions=len(history_items),
        positions=history_items,
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
