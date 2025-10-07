from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    PROJECT_NAME: str = "bwm-ilp-spk"
    API_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "mysql+asyncmy://user:password@localhost:3306/bwm_ilp_spk"
    ECHO_SQL: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()


settings = get_settings()
