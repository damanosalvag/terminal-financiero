# Terminal Financiero

Dashboard institucional de portafolio de inversión con análisis técnico, fundamental, IA estratégica y escáner de mercado.

## Arquitectura

```
terminal-financiero/
├── backend/                          # FastAPI + SQLAlchemy + Pandas
│   ├── app/
│   │   ├── api/endpoints/            # Rutas HTTP
│   │   │   ├── portfolio.py          # CRUD de posiciones + summary + news intel
│   │   │   ├── watchlist.py          # Radar (CRUD + análisis en paralelo)
│   │   │   ├── analysis.py           # Cockpit (chart, fundamentals, narrative, market-heatmap)
│   │   │   ├── screener.py           # Scanner multi-filtro (PE, PS, Cap, Beta, Sector, D/E, RSI, MACD, EMA200, RVOL)
│   │   │   └── auth.py               # Login JWT con rate limiting
│   │   ├── core/                     # Configuración
│   │   │   ├── config.py             # Settings via .env (pydantic-settings)
│   │   │   ├── database.py           # SQLAlchemy engine + session
│   │   │   ├── security.py           # JWT create/verify (python-jose, 1 día)
│   │   │   ├── rate_limit.py         # 5 intentos/15min por IP
│   │   │   └── deps.py               # Dependencias FastAPI (legacy)
│   │   ├── infrastructure/
│   │   │   └── market_data.py        # YahooFinanceClient (proxy + cache + degradación)
│   │   ├── models/                   # SQLAlchemy ORM
│   │   │   ├── portfolio.py          # PortfolioPosition (UUID, 14 campos)
│   │   │   └── watchlist.py          # WatchlistTicker + importance_score
│   │   ├── schemas/                  # Pydantic validation
│   │   │   ├── portfolio.py          # PositionCreate/Response/AnalysisResponse
│   │   │   ├── watchlist.py          # WatchlistCreate/Response
│   │   │   └── auth.py              # LoginRequest/TokenResponse
│   │   └── services/                 # Lógica pura (sin DB)
│   │       ├── finance_math.py       # Interés compuesto, RSI, Graham, DCF, probabilidad log-normal
│   │       ├── technical_analysis.py # EMA, MACD, ADX, OBV, MFI, VWAP, Stochastic, Wyckoff
│   │       ├── screener.py           # Batch scan con yfinance.download() vectorizado
│   │       └── llm_advisor.py        # DeepSeek AI (noticias, narrativa)
│   ├── .env                          # Variables de entorno (NO COMMITEAR)
│   └── requirements.txt
└── frontend/                         # Next.js 16 (App Router) + Tailwind CSS v4
    ├── src/
    │   ├── app/
    │   │   ├── page.tsx              # Dashboard (4 tabs: Portafolio, Historial, Radar, Heatmap)
    │   │   ├── layout.tsx            # Root layout + nav + autenticación
    │   │   ├── api.ts               # Cliente HTTP con auth automática
    │   │   ├── login/page.tsx       # Login JWT
    │   │   ├── screener/page.tsx    # Scanner multi-filtro + tabla expandida
    │   │   ├── globals.css          # Tema oscuro institucional (Tailwind v4)
    │   │   └── asset/[ticker]/page.tsx  # Cockpit (chart + technical + fundamental + IA)
    │   ├── components/
    │   │   ├── NewPositionModal.tsx
    │   │   ├── ClosePositionModal.tsx
    │   │   ├── HealthRadarChart.tsx  # SVG nativo (sin recharts)
    │   │   └── LogoutButton.tsx
    │   └── middleware.ts             # Auth proxy (protege rutas)
    └── package.json
```

## Arquitectura Anti-Bloqueo (Resiliencia en Render)

El backend opera en Render (512MB RAM) y Yahoo Finance bloquea IPs de servidores cloud. Se implementó una defensa en 4 capas para evitar que el UI se caiga:

| Capa | Concepto | Ubicación | Mecanismo |
|---|---|---|---|
| 1 | **Stealth Proxy** | `infrastructure/market_data.py:20-39` | Monkey-patch de `requests.Session.send` — redirige requests a Yahoo por Cloudflare Worker. Se activa/desactiva con `CLOUDFLARE_WORKER_URL` |
| 2 | **Soft Cache 120s** | `infrastructure/market_data.py:50-85` | Dict en memoria con TTL de 120s en `get_current_price()`. Fallback a caché expirado si la API falla |
| 3 | **Degradación Elegante** | `infrastructure/market_data.py:127-175` | `get_target_price()` retorna `current_price × 1.10` si Yahoo falla. `get_fundamentals()` retorna `{}` en vez de lanzar excepción. `get_beta()` retorna `None`. `portfolio.py` usa el cliente en vez de yfinance directo |
| 4 | **Iteration Throttling + Jitter** | `portfolio.py:167`, `watchlist.py:30`, `screener.py:68` | `time.sleep(0.3-1.0s)` con `random.uniform()` entre requests. Evita ráfagas sincronizadas que disparen rate limiting |

## Stack

| Capa | Tecnologías |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0, Pandas, NumPy, SciPy |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS v4, Lightweight Charts |
| Base de datos | PostgreSQL (Supabase) |
| Datos mercado | yfinance (Yahoo Finance) |
| IA | DeepSeek API (OpenAI-compatible) |
| Auth | JWT (python-jose), cookies HttpOnly, rate limiting |
| Deploy | Render (backend) + Vercel (frontend) |

## Instalación

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
# Configurar backend/.env con DATABASE_URL, AUTH_PASSWORD, JWT_SECRET
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
# Configurar .env.local con NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm run dev
```

## Endpoints API

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/auth/login` | Login JWT (rate limited: 5/15min) |
| `GET/POST` | `/portfolio/` | CRUD posiciones (POST promedia si ya existe) |
| `GET` | `/portfolio/summary` | Resumen + análisis técnico + probabilidad |
| `GET` | `/portfolio/history` | Historial cerradas + métricas avanzadas |
| `GET` | `/portfolio/news-intel` | IA de noticias por posición |
| `GET/POST/DELETE` | `/watchlist/` | Radar con análisis en paralelo |
| `GET` | `/watchlist/check/{ticker}` | Verificar si está en watchlist |
| `GET` | `/analysis/{ticker}/chart` | OHLCV + análisis técnico completo |
| `GET` | `/analysis/{ticker}/fundamentals` | Ratios + valor intrínseco + checklist |
| `GET` | `/analysis/{ticker}/narrative` | IA estratégica (DeepSeek) |
| `GET` | `/analysis/market-heatmap` | Heatmap S&P 500 / Dow / Nasdaq / Russell |
| `POST` | `/screener/scan` | Scanner multi-filtro (PE, PS, Cap, Beta, Sector, D/E, RSI, MACD, EMA200, RVOL) |

## Variables de entorno

### Backend (.env / Render)

| Variable | Obligatorio | Descripción |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL (Supabase) |
| `AUTH_PASSWORD` | ✅ | Contraseña de login |
| `JWT_SECRET` | ✅ | Clave de firma JWT (32+ chars) |
| `AUTH_USERNAME` | No | Default: `admin` |
| `ALLOWED_ORIGINS` | ✅ | `https://tu-app.vercel.app` |
| `COOKIE_SECURE` | ✅ | `true` en producción |
| `DEEPSEEK_API_KEY` | No | IA de noticias |
| `MALLOC_ARENA_MAX` | Recomendado | `2` (optimiza RAM en Render) |
| `CLOUDFLARE_WORKER_URL` | No | `https://yahoo-stealth-proxy.damanosalvag.workers.dev/` — dejar vacío para desactivar proxy |

### Frontend (.env.local / Vercel)

| Variable | Obligatorio | Descripción |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | ✅ | `https://terminal-financiero-api.onrender.com` |

## Convenciones

- Código en **inglés**, comentarios y UI en **español**
- Backend calcula, Frontend dibuja — sin lógica financiera en React
- Type hints obligatorios en Python, sin `any` en TypeScript
- Manejo de estados `loading | error | success` en todas las vistas
- Componentes Smart (fetch) / Dumb (reciben props)
- Fórmulas financieras en `/services`, APIs externas en `/infrastructure`
- Resiliencia: toda llamada externa tiene timeout implícito vía proxy, caché 120s, y degradación a fallback matemático. El UI nunca crashea por un error de red
- Throttling: `time.sleep(0.3 + random.uniform(0, 0.4))` antes de cada request externo para evitar rate limiting
- Proxy toggle: `CLOUDFLARE_WORKER_URL` (env var) habilita/deshabilita el stealth proxy. Vacío = llamadas directas
