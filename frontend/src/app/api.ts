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
  current_rsi: number | null;
  sector: string;
  daily_change_pct: number | null;
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
  best_trade_ticker: string | null;
  best_trade_profit: number | null;
  worst_trade_ticker: string | null;
  worst_trade_loss: number | null;
  win_rate_percentage: number;
  total_commissions_paid: number;
}

export async function getPortfolioHistory(): Promise<PositionHistoryResponse> {
  const res = await fetch(`${API_BASE}/portfolio/history`);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Error ${res.status} al obtener historial. ${detail}`);
  }
  return res.json();
}

export interface WatchlistTicker {
  id: string;
  ticker: string;
  added_date: string;
  current_price: number | null;
  current_rsi: number | null;
  target_price: number | null;
  margin_of_safety: number | null;
}

export async function getWatchlist(): Promise<WatchlistTicker[]> {
  const res = await fetch(`${API_BASE}/watchlist/`);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Error ${res.status} al obtener watchlist. ${detail}`);
  }
  return res.json();
}

export async function addWatchlistTicker(ticker: string): Promise<WatchlistTicker> {
  const res = await fetch(`${API_BASE}/watchlist/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Error ${res.status} al agregar ticker. ${detail}`);
  }
  return res.json();
}

export async function removeWatchlistTicker(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/watchlist/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Error ${res.status} al eliminar ticker. ${detail}`);
  }
}

export interface MarketHeatmapAsset {
  ticker: string;
  change_pct: number;
}

export interface MarketHeatmapSector {
  sector: string;
  assets: MarketHeatmapAsset[];
}

export async function getMarketHeatmap(): Promise<MarketHeatmapSector[]> {
  const res = await fetch(`${API_BASE}/analysis/market-heatmap`);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Error ${res.status} al obtener heatmap. ${detail}`);
  }
  return res.json();
}
