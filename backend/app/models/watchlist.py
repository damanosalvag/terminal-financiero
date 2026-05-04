import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WatchlistTicker(Base):
    """
    Tickers en el radar de monitoreo. Activos que aún no están en el portafolio
    pero que se siguen para detectar puntos de entrada basados en momentum.
    """

    __tablename__ = "watchlist_tickers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    added_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<WatchlistTicker(id={self.id}, ticker={self.ticker})>"
