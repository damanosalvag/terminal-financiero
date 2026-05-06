"""
Servicio puro de análisis técnico para el Terminal Financiero.
Módulo desacoplado: recibe DataFrames, devuelve diccionarios. Sin DB ni APIs externas.

Indicadores implementados:
  - EMA 50/200, SMA 20/50, Soporte/Resistencia, ATR, RVOL, RSI 14
  - MACD (12,26,9), Stochastic (14,3,3), ADX 14, OBV, MFI 14, VWAP 20
  - 52-Week Range, Wyckoff Phase
"""

import math
from typing import Any

import pandas as pd
import numpy as np


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float | None:
    if len(df) < period + 1:
        return None
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return round(float(tr.rolling(window=period).mean().iloc[-1]), 4)


def _calculate_adx(df: pd.DataFrame, period: int = 14) -> float | None:
    """Average Directional Index (ADX) de Wilder."""
    n = len(df)
    if n < period * 2:
        return None
    high, low, close = df["high"], df["low"], df["close"]

    dm_plus = high.diff()
    dm_minus = (-low.diff())
    dm_plus = dm_plus.where(dm_plus > 0, 0.0)
    dm_minus = dm_minus.where(dm_minus > 0, 0.0)
    dm_plus = dm_plus.where(dm_plus > dm_minus, 0.0)
    dm_minus = dm_minus.where(dm_minus > dm_plus, 0.0)

    tr = _calc_tr_raw(high, low, close)
    atr_series = tr.rolling(period).mean()

    # Wilder smoothing
    sum_dm_plus = dm_plus.iloc[:period].sum()
    sum_dm_minus = dm_minus.iloc[:period].sum()
    sum_tr = tr.iloc[:period].sum()

    di_plus_list, di_minus_list = [], []
    for i in range(period, n):
        sum_dm_plus = sum_dm_plus - (sum_dm_plus / period) + float(dm_plus.iloc[i])
        sum_dm_minus = sum_dm_minus - (sum_dm_minus / period) + float(dm_minus.iloc[i])
        sum_tr = sum_tr - (sum_tr / period) + float(tr.iloc[i])
        di_p = 100 * sum_dm_plus / sum_tr if sum_tr > 0 else 0
        di_m = 100 * sum_dm_minus / sum_tr if sum_tr > 0 else 0
        di_plus_list.append(di_p)
        di_minus_list.append(di_m)

    dx_series = []
    for i in range(len(di_plus_list)):
        denom = di_plus_list[i] + di_minus_list[i]
        dx = 100 * abs(di_plus_list[i] - di_minus_list[i]) / denom if denom > 0 else 0
        dx_series.append(dx)

    initial_dx_sum = sum(dx_series[:period])
    adx_val = initial_dx_sum / period
    adx_values = []
    for i in range(period, len(dx_series)):
        adx_val = (adx_val * (period - 1) + dx_series[i]) / period
        adx_values.append(adx_val)

    return round(float(adx_values[-1]), 2) if adx_values else None


def _calc_tr_raw(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)


def _calculate_obv(df: pd.DataFrame) -> dict[str, Any] | None:
    """On-Balance Volume: acumula volumen basado en dirección del precio."""
    n = len(df)
    if n < 2:
        return None
    close = df["close"]
    volume = df["volume"]
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (direction * volume).cumsum()

    # Tendencia de OBV en los últimos 20 días
    if n >= 21:
        obv_recent = obv.iloc[-20:].tolist()
        obv_trend = "Accumulating" if obv.iloc[-1] > obv.iloc[-20] else "Distributing"
    else:
        obv_trend = "Insufficient data"

    return {
        "value": round(float(obv.iloc[-1]), 0),
        "trend": obv_trend,
    }


def _calculate_mfi(df: pd.DataFrame, period: int = 14) -> float | None:
    """Money Flow Index: RSI ponderado por volumen."""
    n = len(df)
    if n < period + 1:
        return None
    high, low, close, volume = df["high"], df["low"], df["close"], df["volume"]
    typical_price = (high + low + close) / 3
    raw_money_flow = typical_price * volume

    pos_flow, neg_flow = pd.Series(0.0, index=df.index), pd.Series(0.0, index=df.index)
    tp_diff = typical_price.diff()
    pos_flow[tp_diff > 0] = raw_money_flow[tp_diff > 0]
    neg_flow[tp_diff < 0] = raw_money_flow[tp_diff < 0]

    pos_mf = pos_flow.rolling(window=period).sum()
    neg_mf = neg_flow.rolling(window=period).sum()

    mfr = pos_mf / neg_mf.replace(0, np.nan)
    mfi = 100 - (100 / (1 + mfr))
    return round(float(mfi.iloc[-1]), 2) if not pd.isna(mfi.iloc[-1]) else None


def _calculate_vwap(df: pd.DataFrame, period: int = 20) -> float | None:
    """Volume Weighted Average Price (20 períodos)."""
    n = len(df)
    if n < period:
        return None
    window = df.iloc[-period:]
    typical_price = (window["high"] + window["low"] + window["close"]) / 3
    vwap = (typical_price * window["volume"]).sum() / window["volume"].sum()
    return round(float(vwap), 2)


def _calculate_stochastic(df: pd.DataFrame, k_period: int = 14, k_smooth: int = 3, d_smooth: int = 3) -> dict[str, float | None]:
    """Stochastic Oscillator: %K y %D."""
    n = len(df)
    if n < k_period:
        return {"percent_k": None, "percent_d": None}
    high, low, close = df["high"], df["low"], df["close"]
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()

    percent_k_raw = ((close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)) * 100
    percent_k = percent_k_raw.rolling(window=k_smooth).mean()
    percent_d = percent_k.rolling(window=d_smooth).mean()

    return {
        "percent_k": round(float(percent_k.iloc[-1]), 2) if not pd.isna(percent_k.iloc[-1]) else None,
        "percent_d": round(float(percent_d.iloc[-1]), 2) if not pd.isna(percent_d.iloc[-1]) else None,
    }


def analyze_price_action(df: pd.DataFrame) -> dict[str, Any]:
    if len(df) < 50:
        return _insufficient_response()

    current_close = float(df["close"].iloc[-1])
    recent_20 = df["close"].iloc[-20:]

    # ── Básicos ──────────────────────────────────────
    support = round(float(recent_20.min()), 2)
    resistance = round(float(recent_20.max()), 2)
    sma_20 = df["close"].rolling(window=20).mean()
    sma_50 = df["close"].rolling(window=50).mean()
    latest_sma20 = round(float(sma_20.iloc[-1]), 2)
    latest_sma50 = round(float(sma_50.iloc[-1]), 2)
    ema_50_series = _ema(df["close"], 50)
    latest_ema50 = round(float(ema_50_series.iloc[-1]), 2)
    ema_200_avail = len(df) >= 200
    latest_ema200 = round(float(_ema(df["close"], 200).iloc[-1]), 2) if ema_200_avail else None
    trend = "Bullish" if latest_sma20 > latest_sma50 else "Bearish"

    # ── Wyckoff ──────────────────────────────────────
    near_support = abs(current_close - support) / support < 0.03 if support > 0 else False
    near_resistance = abs(resistance - current_close) / resistance < 0.03 if resistance > 0 else False
    if trend == "Bearish" and near_support:
        wyckoff = "Accumulation"
    elif trend == "Bullish" and near_resistance:
        wyckoff = "Distribution"
    elif trend == "Bullish":
        wyckoff = "Markup"
    else:
        wyckoff = "Markdown"

    # ── ATR / RVOL / RSI ─────────────────────────────
    atr = _calculate_atr(df)
    avg_vol_20 = float(df["volume"].iloc[-21:-1].mean()) if len(df) >= 21 else None
    curr_vol = float(df["volume"].iloc[-1])
    rvol = round(curr_vol / avg_vol_20, 2) if avg_vol_20 and avg_vol_20 > 0 else None
    from app.services.finance_math import calculate_rsi
    current_rsi = calculate_rsi([float(p) for p in df["close"].tolist()])

    # ── Checklist base ───────────────────────────────
    above_ema50 = current_close > latest_ema50
    above_ema200 = (current_close > latest_ema200) if latest_ema200 is not None else None
    rsi_in_range = (40 <= current_rsi <= 65) if current_rsi is not None else None
    rvol_strong = (rvol >= 1.3) if rvol is not None else None
    atr_ok = (atr / current_close < 0.08) if atr and current_close > 0 else None

    # ── 52-Week Range ────────────────────────────────
    if len(df) >= 250:
        high_52w = round(float(df["high"].iloc[-252:].max()), 2)
        low_52w = round(float(df["low"].iloc[-252:].min()), 2)
        pct_52w = round(((current_close - low_52w) / (high_52w - low_52w)) * 100, 1) if (high_52w - low_52w) > 0 else None
    else:
        high_52w, low_52w, pct_52w = None, None, None

    # ── MACD (12,26,9) ───────────────────────────────
    ema12 = _ema(df["close"], 12)
    ema26 = _ema(df["close"], 26)
    macd_line = ema12 - ema26
    signal_line = _ema(macd_line, 9)
    macd_hist = macd_line - signal_line
    macd_signal = "Bullish" if float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]) else "Bearish"
    macd_data = {
        "macd": round(float(macd_line.iloc[-1]), 4),
        "signal": round(float(signal_line.iloc[-1]), 4),
        "histogram": round(float(macd_hist.iloc[-1]), 4),
        "signal_cross": macd_signal,
    }

    # ── Stochastic (14,3,3) ──────────────────────────
    stoch = _calculate_stochastic(df, 14, 3, 3)

    # ── ADX (14) ─────────────────────────────────────
    adx = _calculate_adx(df, 14)

    # ── OBV ──────────────────────────────────────────
    obv = _calculate_obv(df)

    # ── MFI (14) ─────────────────────────────────────
    mfi = _calculate_mfi(df, 14)

    # ── VWAP (20) ────────────────────────────────────
    vwap = _calculate_vwap(df, 20)

    return {
        "support": support,
        "resistance": resistance,
        "trend": trend,
        "wyckoff_phase": wyckoff,
        "sma_20": latest_sma20,
        "sma_50": latest_sma50,
        "ema_50": latest_ema50,
        "ema_200": latest_ema200,
        "current_close": round(current_close, 2),
        "atr": atr,
        "rvol": rvol,
        "current_rsi": current_rsi,
        "checklist": {
            "above_ema50": above_ema50,
            "above_ema200": above_ema200,
            "rsi_in_range": rsi_in_range,
            "rvol_strong": rvol_strong,
            "atr_ok": atr_ok,
        },
        "high_52w": high_52w,
        "low_52w": low_52w,
        "pct_52w": pct_52w,
        "macd": macd_data,
        "stochastic": stoch,
        "adx": adx,
        "obv": obv,
        "mfi": mfi,
        "vwap": vwap,
    }


def _insufficient_response() -> dict[str, Any]:
    return {
        "support": None, "resistance": None, "trend": "Insufficient data",
        "wyckoff_phase": "Unknown", "sma_20": None, "sma_50": None,
        "ema_50": None, "ema_200": None, "current_close": None,
        "atr": None, "rvol": None, "current_rsi": None,
        "checklist": {"above_ema50": None, "above_ema200": None, "rsi_in_range": None, "rvol_strong": None, "atr_ok": None},
        "high_52w": None, "low_52w": None, "pct_52w": None,
        "macd": None, "stochastic": None, "adx": None, "obv": None, "mfi": None, "vwap": None,
    }
