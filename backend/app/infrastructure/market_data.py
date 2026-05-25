"""
Cliente de infraestructura para obtener datos de mercado desde Yahoo Finance (yfinance).
Programación defensiva: toda llamada externa está envuelta en try/except.
Las excepciones nativas de yfinance nunca burbujean hacia la capa de aplicación.

Si se cambia de proveedor (ej. a Alpha Vantage), solo se modifica esta clase.

ARQUITECTURA:
- `YahooFinanceClient` es una clase singleton (vía `market_client` al final del módulo).
- Caches a nivel de instancia (que al ser singleton, son efectivamente process-global):
    * _price_cache:    TTL 120s — precio intradía vivo
    * _info_cache:     TTL 6h    — sector/target/beta (cambian raramente)
    * _ohlcv_cache:    TTL 600s  — series históricas (1y / 6mo)
    * _dividends_cache:TTL 6h    — dividendos por (ticker, start_date)
- Lock `threading.Lock()` para acceso seguro desde ThreadPoolExecutor.
"""

import logging
import threading
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
    Pensado para ser usado como singleton (instancia única en `market_client`).
    Comparte caches entre todos los endpoints.
    """

    # TTLs en segundos
    _PRICE_TTL: int = 120        # precio vivo: 2 minutos
    _INFO_TTL: int = 6 * 3600    # sector/target/beta: 6 horas
    _OHLCV_TTL: int = 600        # series históricas: 10 minutos
    _DIVIDENDS_TTL: int = 6 * 3600  # dividendos: 6 horas

    def __init__(self) -> None:
        self._price_cache: dict[str, tuple[float, float]] = {}
        self._info_cache: dict[str, tuple[dict[str, Any], float]] = {}
        self._ohlcv_cache: dict[tuple[str, str], tuple[list[float], float]] = {}
        self._dividends_cache: dict[tuple[str, str], tuple[float, float]] = {}
        self._lock = threading.Lock()

    def _get_ticker(self, ticker: str) -> yf.Ticker:
        return yf.Ticker(ticker)

    # ── Precio intradía ─────────────────────────────────────────────
    def get_current_price(self, ticker: str) -> float:
        """
        Obtiene el último precio de cierre usando history(period='1d').
        Soft cache 120s. Fallback a caché expirado si la API falla (mejor stale que crash).
        """
        with self._lock:
            cached = self._price_cache.get(ticker)
        if cached is not None and _time.time() - cached[1] < self._PRICE_TTL:
            return cached[0]

        try:
            df = self._get_ticker(ticker).history(period="1d")
            if df.empty:
                raise ValueError(f"Ticker not found or data unavailable: '{ticker}'")
            price = float(df["Close"].iloc[-1])
            with self._lock:
                self._price_cache[ticker] = (price, _time.time())
            return price
        except ValueError:
            raise
        except Exception as exc:
            if cached is not None:
                logger.warning(
                    "Returning stale cached price for ticker=%s: fetch failed (%s)", ticker, exc
                )
                return cached[0]
            logger.warning("Market data fetch failed for ticker=%s: %s", ticker, exc)
            raise ValueError(
                f"Ticker not found or data unavailable: '{ticker}'. Underlying error: {exc}"
            ) from exc

    def prime_price(self, ticker: str, price: float) -> None:
        """
        Inyecta un precio en el cache (sin hacer request). Útil después de un
        batch download para evitar que el siguiente get_current_price() haga otra
        llamada redundante.
        """
        with self._lock:
            self._price_cache[ticker] = (price, _time.time())

    # ── Series históricas ───────────────────────────────────────────
    def get_historical_prices(self, ticker: str, period: str = "1y") -> list[float]:
        """Obtiene precios de cierre históricos para indicadores técnicos. Cache 10min."""
        key = (ticker, period)
        with self._lock:
            cached = self._ohlcv_cache.get(key)
        if cached is not None and _time.time() - cached[1] < self._OHLCV_TTL:
            return cached[0]

        try:
            df = self._get_ticker(ticker).history(period=period)
            if df.empty or "Close" not in df.columns:
                raise ValueError(f"Ticker not found or data unavailable: '{ticker}'")
            closes = [float(v) for v in df["Close"].tolist()]
            with self._lock:
                self._ohlcv_cache[key] = (closes, _time.time())
            return closes
        except ValueError:
            raise
        except Exception as exc:
            if cached is not None:
                logger.warning(
                    "Returning stale cached history for ticker=%s period=%s (fetch failed: %s)",
                    ticker, period, exc,
                )
                return cached[0]
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

    # ── Batch OHLCV (la gran optimización del portfolio_summary) ────
    def download_batch_history(
        self, tickers: list[str], period: str = "1y"
    ) -> dict[str, list[float]]:
        """
        Descarga history(period=...) de N tickers en UNA sola request batch.
        Reemplaza N llamadas individuales por 1 sola — patrón ya usado en heatmap/screener.

        Retorna {ticker: list[float] de cierres diarios}.
        Cachea cada serie individual también en _ohlcv_cache para hits subsecuentes.

        Para tickers que ya estén frescos en cache, los devuelve sin descargar.
        Solo descarga los que falten o estén expirados.
        """
        if not tickers:
            return {}

        # Separar tickers cacheados frescos de los que requieren descarga
        now = _time.time()
        cached_fresh: dict[str, list[float]] = {}
        to_fetch: list[str] = []
        with self._lock:
            for t in tickers:
                entry = self._ohlcv_cache.get((t, period))
                if entry is not None and now - entry[1] < self._OHLCV_TTL:
                    cached_fresh[t] = entry[0]
                else:
                    to_fetch.append(t)

        # Si todos están cacheados, no hacemos request
        if not to_fetch:
            return cached_fresh

        result: dict[str, list[float]] = dict(cached_fresh)
        try:
            # yf.download con espacios separa tickers. group_by='ticker' simplifica el acceso.
            raw = yf.download(
                tickers=" ".join(to_fetch),
                period=period,
                progress=False,
                auto_adjust=True,
                threads=False,  # threads=True causa rate-limit más agresivo en Render
                group_by="ticker" if len(to_fetch) > 1 else "column",
            )
            if raw is None or raw.empty:
                logger.warning("Batch download returned empty for tickers=%s", to_fetch)
                return result

            # Caso multi-ticker: MultiIndex columns (ticker, field)
            if isinstance(raw.columns, pd.MultiIndex):
                for t in to_fetch:
                    if t not in raw.columns.get_level_values(0):
                        continue
                    try:
                        series = raw[t]["Close"].dropna()
                        if not series.empty:
                            closes = [float(v) for v in series.tolist()]
                            result[t] = closes
                            with self._lock:
                                self._ohlcv_cache[(t, period)] = (closes, now)
                    except Exception as inner_exc:
                        logger.debug("Could not extract %s from batch: %s", t, inner_exc)
            else:
                # Caso single-ticker: columnas planas
                if "Close" in raw.columns and to_fetch:
                    series = raw["Close"].dropna()
                    if not series.empty:
                        closes = [float(v) for v in series.tolist()]
                        t = to_fetch[0]
                        result[t] = closes
                        with self._lock:
                            self._ohlcv_cache[(t, period)] = (closes, now)
        except Exception as exc:
            logger.warning("Batch history download failed: %s", exc)
            # Para los tickers que NO se pudieron descargar pero tienen caché expirado,
            # devolver el stale en vez de nada.
            with self._lock:
                for t in to_fetch:
                    if t not in result:
                        stale = self._ohlcv_cache.get((t, period))
                        if stale is not None:
                            result[t] = stale[0]

        return result

    # ── Info batch (sector + target + beta) ─────────────────────────
    def get_info_batch(self, ticker: str, current_price: float | None = None) -> dict[str, Any]:
        """
        Obtiene sector, target_mean_price y beta en UNA sola llamada a ticker.info.
        Cache TTL 6h (estos campos cambian raramente).

        Degradación elegante:
        - sector: "Unknown" si falla (no se cachea fallo)
        - target_mean_price: current_price * 1.10 si current_price está disponible
        - beta: None si falla
        """
        with self._lock:
            cached = self._info_cache.get(ticker)
        if cached is not None and _time.time() - cached[1] < self._INFO_TTL:
            # Si el target cacheado quedó como None y ahora tenemos current_price,
            # podemos usar el fallback sin invalidar el resto del cache.
            entry = cached[0]
            if entry.get("target_mean_price") is None and current_price is not None and current_price > 0:
                return {
                    **entry,
                    "target_mean_price": round(current_price * 1.10, 2),
                }
            return entry

        try:
            info = self._get_ticker(ticker).info
            raw_target = info.get("targetMeanPrice")
            raw_beta = info.get("beta")
            result = {
                "sector": info.get("sector") or "Unknown",
                "target_mean_price": float(raw_target) if raw_target is not None else None,
                "beta": float(raw_beta) if raw_beta is not None else None,
            }
            # Solo cachear si obtuvimos un sector válido (evita poisoning con "Unknown")
            if result["sector"] != "Unknown":
                with self._lock:
                    self._info_cache[ticker] = (result, _time.time())
            # Aplicar fallback de target si quedó None
            if result["target_mean_price"] is None and current_price is not None and current_price > 0:
                result["target_mean_price"] = round(current_price * 1.10, 2)
            return result
        except Exception as exc:
            logger.warning("Info batch failed for ticker=%s: %s", ticker, exc)
            # Si hay stale en cache, devolverlo
            if cached is not None:
                stale = cached[0]
                logger.info("Returning stale info_batch for %s", ticker)
                if stale.get("target_mean_price") is None and current_price is not None and current_price > 0:
                    return {**stale, "target_mean_price": round(current_price * 1.10, 2)}
                return stale
            fallback_target: float | None = None
            if current_price is not None and current_price > 0:
                fallback_target = round(current_price * 1.10, 2)
                logger.info("Fallback target for %s: %.2f (10%% premium)", ticker, fallback_target)
            return {
                "sector": "Unknown",
                "target_mean_price": fallback_target,
                "beta": None,
            }

    # ── Fundamentals completos (para asset cockpit) ─────────────────
    def get_fundamentals(self, ticker: str) -> dict[str, Any]:
        """Obtiene ratios fundamentales completos desde Yahoo Finance."""
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

            # Oportunisticamente, poblar también _info_cache (mismo .info)
            sector_raw = info.get("sector") or "Unknown"
            if sector_raw != "Unknown":
                raw_target = info.get("targetMeanPrice")
                raw_beta = info.get("beta")
                with self._lock:
                    self._info_cache[ticker] = (
                        {
                            "sector": sector_raw,
                            "target_mean_price": float(raw_target) if raw_target is not None else None,
                            "beta": float(raw_beta) if raw_beta is not None else None,
                        },
                        _time.time(),
                    )

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
                "sector": sector_raw,
                "target_mean_price": _safe_float("targetMeanPrice"),
                "target_median_price": _safe_float("targetMedianPrice"),
                "analyst_opinions": _safe_float("numberOfAnalystOpinions"),
                "recommendation": info.get("recommendationKey"),
                "dividend_info": dividend_info,
            }
        except Exception as exc:
            logger.warning("Fundamentals fetch failed for ticker=%s: %s", ticker, exc)
            return {}

    # ── Dividendos ──────────────────────────────────────────────────
    def get_dividends_since(self, ticker: str, start_date: datetime) -> float:
        """Suma de dividendos desde start_date. Cache 6h (los dividendos pasados son inmutables)."""
        key = (ticker, start_date.isoformat())
        with self._lock:
            cached = self._dividends_cache.get(key)
        if cached is not None and _time.time() - cached[1] < self._DIVIDENDS_TTL:
            return cached[0]

        try:
            t = self._get_ticker(ticker)
            dividends = t.dividends
            if dividends is None or dividends.empty:
                with self._lock:
                    self._dividends_cache[key] = (0.0, _time.time())
                return 0.0
            start_ts = pd.Timestamp(start_date)
            if dividends.index.tz is not None:
                if start_ts.tz is None:
                    start_ts = start_ts.tz_localize("UTC").tz_convert(dividends.index.tz)
                else:
                    start_ts = start_ts.tz_convert(dividends.index.tz)
            filtered = dividends[dividends.index >= start_ts]
            total = round(float(filtered.sum()), 4) if not filtered.empty else 0.0
            with self._lock:
                self._dividends_cache[key] = (total, _time.time())
            return total
        except Exception as exc:
            logger.warning("Dividends fetch failed for ticker=%s: %s", ticker, exc)
            if cached is not None:
                return cached[0]
            return 0.0

    # ── Noticias ────────────────────────────────────────────────────
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


# ── Singleton compartido ─────────────────────────────────────────────
# Una sola instancia para todo el proceso. Endpoints comparten todos los caches.
market_client = YahooFinanceClient()
