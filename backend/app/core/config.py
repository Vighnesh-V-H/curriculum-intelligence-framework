from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Curriculum Intelligence API"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    database_url: str
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0)
    cors_origins: list[str] = ["http://localhost:3000"]
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: SecretStr | None = None

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
