"""
Cliente de infraestructura para obtener datos de mercado desde Yahoo Finance (yfinance).
Programación defensiva: toda llamada externa está envuelta en try/except.
Las excepciones nativas de yfinance nunca burbujean hacia la capa de aplicación.

Si se cambia de proveedor (ej. a Alpha Vantage), solo se modifica esta clase.
"""

import logging
import time as _time
from datetime import datetime
from typing import Any
from urllib.parse import quote as _url_quote

import pandas as pd
import yfinance as yf

from app.core.config import settings

# ── Stealth Proxy para Yahoo Finance vía Cloudflare Worker ───────────
# Intercepta requests HTTP a Yahoo y las redirige por el proxy.
# Si el proxy falla o no está configurado, la request va directo a Yahoo.
# NO afecta llamadas a otras APIs (Wikipedia, DeepSeek).
_proxy_worker = (settings.CLOUDFLARE_WORKER_URL or "").strip()

if _proxy_worker:
    import requests as _requests

    _original_send = _requests.Session.send

    def _stealth_send(self, request, **kwargs):
        try:
            if "yahoo.com" in request.url:
                request.url = f"{_proxy_worker}?url={_url_quote(request.url, safe='')}"
        except Exception:
            pass
        return _original_send(self, request, **kwargs)

    _requests.Session.send = _stealth_send

logger = logging.getLogger(__name__)


class YahooFinanceClient:
    """
    Cliente para Yahoo Finance que aísla la dependencia externa.
    Si se cambia de proveedor (ej. a Alpha Vantage), solo se modifica esta clase.
    """

    def __init__(self):
        self._price_cache: dict[str, tuple[float, float]] = {}
        self._cache_ttl = 120

    def _get_ticker(self, ticker: str) -> yf.Ticker:
        return yf.Ticker(ticker)

    def get_current_price(self, ticker: str) -> float:
        """
        Obtiene el último precio de cierre usando history(period='1d').
        Con manejo defensivo de rate limiting, errores de red y soft cache 120s.
        """
        if ticker in self._price_cache:
            cached_price, cached_at = self._price_cache[ticker]
            if _time.time() - cached_at < self._cache_ttl:
                return cached_price

        try:
            df = self._get_ticker(ticker).history(period="1d")
            if df.empty:
                raise ValueError(f"Ticker not found or data unavailable: '{ticker}'")
            price = float(df["Close"].iloc[-1])
            self._price_cache[ticker] = (price, _time.time())
            return price
        except ValueError:
            raise
        except Exception as exc:
            if ticker in self._price_cache:
                logger.warning(
                    "Returning stale cached price for ticker=%s: fetch failed (%s)", ticker, exc
                )
                return self._price_cache[ticker][0]
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

    def get_target_price(self, ticker: str, current_price: float | None = None) -> float | None:
        """
        Obtiene targetMeanPrice de analistas.
        Si falla, degrada a current_price * 1.10 como estimación conservadora.
        """
        try:
            info = self._get_ticker(ticker).info
            target = info.get("targetMeanPrice")
            return float(target) if target is not None else None
        except Exception as exc:
            logger.warning("Target price failed for ticker=%s: %s", ticker, exc)
            if current_price is not None and current_price > 0:
                fallback = round(current_price * 1.10, 2)
                logger.info(
                    "Fallback target price for %s: %.2f (10%% premium over current)",
                    ticker, fallback
                )
                return fallback
            return None

    def get_beta(self, ticker: str) -> float | None:
        """Obtiene beta del ticker. Degrada a None si falla."""
        try:
            info = self._get_ticker(ticker).info
            beta = info.get("beta")
            return float(beta) if beta is not None else None
        except Exception as exc:
            logger.warning("Beta fetch failed for ticker=%s: %s", ticker, exc)
            return None

    def get_info_batch(self, ticker: str, current_price: float | None = None) -> dict[str, Any]:
        """
        Obtiene sector, target_mean_price y beta en UNA sola llamada a ticker.info.
        Reemplaza las 3 llamadas separadas (_get_sector, get_target_price, get_beta)
        que cada una creaba un Ticker nuevo y hacía su propia request HTTP a .info.

        Degradación elegante:
        - sector: "Unknown" si falla (sin cachear el fallo)
        - target_mean_price: current_price * 1.10 si current_price está disponible
        - beta: None si falla
        """
        try:
            info = self._get_ticker(ticker).info
            raw_target = info.get("targetMeanPrice")
            raw_beta = info.get("beta")
            return {
                "sector": info.get("sector") or "Unknown",
                "target_mean_price": float(raw_target) if raw_target is not None else None,
                "beta": float(raw_beta) if raw_beta is not None else None,
            }
        except Exception as exc:
            logger.warning("Info batch failed for ticker=%s: %s", ticker, exc)
            fallback_target: float | None = None
            if current_price is not None and current_price > 0:
                fallback_target = round(current_price * 1.10, 2)
                logger.info("Fallback target for %s: %.2f (10%% premium)", ticker, fallback_target)
            return {
                "sector": "Unknown",
                "target_mean_price": fallback_target,
                "beta": None,
            }

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
            return {}

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
