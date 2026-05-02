"""
Cliente de infraestructura para obtener datos de mercado desde Yahoo Finance (yfinance).
Programación defensiva: toda llamada externa está envuelta en try/except.
Las excepciones nativas de yfinance nunca burbujean hacia la capa de aplicación.
"""

import logging
from datetime import datetime

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class YahooFinanceClient:
    """
    Cliente para Yahoo Finance que aísla la dependencia externa.
    Si se cambia de proveedor (ej. a Alpha Vantage), solo se modifica esta clase.
    """

    def get_current_price(self, ticker: str) -> float:
        """
        Obtiene el último precio de cierre disponible usando el historial de 1 día.

        Se usa history(period='1d') en lugar de .info porque es más confiable
        y menos propenso a devolver datos stale en mercados cerrados.

        Args:
            ticker: Símbolo bursátil (ej. AAPL, TSLA, BIMBOA.MX).

        Returns:
            Último precio de cierre (Close).

        Raises:
            ValueError: Si el ticker no existe, no tiene datos o la API falla.
        """
        try:
            df = yf.Ticker(ticker).history(period="1d")

            if df.empty:
                raise ValueError(f"Ticker not found or data unavailable: '{ticker}'")

            close_price = float(df["Close"].iloc[-1])
            return close_price

        except ValueError:
            raise
        except Exception as exc:
            logger.exception("Network or API failure fetching price for ticker=%s", ticker)
            raise ValueError(
                f"Ticker not found or data unavailable: '{ticker}'. "
                f"Underlying error: {exc}"
            ) from exc

    def get_dividends_since(self, ticker: str, start_date: datetime) -> float:
        """
        Obtiene la suma de dividendos pagados por el ticker desde start_date hasta hoy.

        Args:
            ticker: Símbolo bursátil.
            start_date: Fecha desde la cual acumular dividendos.

        Returns:
            Suma total de dividendos por título. 0.0 si no hay dividendos en el período.

        Raises:
            ValueError: Si el ticker no existe o la API falla.
        """
        try:
            t = yf.Ticker(ticker)
            dividends = t.dividends

            if dividends is None or dividends.empty:
                return 0.0

            # yfinance devuelve índices timezone-aware (ej. America/New_York).
            # Convertir start_date a Timestamp y alinearlo con la zona horaria del índice
            # para evitar errores de comparación entre naive y aware datetimes.
            start_ts = pd.Timestamp(start_date)
            if dividends.index.tz is not None:
                if start_ts.tz is None:
                    start_ts = start_ts.tz_localize("UTC").tz_convert(dividends.index.tz)
                else:
                    start_ts = start_ts.tz_convert(dividends.index.tz)

            filtered = dividends[dividends.index >= start_ts]

            if filtered.empty:
                return 0.0

            return round(float(filtered.sum()), 4)

        except Exception as exc:
            logger.exception("Network or API failure fetching dividends for ticker=%s", ticker)
            raise ValueError(
                f"Ticker not found or data unavailable: '{ticker}'. "
                f"Underlying error: {exc}"
            ) from exc
