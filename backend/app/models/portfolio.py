import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PortfolioPosition(Base):
    """
    Representa una posición en el portafolio del inversionista.
    Permite registrar acciones fraccionadas (quantity float) y el objetivo
    de utilidad anual (por defecto 100% para estrategias de alto rendimiento).
    """

    __tablename__ = "portfolio_positions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    buy_price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    buy_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_inflation: Mapped[float] = mapped_column(Float, default=0.0)
    target_annual_yield: Mapped[float] = mapped_column(Float, default=100.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    exit_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    def __repr__(self) -> str:
        return f"<PortfolioPosition(id={self.id}, ticker={self.ticker}, quantity={self.quantity})>"
