"""
Cliente de infraestructura para obtener datos de mercado desde Yahoo Finance (yfinance).
Programación defensiva: toda llamada externa está envuelta en try/except.
Las excepciones nativas de yfinance nunca burbujean hacia la capa de aplicación.

Si se cambia de proveedor (ej. a Alpha Vantage), solo se modifica esta clase.
"""

import logging
from datetime import datetime
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class YahooFinanceClient:
    """
    Cliente para Yahoo Finance que aísla la dependencia externa.
    Si se cambia de proveedor (ej. a Alpha Vantage), solo se modifica esta clase.
    """

    def _get_ticker(self, ticker: str) -> yf.Ticker:
        return yf.Ticker(ticker)

    def get_current_price(self, ticker: str) -> float:
        """
        Obtiene el último precio de cierre usando history(period='1d').
        Con manejo defensivo de rate limiting y errores de red.
        """
        try:
            df = self._get_ticker(ticker).history(period="1d")
            if df.empty:
                raise ValueError(f"Ticker not found or data unavailable: '{ticker}'")
            return float(df["Close"].iloc[-1])
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("Market data fetch failed for ticker=%s: %s", ticker, exc)
            raise ValueError(
                f"Ticker not found or data unavailable: '{ticker}'. Underlying error: {exc}"
            ) from exc

    def get_historical_prices(self, ticker: str, period: str = "1y") -> list[float]:
        """Obtiene precios de cierre históricos para indicadores técnicos."""
        try:
            df = self._get_ticker(ticker).history(period=period)
            if df.empty or "Close" not in df.columns:
                raise ValueError(f"Ticker not found or data unavailable: '{ticker}'")
            return [float(v) for v in df["Close"].tolist()]
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("Historical prices failed for ticker=%s: %s", ticker, exc)
            raise ValueError(
                f"Ticker not found or data unavailable: '{ticker}'. Underlying error: {exc}"
            ) from exc

    def get_ohlcv_data(self, ticker: str, period: str = "6mo") -> list[dict[str, Any]]:
        """Obtiene OHLCV para gráficos de velas."""
        try:
            df = self._get_ticker(ticker).history(period=period)
            if df.empty:
                raise ValueError(f"Ticker not found or data unavailable: '{ticker}'")
            candles: list[dict[str, Any]] = []
            for dt, row in df.iterrows():
                candles.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                })
            return candles
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("OHLCV data failed for ticker=%s: %s", ticker, exc)
            raise ValueError(
                f"Ticker not found or data unavailable: '{ticker}'. Underlying error: {exc}"
            ) from exc

    def get_target_price(self, ticker: str) -> float | None:
        """Obtiene targetMeanPrice de analistas."""
        try:
            info = self._get_ticker(ticker).info
            target = info.get("targetMeanPrice")
            return float(target) if target is not None else None
        except Exception as exc:
            logger.warning("Target price failed for ticker=%s: %s", ticker, exc)
            return None

    def get_fundamentals(self, ticker: str) -> dict[str, Any]:
        """Obtiene ratios fundamentales desde Yahoo Finance."""
        try:
            t = self._get_ticker(ticker)
            info = t.info

            def _safe_float(key: str) -> float | None:
                val = info.get(key)
                return float(val) if val is not None else None

            dividend_info: dict[str, Any] = {
                "next_ex_date": _safe_float("exDividendDate"),
                "history": [],
                "payments_per_year": 0,
            }
            try:
                if not t.dividends.empty:
                    now_ts = pd.Timestamp.now(tz=t.dividends.index.tz) if t.dividends.index.tz else pd.Timestamp.now()
                    one_year_ago = now_ts - pd.Timedelta(days=365)
                    recent_divs = t.dividends[t.dividends.index >= one_year_ago]
                    for date, amount in recent_divs.items():
                        dividend_info["history"].append({
                            "date": date.strftime("%Y-%m-%d"),
                            "amount": round(float(amount), 4),
                        })
                    dividend_info["payments_per_year"] = len(recent_divs)
            except Exception:
                pass

            return {
                "trailing_pe": _safe_float("trailingPE"),
                "price_to_sales": _safe_float("priceToSalesTrailing12Months"),
                "dividend_yield": _safe_float("dividendYield"),
                "debt_to_equity": _safe_float("debtToEquity"),
                "free_cashflow": _safe_float("freeCashflow"),
                "trailing_eps": _safe_float("trailingEps"),
                "forward_eps": _safe_float("forwardEps"),
                "book_value": _safe_float("bookValue"),
                "shares_outstanding": _safe_float("sharesOutstanding"),
                "earnings_timestamp": _safe_float("earningsTimestamp"),
                "revenue_growth": _safe_float("revenueGrowth"),
                "earnings_growth": _safe_float("earningsGrowth"),
                "sector": info.get("sector", "Unknown"),
                "target_mean_price": _safe_float("targetMeanPrice"),
                "target_median_price": _safe_float("targetMedianPrice"),
                "analyst_opinions": _safe_float("numberOfAnalystOpinions"),
                "recommendation": info.get("recommendationKey"),
                "dividend_info": dividend_info,
            }
        except Exception as exc:
            logger.warning("Fundamentals fetch failed for ticker=%s: %s", ticker, exc)
            raise ValueError(
                f"Ticker not found or data unavailable: '{ticker}'. Underlying error: {exc}"
            ) from exc

    def get_dividends_since(self, ticker: str, start_date: datetime) -> float:
        """Suma de dividendos desde start_date."""
        try:
            t = self._get_ticker(ticker)
            dividends = t.dividends
            if dividends is None or dividends.empty:
                return 0.0
            start_ts = pd.Timestamp(start_date)
            if dividends.index.tz is not None:
                if start_ts.tz is None:
                    start_ts = start_ts.tz_localize("UTC").tz_convert(dividends.index.tz)
                else:
                    start_ts = start_ts.tz_convert(dividends.index.tz)
            filtered = dividends[dividends.index >= start_ts]
            return round(float(filtered.sum()), 4) if not filtered.empty else 0.0
        except Exception as exc:
            logger.warning("Dividends fetch failed for ticker=%s: %s", ticker, exc)
            return 0.0

    def get_recent_news(self, ticker: str) -> list[dict[str, str | None]]:
        """Últimas noticias desde Yahoo Finance."""
        try:
            news_items = self._get_ticker(ticker).news
            if not news_items:
                return []
            articles: list[dict[str, str | None]] = []
            for item in news_items[:5]:
                articles.append({
                    "title": (item.get("content", {}) or {}).get("title"),
                    "publisher": (item.get("content", {}) or {}).get("pubDate") or item.get("publisher"),
                    "link": (item.get("content", {}) or {}).get("canonicalUrl") or item.get("link"),
                })
            return [a for a in articles if a["title"]]
        except Exception as exc:
            logger.warning("News fetch failed for ticker=%s: %s", ticker, exc)
            return []
