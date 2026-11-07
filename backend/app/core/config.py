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
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    database_url: str
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0)
    cors_origins: list[str] = ["http://localhost:3000"]
    cors_allow_origin_regex: str = (
        r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+"
        r"|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$"
    )
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: SecretStr | None = None
    max_upload_size_mb: int = Field(default=20, gt=0)
    allowed_upload_extensions: list[str] = [".pdf", ".docx", ".txt", ".md", ".csv"]
    uploadthing_token: SecretStr | None = None
    uploadthing_api_key: SecretStr | None = None
    uploadthing_app_id: str | None = None
    uploadthing_region: str | None = None
    uploadthing_ingest_host: str = "ingest.uploadthing.com"
    uploadthing_ufs_host: str = "ufs.sh"
    uploadthing_ufs_app_id_location: str = "subdomain"
    uploadthing_timeout_seconds: int = Field(default=120, gt=0)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = Field(default=120, gt=0)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return normalized

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
