"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the FlagBoard application."""

    database_url: str
    jwt_secret: str
    jwt_expiry_hours: int = 24
    api_key_pepper: str
    cache_ttl_seconds: int = 30
    cors_allowed_origins: list[str]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
