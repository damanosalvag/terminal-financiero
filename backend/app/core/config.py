from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Gestor de configuración que carga variables desde el archivo .env en /backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    PROJECT_NAME: str = "Terminal Financiero API"
    DEEPSEEK_API_KEY: str | None = None
    AUTH_USERNAME: str = "admin"
    AUTH_PASSWORD: str
    JWT_SECRET: str
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    COOKIE_SECURE: bool = False  # True en producción (HTTPS)
    CLOUDFLARE_WORKER_URL: str = "https://yahoo-stealth-proxy.damanosalvag.workers.dev/"


settings = Settings()
