import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WatchlistCreate(BaseModel):
    """Esquema para agregar un ticker al watchlist."""

    ticker: str = Field(..., min_length=1, max_length=10, description="Símbolo bursátil a monitorear")
    importance_score: int = Field(default=1, ge=1, le=5, description="Nivel de importancia (1-5)")
    reason_note: str | None = Field(default=None, max_length=255, description="Razón de seguimiento")


class WatchlistResponse(BaseModel):
    """Ticker en watchlist con datos de mercado en tiempo real."""

    id: uuid.UUID
    ticker: str
    added_date: datetime
    current_price: float | None = None
    current_rsi: float | None = None
    target_price: float | None = None
    margin_of_safety: float | None = None
    importance_score: int = 1
    reason_note: str | None = None

    model_config = ConfigDict(from_attributes=True)
