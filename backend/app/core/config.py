from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Gestor de configuración que carga variables desde el archivo .env en /backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    DATABASE_URL: str
    PROJECT_NAME: str = "Terminal Financiero API"


settings = Settings()
