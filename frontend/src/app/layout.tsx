import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Terminal Financiero",
  description: "Dashboard institucional de portafolio de inversión",
};

const NAV_ITEMS = [
  { href: "/", label: "Portafolio" },
  { href: "/screener", label: "Screener" },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full bg-background" suppressHydrationWarning>
        <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
          <div className="mx-auto flex h-12 max-w-7xl items-center justify-between px-4 md:px-8">
            <Link
              href="/"
              className="text-sm font-bold tracking-tight text-foreground font-mono hover:text-accent transition-colors"
            >
              Terminal Financiero
            </Link>
            <nav className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-lg px-3 py-1.5 text-xs font-medium font-mono text-foreground/60 transition-colors hover:text-foreground hover:bg-foreground/5"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
