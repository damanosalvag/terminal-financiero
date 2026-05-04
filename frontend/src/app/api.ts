const API_BASE = "/api";

export interface PortfolioPosition {
  id: string;
  ticker: string;
  quantity: number;
  buy_price: number;
  currency: string;
  buy_date: string;
  commission: number;
  estimated_inflation: number;
  target_annual_yield: number;
  is_active: boolean;
  exit_price: number | null;
  exit_date: string | null;
}

export interface PositionAnalysis extends PortfolioPosition {
  current_price: number;
  dividends_collected: number;
  days_held: number;
  target_exit_price: number;
  current_utility_percentage: number;
}

export interface PortfolioSummary {
  total_invested_capital: number;
  total_current_value: number;
  global_utility_percentage: number;
  positions: PositionAnalysis[];
}

export async function getPortfolioSummary(): Promise<PortfolioSummary> {
  const res = await fetch(`${API_BASE}/portfolio/summary`);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Error ${res.status} al obtener resumen. ${detail}`);
  }
  return res.json();
}

export interface PositionCreatePayload {
  ticker: string;
  quantity: number;
  buy_price: number;
  buy_date: string;
  commission?: number;
  estimated_inflation?: number;
  target_annual_yield?: number;
}

export async function createPosition(
  payload: PositionCreatePayload
): Promise<PortfolioPosition> {
  const res = await fetch(`${API_BASE}/portfolio/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, currency: "USD" }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Error ${res.status} al crear posición. ${detail}`);
  }
  return res.json();
}

export async function closePosition(
  id: string,
  exit_price: number,
  exit_date: string
): Promise<PortfolioPosition> {
  const res = await fetch(`${API_BASE}/portfolio/${id}/close`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ exit_price, exit_date }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Error ${res.status} al cerrar posición. ${detail}`);
  }
  return res.json();
}

export interface PositionHistoryItem extends PortfolioPosition {
  exit_price: number;
  exit_date: string;
  realized_profit_currency: number;
  realized_utility_percentage: number;
  actual_days_held: number;
}

export interface PositionHistoryResponse {
  total_realized_profit: number;
  total_closed_positions: number;
  positions: PositionHistoryItem[];
}

export async function getPortfolioHistory(): Promise<PositionHistoryResponse> {
  const res = await fetch(`${API_BASE}/portfolio/history`);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Error ${res.status} al obtener historial. ${detail}`);
  }
  return res.json();
}
