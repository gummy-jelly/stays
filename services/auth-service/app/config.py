from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_EXPIRE: int = 30        # Access Token 만료 (분)
    REFRESH_EXPIRE: int = 7     # Refresh Token 만료 (일)
    REDIS_URL: str = "redis://localhost:6379/0"
    SERVICE_PORT: int = 8000

    model_config = {"env_file": ".env"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
