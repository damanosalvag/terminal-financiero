import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import LogoutButton from "@/components/LogoutButton";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Terminal Financiero",
  description: "Dashboard institucional de portafolio de inversión",
};

const NAV_ITEMS = [
  { href: "/", label: "Portafolio" },
  { href: "/screener", label: "Screener" },
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="min-h-full bg-background" suppressHydrationWarning>
        <header className="sticky top-0 z-50 border-b border-border/60 bg-background/90 backdrop-blur-lg">
          <div className="mx-auto flex h-10 max-w-screen-2xl items-center justify-between px-4 md:px-6">
            <Link href="/" className="text-[11px] font-semibold tracking-widest text-foreground/40 uppercase font-mono hover:text-foreground/70 transition-colors">
              TF
            </Link>
            <nav className="flex items-center">
              {NAV_ITEMS.map((item) => (
                <Link key={item.href} href={item.href}
                  className="px-3 py-1 text-[11px] font-mono text-foreground/40 hover:text-foreground transition-colors">
                  {item.label}
                </Link>
              ))}
              <span className="mx-1 text-border">|</span>
              <LogoutButton />
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
