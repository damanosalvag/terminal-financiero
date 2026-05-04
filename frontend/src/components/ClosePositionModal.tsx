"use client";

import { type FormEvent, useState } from "react";
import { type PositionAnalysis, closePosition } from "@/app/api";

interface Props {
  open: boolean;
  position: PositionAnalysis | null;
  onClose: () => void;
  onClosed: () => void;
}

function toLocalDatetimeString(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function ClosePositionModal({ open, position, onClose, onClosed }: Props) {
  const [exitPrice, setExitPrice] = useState("");
  const [exitDate, setExitDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Pre-fill defaults cuando el modal se abre con una posición
  if (open && position && exitPrice === "") {
    setExitPrice(position.current_price.toFixed(2));
    setExitDate(toLocalDatetimeString(new Date()));
  }

  if (!open || !position) return null;

  const handleOverlayClick = () => {
    if (!submitting) onClose();
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      await closePosition(position.id, parseFloat(exitPrice), new Date(exitDate).toISOString());
      setExitPrice("");
      setExitDate("");
      onClosed();
      onClose();
      alert(`Posición ${position.ticker} cerrada exitosamente.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cerrar la posición");
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass =
    "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono text-foreground placeholder:text-foreground/20 focus:outline-none focus:ring-2 focus:ring-negative/50 transition-colors";

  const labelClass = "block mb-1 text-xs font-medium text-foreground/50 uppercase tracking-wider";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={handleOverlayClick}
    >
      <div
        className="w-full max-w-sm rounded-2xl border border-border bg-surface p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-bold text-foreground font-mono">
            Cerrar {position.ticker}
          </h2>
          <button
            onClick={onClose}
            disabled={submitting}
            className="rounded-lg p-1 text-foreground/30 hover:text-foreground/80 transition-colors disabled:opacity-20"
          >
            <CloseIcon />
          </button>
        </div>

        <div className="mb-4 rounded-lg border border-border bg-background px-4 py-3 space-y-1">
          <div className="flex justify-between text-xs text-foreground/50 font-mono">
            <span>P. Compra</span>
            <span>P. Actual</span>
          </div>
          <div className="flex justify-between text-sm font-bold font-mono">
            <span className="text-foreground/70">${position.buy_price.toFixed(2)}</span>
            <span className="text-foreground">${position.current_price.toFixed(2)}</span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={labelClass}>Precio de Salida</label>
            <input
              type="number"
              value={exitPrice}
              onChange={(e) => setExitPrice(e.target.value)}
              step="0.01"
              min="0.01"
              required
              className={inputClass}
            />
          </div>

          <div>
            <label className={labelClass}>Fecha de Salida</label>
            <input
              type="datetime-local"
              value={exitDate}
              onChange={(e) => setExitDate(e.target.value)}
              required
              className={inputClass}
            />
          </div>

          {error && (
            <p className="rounded-lg border border-negative/30 bg-negative/10 px-3 py-2 text-xs font-mono text-negative">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-negative py-2.5 text-sm font-bold text-white hover:bg-negative/90 transition-colors disabled:opacity-50 font-mono"
          >
            {submitting ? "Cerrando..." : `Cerrar ${position.ticker}`}
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
