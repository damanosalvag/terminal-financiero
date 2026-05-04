import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints.analysis import router as analysis_router
from app.api.endpoints.portfolio import router as portfolio_router
from app.api.endpoints.watchlist import router as watchlist_router
from app.core.config import settings
from app.core.database import Base, engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Al iniciar la aplicación, crea todas las tablas definidas en los modelos SQLAlchemy
    en la base de datos de Supabase si no existen aún.
    Si la base de datos no está disponible, el servidor arranca igual para permitir
    diagnóstico; las rutas que requieran DB fallarán con un error claro.
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tables created successfully.")
    except Exception as exc:
        logger.warning("Could not create tables: %s", exc)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(analysis_router)


@app.get("/")
def root():
    return {"status": "ok", "project": settings.PROJECT_NAME}
