# Terminal Financiero

Dashboard institucional de portafolio de inversión con análisis en tiempo real, métricas de interés compuesto y objetivo de utilidad anual (100% Efectivo Anual).

## Arquitectura

```
terminal-financiero/
├── backend/                  # FastAPI + SQLAlchemy + Pandas
│   ├── app/
│   │   ├── api/endpoints/    # Rutas HTTP (CRUD + análisis)
│   │   ├── core/             # Configuración (DB, settings)
│   │   ├── infrastructure/   # Clientes externos (Yahoo Finance)
│   │   ├── models/           # Modelos SQLAlchemy
│   │   ├── schemas/          # Validación Pydantic
│   │   └── services/         # Lógica financiera pura
│   ├── .env                  # DATABASE_URL (no commitear)
│   └── requirements.txt
├── frontend/                 # Next.js 16 + Tailwind CSS v4
│   └── src/app/
│       ├── api.ts            # Cliente HTTP tipado
│       ├── globals.css       # Tema oscuro profesional
│       ├── layout.tsx
│       └── page.tsx          # Dashboard principal
└── .cursorrules              # Reglas de arquitectura para AI
```

### Principios (Clean Architecture)

- **Backend calcula, Frontend dibuja** — Sin lógica financiera en componentes React.
- **Modularidad** — Cambiar de proveedor de datos (yfinance → Alpha Vantage) solo afecta la capa `infrastructure/`.
- **Inyección de dependencias** — FastAPI `Depends()` para sesiones de DB; sin instancias directas en rutas.
- **Tipado estricto** — Python type hints obligatorios, TypeScript sin `any`.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0, Pandas |
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4 |
| Base de datos | PostgreSQL (Supabase) |
| Datos de mercado | yfinance |

## Instalación

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# Configurar .env con tu DATABASE_URL de Supabase
cp .env.example .env

# Ejecutar
uvicorn app.main:app --reload
```

API disponible en `http://localhost:8000` · OpenAPI docs en `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard disponible en `http://localhost:3000`.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/portfolio/` | Crear posición |
| `GET` | `/portfolio/` | Listar posiciones activas |
| `GET` | `/portfolio/summary` | Resumen macro del portafolio |
| `GET` | `/portfolio/{id}/analysis` | Análisis individual con métricas en tiempo real |
| `PATCH` | `/portfolio/{id}/close` | Cerrar posición (registrar salida) |

## Modelo de Datos — `PortfolioPosition`

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | Identificador único |
| `ticker` | String(10) | Símbolo bursátil |
| `quantity` | Float | Cantidad de títulos (acepta fracciones) |
| `buy_price` | Float | Precio unitario de compra |
| `currency` | String(3) | Código de moneda (USD, MXN, EUR) |
| `buy_date` | DateTime | Fecha de adquisición |
| `commission` | Float | Comisión total de la operación |
| `estimated_inflation` | Float | Inflación anual estimada (%) |
| `target_annual_yield` | Float | Objetivo de rentabilidad anual (%) |
| `is_active` | Boolean | Posición activa en portafolio |
| `exit_price` | Float | Precio de salida al cerrar |
| `exit_date` | DateTime | Fecha de cierre |

## Fórmulas Financieras

- **Interés compuesto diario**: `P_objetivo = costo_base × (1 + tasa_efectiva)^(días/365)`
- **Tasa efectiva**: `(1 + rentabilidad_objetivo) × (1 + inflación) − 1`
- **Utilidad real**: `valor_actual − costo_base − erosión_inflacionaria`
- **Comisión prorrateada**: `costo_base/título = precio_compra + comisión/cantidad`

## Convenciones

- Código en **inglés**, comentarios y UI en **español**.
- Nombres descriptivos: `precio_cierre_ajustado` en lugar de `pca`.
- Estados asíncronos: siempre `loading`, `error`, `success`.
- Componentes Smart (fetch datos) / Dumb (reciben props y renderizan).
