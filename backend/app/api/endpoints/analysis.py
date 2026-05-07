"""
Rutas del módulo de Análisis / Asset Cockpit.
Provee datos para gráficos de velas, análisis técnico y fundamental de activos individuales.
"""

import io
import logging
import math
from datetime import datetime, timezone

import pandas as pd
import requests
import yfinance as yf
from fastapi import APIRouter, HTTPException, Query

from app.infrastructure.market_data import YahooFinanceClient
from app.services.finance_math import (
    calculate_graham_number,
    calculate_historical_multiple_value,
    calculate_simple_dcf,
)
from app.services.technical_analysis import analyze_price_action

try:
    from app.services.llm_advisor import get_strategic_intel
except ImportError:
    get_strategic_intel = None  # type: ignore[assignment]

router = APIRouter(prefix="/analysis", tags=["Analysis"])

market_client = YahooFinanceClient()

_DAYS_EARNINGS_WARNING = 7


@router.get("/{ticker}/chart")
def get_chart_data(ticker: str):
    """
    Devuelve datos OHLCV históricos (1 año) y análisis técnico con checklist de swing trading.
    Se usa 1 año de datos para calcular correctamente la EMA 200.
    """
    try:
        candles = market_client.get_ohlcv_data(ticker, period="1y")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    df = pd.DataFrame(candles)
    insights = analyze_price_action(df)

    # Para el gráfico mostramos solo los últimos 6 meses (≈126 velas hábiles)
    chart_candles = candles[-126:] if len(candles) > 126 else candles

    return {
        "chart_data": chart_candles,
        "technical_insights": insights,
    }


@router.get("/{ticker}/fundamentals")
def get_fundamentals(ticker: str):
    """
    Devuelve ratios fundamentales, intrinsic values y checklist fundamental de swing trading.
    """
    try:
        fundamentals = market_client.get_fundamentals(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    eps = fundamentals.get("trailing_eps")
    bvps = fundamentals.get("book_value")
    fcf = fundamentals.get("free_cashflow")
    shares = fundamentals.get("shares_outstanding")

    fcf_per_share: float | None = None
    if fcf is not None and shares is not None and shares > 0:
        fcf_per_share = round(fcf / shares, 4)

    fundamentals["fcf_per_share"] = fcf_per_share

    # Clasificación sectorial para seleccionar modelos de valoración aplicables
    sector = fundamentals.get("sector", "Unknown")
    if sector in ("Technology", "Healthcare", "Communication Services"):
        # Intangibles/crecimiento: Book Value es insignificante, Graham no aplica
        applicable_models = ["simple_dcf", "historical_multiple_value"]
    elif sector == "Financial Services":
        # Flujo de caja distorsionado por depósitos, DCF no aplica
        applicable_models = ["graham_number", "historical_multiple_value"]
    elif sector in (
        "Energy", "Basic Materials", "Industrials", "Utilities",
        "Consumer Defensive", "Consumer Cyclical", "Real Estate",
    ):
        # Tangibles/asset-heavy: todos los modelos aplican
        applicable_models = ["graham_number", "simple_dcf", "historical_multiple_value"]
    else:
        # Fallback: desconocido, devolver los tres
        applicable_models = ["graham_number", "simple_dcf", "historical_multiple_value"]

    intrinsic_values = {
        "graham_number": calculate_graham_number(eps, bvps),
        "simple_dcf": calculate_simple_dcf(fcf_per_share),
        "historical_multiple_value": calculate_historical_multiple_value(eps),
    }

    # Checklist fundamental de swing trading
    earnings_growth = fundamentals.get("earnings_growth")
    debt_to_equity = fundamentals.get("debt_to_equity")
    earnings_ts = fundamentals.get("earnings_timestamp")

    eps_growing = (earnings_growth is not None and earnings_growth > 0.10) if earnings_growth is not None else None
    fcf_positive = (fcf is not None and fcf > 0) if fcf is not None else None
    debt_ok = (debt_to_equity is not None and debt_to_equity < 150.0) if debt_to_equity is not None else None

    # Earnings próximos: si el timestamp es en los próximos 7 días
    no_earnings_soon: bool | None = None
    earnings_days_away: int | None = None
    if earnings_ts is not None:
        now_ts = datetime.now(timezone.utc).timestamp()
        days_diff = (earnings_ts - now_ts) / 86400
        earnings_days_away = int(days_diff)
        no_earnings_soon = days_diff < 0 or days_diff > _DAYS_EARNINGS_WARNING

    fundamental_checklist = {
        "eps_growing_10pct": eps_growing,
        "fcf_positive": fcf_positive,
        "debt_ok": debt_ok,
        "no_earnings_soon": no_earnings_soon,
        "earnings_days_away": earnings_days_away,
        "earnings_growth_pct": round(earnings_growth * 100, 1) if earnings_growth is not None else None,
        "debt_to_equity_pct": debt_to_equity,
    }

    return {
        "ratios": fundamentals,
        "intrinsic_values": intrinsic_values,
        "fundamental_checklist": fundamental_checklist,
        "applicable_models": applicable_models,
        "sector": sector,
        "analyst_consensus": {
            "target_mean_price": fundamentals.get("target_mean_price"),
            "target_median_price": fundamentals.get("target_median_price"),
            "analyst_opinions": fundamentals.get("analyst_opinions"),
            "recommendation": fundamentals.get("recommendation"),
        },
    }


@router.get("/{ticker}/narrative")
def get_narrative(ticker: str):
    """
    Genera inteligencia estratégica usando DeepSeek IA.
    Combina noticias recientes con análisis de negocio, competidores,
    cadena de suministro y factores macroeconómicos.

    Requiere la variable de entorno DEEPSEEK_API_KEY configurada.
    """
    if get_strategic_intel is None:
        raise HTTPException(
            status_code=503,
            detail="LLM advisor not available. Install openai and configure DEEPSEEK_API_KEY.",
        )

    news = market_client.get_recent_news(ticker)

    try:
        result = get_strategic_intel(ticker, news)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DeepSeek API error: {exc}") from exc


@router.get("/market-heatmap")
def get_market_heatmap(
    market: str = Query("sp500", description="Market: sp500, dow, nasdaq, russell"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(100, ge=10, le=200, description="Max tickers per request"),
):
    """
    Heatmap multi-mercado con paginación. Soportado: S&P 500, Dow 30, Nasdaq-100, Russell.
    """
    logger = logging.getLogger(__name__)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    _RUSSELL_TICKERS = [
        "SMCI", "CROX", "ELF", "CVNA", "CHWY", "FIX", "XPO", "AIT", "SSB", "HQY",
        "WWD", "RMBS", "NOVT", "QLYS", "BMI", "ENSG", "FN", "SPSC", "EXPO", "LSTR",
        "MTH", "TMHC", "KBH", "ITGR", "BCPC", "NEO", "POWI", "SLAB", "SYNA", "DIOD",
        "MXL", "MRVL", "CRUS", "SMTC", "IDCC", "VECO", "ACLS", "FORM", "UCTT", "ICHR",
        "APOG", "AEIS", "PLXS", "BHE", "JBL", "FLEX", "SANM", "CLS", "PLUS", "ARW",
    ]

    try:
        if market == "sp500":
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            col = "GICS Sector"
        elif market == "dow":
            url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
            col = None
        elif market == "nasdaq":
            url = "https://en.wikipedia.org/wiki/Nasdaq-100"
            col = None
        elif market == "russell":
            tickers = _RUSSELL_TICKERS
            sector_map = {t: "Russell 2000" for t in tickers}
            total = len(tickers)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown market: {market}")

        if market != "russell":
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            html_io = io.StringIO(resp.text)
            tables = pd.read_html(html_io)

            # Buscar la tabla correcta: la que tenga columna 'Symbol' o 'Ticker'
            table = None
            for t in tables:
                cols = [str(c) for c in t.columns]
                if "Symbol" in cols or "Ticker" in cols:
                    table = t
                    break
            if table is None:
                raise HTTPException(status_code=500, detail="Could not find ticker table on Wikipedia page")

            ticker_col = "Symbol" if "Symbol" in table.columns else "Ticker"
            sector_col = next((col for col in table.columns if col in ("GICS Sector", "Sector", "Industry")), None)

            symbols = table[ticker_col].tolist()
            symbols = [str(s).replace(".", "-") for s in symbols]
            total = len(symbols)
            sector_map = {
                s: str(table.iloc[i][sector_col]) if sector_col and i < len(table) else market.upper()
                for i, s in enumerate(symbols)
            }
            tickers = symbols

        # Aplicar paginación
        paginated = tickers[offset : offset + limit]
        current_offset = offset

        if not paginated:
            return {"total_assets": total, "current_offset": current_offset, "sectors": []}

        df = yf.download(tickers=" ".join(paginated), period="5d", progress=False, auto_adjust=True)

        if not isinstance(df.columns, pd.MultiIndex):
            raise HTTPException(status_code=500, detail="Unexpected data format from Yahoo Finance")

        close_df = df["Close"].copy()
        close_df.dropna(axis=1, thresh=2, inplace=True)
        if close_df.empty or close_df.shape[0] < 2 or close_df.shape[1] == 0:
            return {"total_assets": total, "current_offset": current_offset, "sectors": []}

        last_row = close_df.iloc[-1]
        prev_row = close_df.iloc[-2]
        pct_series = ((last_row - prev_row) / prev_row.replace(0, float("nan"))) * 100
        pct_series = pct_series.replace([float("inf"), float("-inf")], float("nan")).dropna()

        sectors: dict[str, list[dict]] = {}
        for ticker in pct_series.index:
            val = float(pct_series[ticker])
            if not math.isfinite(val):
                continue
            change_pct = round(val, 2)
            sector = sector_map.get(ticker, "Unknown")
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append({"ticker": ticker, "change_pct": change_pct})

        result = []
        for sector, assets in sectors.items():
            assets.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
            result.append({"sector": sector, "assets": assets[:15]})

        result.sort(key=lambda x: x["sector"])
        return {"total_assets": total, "current_offset": current_offset, "sectors": result}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Market heatmap error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
