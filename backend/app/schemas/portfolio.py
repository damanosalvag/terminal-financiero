import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PositionCreate(BaseModel):
    """Esquema para crear una nueva posición de portafolio."""

    ticker: str = Field(..., min_length=1, max_length=10, description="Símbolo bursátil")
    quantity: float = Field(..., gt=0.0, description="Número de títulos (acepta fracciones)")
    buy_price: float = Field(..., gt=0.0, description="Precio unitario de compra")
    currency: str = Field(..., min_length=3, max_length=3, description="Código de moneda (USD, MXN, EUR)")
    buy_date: datetime = Field(..., description="Fecha de adquisición de la posición")
    commission: float = Field(default=0.0, ge=0.0, description="Comisión pagada por la operación")
    estimated_inflation: float = Field(default=0.0, ge=0.0, description="Inflación anual estimada en %")
    target_annual_yield: float = Field(
        default=100.0,
        ge=0.0,
        description="Objetivo de utilidad anual en % (por defecto 100% para duplicar capital)",
    )
    is_active: bool = Field(default=True, description="Indica si la posición está activa en el portafolio")


class PositionUpdate(BaseModel):
    """Esquema para actualizar parcialmente una posición existente. Todos los campos son opcionales."""

    ticker: str | None = Field(default=None, min_length=1, max_length=10)
    quantity: float | None = Field(default=None, gt=0.0)
    buy_price: float | None = Field(default=None, gt=0.0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    buy_date: datetime | None = None
    commission: float | None = Field(default=None, ge=0.0)
    estimated_inflation: float | None = Field(default=None, ge=0.0)
    target_annual_yield: float | None = Field(default=None, ge=0.0)
    is_active: bool | None = None


class PositionClose(BaseModel):
    """Esquema para cerrar una posición: registra el precio y la fecha de salida."""

    exit_price: float = Field(..., gt=0.0, description="Precio unitario al que se vendió el título")
    exit_date: datetime = Field(..., description="Fecha en que se cerró la posición")


class PositionResponse(BaseModel):
    """Esquema para devolver una posición desde la base de datos."""

    id: uuid.UUID
    ticker: str
    quantity: float
    buy_price: float
    currency: str
    buy_date: datetime
    commission: float
    estimated_inflation: float
    target_annual_yield: float
    is_active: bool
    exit_price: float | None = None
    exit_date: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PositionAnalysisResponse(PositionResponse):
    """Posición con métricas dinámicas calculadas en tiempo real (precio actual, objetivo, utilidad)."""

    current_price: float
    dividends_collected: float
    days_held: int
    target_exit_price: float
    current_utility_percentage: float
    current_rsi: float | None = None


class PortfolioSummaryResponse(BaseModel):
    """Resumen macro del portafolio completo con métricas agregadas y posiciones individuales."""

    total_invested_capital: float
    total_current_value: float
    global_utility_percentage: float
    positions: list[PositionAnalysisResponse]


class PositionHistoryItem(PositionResponse):
    """Posición cerrada con métricas de utilidad realizada."""

    realized_profit_currency: float
    realized_utility_percentage: float
    actual_days_held: int


class PositionHistoryResponse(BaseModel):
    """Resumen de posiciones cerradas con ganancia/pérdida total realizada y métricas avanzadas."""

    total_realized_profit: float
    total_closed_positions: int
    positions: list[PositionHistoryItem]
    best_trade_ticker: str | None = None
    best_trade_profit: float | None = None
    worst_trade_ticker: str | None = None
    worst_trade_loss: float | None = None
    win_rate_percentage: float = 0.0
    total_commissions_paid: float = 0.0
