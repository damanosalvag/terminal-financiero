"use client";

import { useRouter } from "next/navigation";

export default function LogoutButton() {
  const router = useRouter();

  const handleLogout = () => {
    document.cookie = "token=; path=/; max-age=0";
    window.location.href = "/login";
  };

  return (
    <button
      onClick={handleLogout}
      className="px-3 py-1 text-[11px] font-mono text-foreground/25 hover:text-[var(--negative)] transition-colors"
    >
      Salir
    </button>
  );
}
