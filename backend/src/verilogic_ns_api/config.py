from functools import lru_cache
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "VeriLogic-NS API"
    version: str = "0.1.0"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    orchestration_provider_mode: str = "cache_only"
    orchestration_queue_size: int = 3
    orchestration_retention_seconds: int = 1800

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="VERILOGIC_",
        extra="ignore",
    )

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        normalized: list[str] = []
        for origin in origins:
            parsed = urlparse(origin)
            if origin == "*" or parsed.scheme not in {"http", "https"} or not parsed.netloc:
                msg = f"CORS origin must be an explicit HTTP(S) origin: {origin!r}"
                raise ValueError(msg)
            normalized.append(origin.rstrip("/"))
        return normalized

    @field_validator("orchestration_provider_mode")
    @classmethod
    def validate_provider_mode(cls, value: str) -> str:
        if value not in {"live", "cache_only"}:
            raise ValueError("orchestration provider mode must be live or cache_only")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
