"""
Servicio puro de matemática financiera para el Terminal Financiero.
Módulo estrictamente desacoplado: sin imports de SQLAlchemy, modelos ni base de datos.

Principios:
  - Interés compuesto diario (daily compounding).
  - Ajuste por erosión inflacionaria sobre la base de costo.
  - Deducción de dividendos acumulados para reflejar retorno real.
  - Indicadores técnicos (RSI) calculados con pandas rolling.
"""

from datetime import datetime

import numpy as np
import pandas as pd
from scipy.stats import norm


def calculate_days_held(buy_date: datetime, current_date: datetime) -> int:
    """
    Calcula el número absoluto de días transcurridos entre la compra y la fecha actual.

    Se fuerza un mínimo de 1 día para evitar divisiones por cero en las fórmulas
    de interés compuesto cuando el cálculo se ejecuta el mismo día de la compra.

    Args:
        buy_date: Fecha de adquisición de la posición.
        current_date: Fecha de referencia (típicamente hoy).

    Returns:
        Días transcurridos, con un mínimo de 1.
    """
    # Ambos argumentos pueden venir con o sin timezone (DB devuelve naive,
    # datetime.now(timezone.utc) devuelve aware). Se elimina tzinfo para que
    # la resta sea segura independientemente del origen de cada fecha.
    naive_buy = buy_date.replace(tzinfo=None)
    naive_current = current_date.replace(tzinfo=None)
    # Días calendario: diferencia entre fechas sin contar horas parciales.
    # Si la compra fue ayer (cualquier hora) y hoy es otro día del calendario → 1 día.
    calendar_days = (naive_current.date() - naive_buy.date()).days
    return max(calendar_days, 1)


def calculate_target_exit_price(
    buy_price: float,
    commission: float,
    target_annual_yield: float,
    days_held: int,
    estimated_inflation: float,
    dividends_collected: float = 0.0,
) -> float:
    """
    Calcula el precio de salida exacto requerido HOY para alcanzar el objetivo de
    rentabilidad anual efectiva (target_annual_yield).

    Fórmula aplicada (interés compuesto diario):
      1. base_cost = buy_price + commission
      2. growth = base_cost * (1 + target_annual_yield/100) ** (days_held / 365)
      3. inflation_erosion = base_cost * ((1 + estimated_inflation/100) ** (days_held/365) - 1)
      4. target_exit_price = growth + inflation_erosion - dividends_collected

    La erosión inflacionaria se SUMA al objetivo porque el precio debe compensar
    la pérdida de poder adquisitivo. Los dividendos ya cobrados se RESTAN porque
    reducen el precio de salida necesario para alcanzar la meta.

    Args:
        buy_price: Precio unitario de compra del título.
        commission: Comisión pagada por título en la operación.
        target_annual_yield: Rentabilidad anual objetivo en % (ej. 100.0 = duplicar).
        days_held: Días transcurridos desde la compra.
        estimated_inflation: Inflación anual estimada en %.
        dividends_collected: Dividendos acumulados por título hasta la fecha.

    Returns:
        Precio de salida objetivo por título, redondeado a 4 decimales.
    """
    base_cost = buy_price + commission
    t_years = days_held / 365.0

    # Crecimiento compuesto requerido para alcanzar el objetivo de rentabilidad
    growth = base_cost * (1.0 + target_annual_yield / 100.0) ** t_years

    # Erosión inflacionaria: cuánto valor adicional se necesita para preservar poder adquisitivo
    inflation_erosion = base_cost * ((1.0 + estimated_inflation / 100.0) ** t_years - 1.0)

    target_exit = growth + inflation_erosion - dividends_collected
    return round(max(target_exit, 0.0), 4)


def calculate_current_utility_percentage(
    buy_price: float,
    current_price: float,
    commission: float,
    estimated_inflation: float,
    days_held: int,
    dividends_collected: float = 0.0,
) -> float:
    """
    Calcula el porcentaje de utilidad real neta al día de hoy, descontando todos
    los costos, el impacto inflacionario acumulado y sumando los dividendos recibidos.

    Fórmula:
      1. total_cost = buy_price + commission
      2. current_value = current_price + dividends_collected
      3. inflation_erosion = total_cost * ((1 + estimated_inflation/100) ** (days_held/365) - 1)
      4. net_return = current_value - total_cost - inflation_erosion
      5. utility_pct = (net_return / total_cost) * 100

    Si la utilidad neta es negativa después del ajuste inflacionario, significa que
    la posición está perdiendo valor real (no solo nominal).

    Args:
        buy_price: Precio unitario de compra del título.
        current_price: Precio de mercado actual del título.
        commission: Comisión pagada por título en la operación.
        estimated_inflation: Inflación anual estimada en %.
        days_held: Días transcurridos desde la compra.
        dividends_collected: Dividendos acumulados por título hasta la fecha.

    Returns:
        Porcentaje de utilidad real neta, redondeado a 2 decimales.
    """
    total_cost = buy_price + commission
    current_value = current_price + dividends_collected

    t_years = days_held / 365.0

    # Ajuste inflacionario: lo que la inversión debió crecer solo para no perder poder adquisitivo
    inflation_erosion = total_cost * ((1.0 + estimated_inflation / 100.0) ** t_years - 1.0)

    net_return = current_value - total_cost - inflation_erosion

    if total_cost == 0.0:
        return 0.0

    utility_pct = (net_return / total_cost) * 100.0
    return round(utility_pct, 2)


def calculate_rsi(closing_prices: list[float], period: int = 14) -> float | None:
    """
    Calcula el Relative Strength Index (RSI) usando el método de Wilder.

    El RSI mide la velocidad y magnitud de los cambios de precio. Un valor > 70
    sugiere sobrecompra, < 30 sugiere sobreventa.

    Se requiere al menos (period + 1) precios para calcular el indicador.
    Si no hay suficientes datos, retorna None.

    Args:
        closing_prices: Lista de precios de cierre en orden cronológico.
        period: Período del RSI (default 14).

    Returns:
        Valor del RSI entre 0 y 100, o None si no hay suficientes datos.
    """
    if len(closing_prices) < period + 1:
        return None

    df = pd.DataFrame({"close": closing_prices})
    df["delta"] = df["close"].diff()
    df["gain"] = df["delta"].clip(lower=0)
    df["loss"] = (-df["delta"]).clip(lower=0)

    # Promedio inicial simple de las primeras 'period' observaciones (excluyendo la primera diff que es NaN)
    avg_gain = float(df["gain"].iloc[1 : period + 1].mean())
    avg_loss = float(df["loss"].iloc[1 : period + 1].mean())

    rsi_values: list[float] = []

    # Calcular RSI para cada punto posterior usando suavizado de Wilder
    for i in range(period + 1, len(df)):
        current_gain = float(df["gain"].iloc[i])
        current_loss = float(df["loss"].iloc[i])
        avg_gain = (avg_gain * (period - 1) + current_gain) / period
        avg_loss = (avg_loss * (period - 1) + current_loss) / period

        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        rsi_values.append(rsi)

    # Retornar el último valor de RSI calculado
    return round(rsi_values[-1], 2) if rsi_values else None


def calculate_graham_number(eps: float | None, bvps: float | None) -> float | None:
    """
    Calcula el Número de Graham: sqrt(22.5 × EPS × BVPS).
    Fórmula clásica de Benjamin Graham para estimar el valor intrínseco máximo
    que un inversor defensivo debería pagar por una acción.

    Args:
        eps: Earnings Per Share (trailing).
        bvps: Book Value Per Share.

    Returns:
        Número de Graham redondeado a 2 decimales, o None si los datos son inválidos.
    """
    if eps is None or bvps is None or eps <= 0 or bvps <= 0:
        return None
    return round((22.5 * eps * bvps) ** 0.5, 2)


def calculate_simple_dcf(
    free_cashflow: float | None,
    growth_rate: float = 0.05,
    discount_rate: float = 0.09,
    years: int = 10,
) -> float | None:
    """
    Calcula un valor intrínseco simplificado vía Discounted Cash Flow (DCF).
    Proyecta el FCF actual con una tasa de crecimiento constante por 'years' años
    y descuenta los flujos a la tasa de descuento especificada.

    Args:
        free_cashflow: Free Cash Flow actual.
        growth_rate: Tasa de crecimiento anual (default 5%).
        discount_rate: Tasa de descuento (default 9%).
        years: Años a proyectar (default 10).

    Returns:
        Valor presente de los flujos proyectados, o None si el FCF es inválido.
    """
    if free_cashflow is None or free_cashflow <= 0:
        return None

    total_value = 0.0
    for year in range(1, years + 1):
        projected_fcf = free_cashflow * ((1.0 + growth_rate) ** year)
        discounted = projected_fcf / ((1.0 + discount_rate) ** year)
        total_value += discounted

    return round(total_value, 2)


def calculate_historical_multiple_value(eps: float | None, target_pe: float = 15.0) -> float | None:
    """
    Calcula el valor intrínseco basado en un múltiplo P/E histórico objetivo.
    Valor = EPS × P/E objetivo.

    Args:
        eps: Earnings Per Share (trailing).
        target_pe: Múltiplo P/E objetivo (default 15x).

    Returns:
        Valor intrínseco por múltiplo, o None si el EPS es inválido.
    """
    if eps is None or eps <= 0:
        return None
    return round(eps * target_pe, 2)


def calculate_target_probability(
    target_exit_price: float,
    current_price: float,
    target_mean_price: float | None,
    days_held: int,
    beta: float | None = None,
    sigma: float | None = None,
) -> float | None:
    """
    Calcula la probabilidad (0-100%) de que el precio alcance target_exit_price
    usando un modelo híbrido: log-normal (Black-Scholes ATM) × penalización logística de analistas.

    Market Probability — modelo log-normal:
        mu = R_f + beta × (R_m − R_f)     # CAPM drift
        Z  = [ln(P_T / P_C) − (mu − σ²/2) × t] / [σ × √t]
        market_prob = 1 − Φ(Z)

    Analyst Penalty — función logística:
        k = 15 (agresividad)
        penalty = 1 / (1 + e^{k × (P_T / P_A − 1)})

    Final: total = market_prob × penalty

    Args:
        target_exit_price: Precio objetivo calculado por la app (P_T).
        current_price: Precio actual del activo (P_C).
        target_mean_price: Precio objetivo de analistas (P_A).
        days_held: Días transcurridos (t = days / 365).
        beta: Beta de la acción (default 1.0 si no disponible).
        sigma: Volatilidad histórica anualizada (calculada de returns diarios × √252).
    """
    if target_mean_price is None or target_mean_price <= 0:
        return None
    if target_exit_price <= 0 or current_price <= 0:
        return None

    # Fix 2: el objetivo ya se alcanzó → probabilidad 100%
    if current_price >= target_exit_price:
        return 100.0

    # Fix 1: forzar mínimo 1 día para evitar división por cero
    safe_days: int = max(days_held, 1)

    beta_val: float = beta if beta is not None and beta > 0 else 1.0
    sigma_val: float = sigma if sigma is not None and sigma > 0 else 0.30

    R_f: float = 0.042
    R_m: float = 0.09
    t_years: float = safe_days / 365.0

    # ── 1. Drift (CAPM) ──────────────────────────────────────────
    mu: float = R_f + beta_val * (R_m - R_f)

    # ── 2. Market Probability (log-normal, derivado de Black-Scholes) ─
    numerator: float = np.log(target_exit_price / current_price) - (mu - (sigma_val**2) / 2.0) * t_years
    denominator: float = sigma_val * np.sqrt(t_years)
    if denominator <= 0:
        return None
    z_score: float = numerator / denominator
    market_probability: float = 1.0 - float(norm.cdf(z_score))

    # Fix 3: Penalización de analistas con cliff en 0.98 (k=40)
    # Solo penaliza fuerte cuando el target supera el 98% del consenso
    penalty_factor: float = 1.0 / (1.0 + np.exp(40.0 * (target_exit_price / target_mean_price - 0.98)))

    # ── 4. Final ──────────────────────────────────────────────────
    total_probability: float = market_probability * penalty_factor
    return round(max(0.0, min(100.0, total_probability * 100.0)), 1)


def calculate_volatility_regime(
    historical_close: list[float],
) -> tuple[float, float | None]:
    """
    Calcula el régimen de volatilidad actual usando detección de anomalías.

    Step 1: Umbral de anomalía = percentil 90 de los retornos absolutos diarios (1 año).
    Step 2: Identificar los días donde |retorno| > umbral.
    Step 3: Tomar los últimos 4 eventos anómalos.
    Step 4: heartbeat_days = intervalo promedio entre esos eventos.
    Step 5: sigma = volatilidad anualizada de los últimos (2 × heartbeat_days) días.

    Fallbacks:
      - < 2 anomalías → heartbeat = 21 días, sigma de 21 días.
      - < 21 datos → sigma de todo el histórico disponible.

    Args:
        historical_close: Lista de precios de cierre diarios (~252 para 1 año).

    Returns:
        (heartbeat_days: float, sigma: float | None)
    """
    if len(historical_close) < 21:
        return 21.0, None

    returns: np.ndarray = np.abs(np.diff(historical_close) / historical_close[:-1])
    anomaly_threshold: float = float(np.percentile(returns, 90))
    if anomaly_threshold <= 0:
        return 21.0, None

    # Índices donde ocurrió una anomalía (día del retorno, 0-indexado en el array de returns)
    anomaly_indices: list[int] = [i for i, r in enumerate(returns) if r > anomaly_threshold]

    if len(anomaly_indices) < 2:
        # Muy pocas anomalías: usar defaults
        recent_std = float(np.std(returns[-21:])) if len(returns) >= 21 else float(np.std(returns))
        sigma = recent_std * np.sqrt(252) if recent_std > 0 else None
        return 21.0, sigma

    # Últimos 4 eventos (o menos si hay < 4)
    last_4_indices = anomaly_indices[-4:]
    intervals: list[int] = [last_4_indices[i + 1] - last_4_indices[i] for i in range(len(last_4_indices) - 1)]
    heartbeat_days: float = max(1.0, float(np.mean(intervals)) if intervals else 21.0)

    # Sigma: volatilidad del período reciente (2 × heartbeat)
    lookback = int(max(21, 2 * heartbeat_days))
    window_returns = returns[-lookback:] if len(returns) >= lookback else returns
    daily_std: float = float(np.std(window_returns))
    sigma: float | None = daily_std * np.sqrt(252) if daily_std > 0 else None

    # Nota: NO se llama gc.collect() aquí. El generational GC de CPython maneja
    # eficientemente arrays numpy efímeros. Llamar gc.collect() en un hot loop
    # (una vez por posición del portafolio) añade 10-100ms por iteración sin beneficio real.

    return heartbeat_days, sigma
