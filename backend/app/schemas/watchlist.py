import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WatchlistCreate(BaseModel):
    """Esquema para agregar un ticker al watchlist."""

    ticker: str = Field(..., min_length=1, max_length=10, description="Símbolo bursátil a monitorear")


class WatchlistResponse(BaseModel):
    """Ticker en watchlist con datos de mercado en tiempo real."""

    id: uuid.UUID
    ticker: str
    added_date: datetime
    current_price: float | None = None
    current_rsi: float | None = None
    target_price: float | None = None
    margin_of_safety: float | None = None

    model_config = ConfigDict(from_attributes=True)
