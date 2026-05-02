const API_BASE = "http://localhost:8000";

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
    throw new Error(`Error fetching summary: ${res.status}`);
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
    throw new Error(`Error closing position: ${res.status}`);
  }
  return res.json();
}
