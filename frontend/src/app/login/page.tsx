"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        throw new Error(`Credenciales inválidas (${res.status})`);
      }
      const data: TokenResponse = await res.json();
      document.cookie = `token=${data.access_token}; path=/; max-age=86400`;
      window.location.href = "/";
    } catch (err: unknown) {
      if (err instanceof TypeError) {
        setError("No se puede conectar al servidor. ¿Está corriendo el backend?");
      } else {
        setError(err instanceof Error ? err.message : "Error al iniciar sesión");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-xl border border-border/50 bg-surface p-6 space-y-5">
        <div>
          <h1 className="text-sm font-bold tracking-widest text-foreground/40 uppercase font-mono mb-1">
            Terminal Financiero
          </h1>
          <p className="text-[11px] text-foreground/25 font-mono">Acceso institucional</p>
        </div>

        <div className="space-y-3">
          <input
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            placeholder="Usuario"
            autoComplete="username"
            required
            className="w-full rounded-md border border-border/50 bg-background px-3 py-2 text-sm font-mono text-foreground placeholder:text-foreground/15 focus:outline-none focus:border-accent/50 transition-colors"
          />
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Contraseña"
            autoComplete="current-password"
            required
            className="w-full rounded-md border border-border/50 bg-background px-3 py-2 text-sm font-mono text-foreground placeholder:text-foreground/15 focus:outline-none focus:border-accent/50 transition-colors"
          />
        </div>

        {error && (
          <p className="text-[11px] font-mono text-[var(--negative)]">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-accent/90 py-2 text-sm font-bold font-mono text-white hover:bg-accent disabled:opacity-40 transition-colors"
        >
          {loading ? "..." : "Ingresar"}
        </button>
      </form>
    </div>
  );
}
