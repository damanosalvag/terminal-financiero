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

import pandas as pd


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
    delta = naive_current - naive_buy
    return max(abs(delta.days), 1)


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
