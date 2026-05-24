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
│   │   │   ├── screener.py           # Scanner multi-filtro con paginación
│   │   │   └── auth.py               # Login JWT con rate limiting
│   │   ├── core/                     # Configuración
│   │   │   ├── config.py             # Settings via .env (pydantic-settings)
│   │   │   ├── database.py           # SQLAlchemy engine + session
│   │   │   ├── security.py           # JWT create/verify (python-jose, 1 día)
│   │   │   ├── rate_limit.py         # 5 intentos/15min por IP
│   │   │   └── deps.py               # Dependencias FastAPI (legacy)
│   │   ├── infrastructure/
│   │   │   └── market_data.py        # YahooFinanceClient (yfinance wrapper)
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
| `POST` | `/screener/scan` | Scanner multi-filtro con paginación |

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
