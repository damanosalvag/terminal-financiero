"use client";

import { type FormEvent, useState } from "react";
import { createPosition } from "@/app/api";

interface Props {
  open: boolean;
  onClose: () => void;
  onPositionCreated: () => void;
}

export default function NewPositionModal({ open, onClose, onPositionCreated }: Props) {
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [buyPrice, setBuyPrice] = useState("");
  const [buyDate, setBuyDate] = useState("");
  const [commission, setCommission] = useState("0");
  const [inflation, setInflation] = useState("3.0");
  const [targetYield, setTargetYield] = useState("100.0");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const resetForm = () => {
    setTicker("");
    setQuantity("");
    setBuyPrice("");
    setBuyDate("");
    setCommission("0");
    setInflation("3.0");
    setTargetYield("100.0");
    setError("");
  };

  const handleOverlayClick = () => {
    if (!submitting) onClose();
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      await createPosition({
        ticker: ticker.trim().toUpperCase(),
        quantity: parseFloat(quantity),
        buy_price: parseFloat(buyPrice),
        buy_date: new Date(buyDate).toISOString(),
        commission: parseFloat(commission) || 0,
        estimated_inflation: parseFloat(inflation) || 0,
        target_annual_yield: parseFloat(targetYield) || 0,
      });

      resetForm();
      onPositionCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear la posición");
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass =
    "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono text-foreground placeholder:text-foreground/20 focus:outline-none focus:ring-2 focus:ring-accent/50 transition-colors";

  const labelClass = "block mb-1 text-xs font-medium text-foreground/50 uppercase tracking-wider";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={handleOverlayClick}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-bold text-foreground font-mono">Nueva Posición</h2>
          <button
            onClick={onClose}
            disabled={submitting}
            className="rounded-lg p-1 text-foreground/30 hover:text-foreground/80 transition-colors disabled:opacity-20"
          >
            <CloseIcon />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Ticker</label>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="AAPL"
                maxLength={10}
                required
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Cantidad</label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="1.5"
                step="0.01"
                min="0.01"
                required
                className={inputClass}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Precio Compra</label>
              <input
                type="number"
                value={buyPrice}
                onChange={(e) => setBuyPrice(e.target.value)}
                placeholder="150.00"
                step="0.01"
                min="0.01"
                required
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Fecha Compra</label>
              <input
                type="datetime-local"
                value={buyDate}
                onChange={(e) => setBuyDate(e.target.value)}
                required
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label className={labelClass}>Comisión</label>
            <input
              type="number"
              value={commission}
              onChange={(e) => setCommission(e.target.value)}
              step="0.01"
              min="0"
              className={inputClass}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Inflación Est. %</label>
              <input
                type="number"
                value={inflation}
                onChange={(e) => setInflation(e.target.value)}
                step="0.1"
                min="0"
                className={inputClass}
              />
            </div>
            <div>
              <label className={labelClass}>Obj. Anual %</label>
              <input
                type="number"
                value={targetYield}
                onChange={(e) => setTargetYield(e.target.value)}
                step="0.1"
                min="0"
                className={inputClass}
              />
            </div>
          </div>

          {error && (
            <p className="rounded-lg border border-negative/30 bg-negative/10 px-3 py-2 text-xs font-mono text-negative">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-accent py-2.5 text-sm font-bold text-accent-foreground hover:bg-accent/90 transition-colors disabled:opacity-50 font-mono"
          >
            {submitting ? "Creando..." : "Crear Posición"}
          </button>
        </form>
      </div>
    </div>
  );
}

function CloseIcon() {
  return (
    <svg
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}
