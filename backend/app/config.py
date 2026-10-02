from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # mysql+pymysql://user:password@localhost/tricycle_waste in production
    database_url: str = "sqlite:///./tricycle_waste.db"
    secret_key: str = "change-me"
    token_hours: int = 24

    match_radius_km: float = 3.0
    offer_timeout_seconds: int = 30
    location_stale_minutes: int = 10
    default_disposal_radius_m: float = 150

    admin_email: str = "admin@tricyclewaste.local"
    admin_password: str = "change-me-admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()
