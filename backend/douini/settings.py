from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "dev"
    DEBUG: bool = True
    SECRET_KEY: str = "dev-only-not-for-production-use-32-chars"
    DATABASE_URL: str = "postgresql+psycopg://douini:douini@localhost:5432/douini"
    API_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8081"]

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@douini.run"
    FRONTEND_URL: str = "http://localhost:5173"

    DOUINI_ENCRYPTION_KEY: str = ""

    @model_validator(mode="after")
    def _check_secret_key(self) -> Settings:
        if self.ENVIRONMENT in ("ppe", "prod") and len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be >= 32 chars in ppe/prod")
        return self

    @property
    def is_prod(self) -> bool:
        return self.ENVIRONMENT == "prod"

    @property
    def psycopg_dsn(self) -> str:
        return self.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")


settings = Settings()

_SECRET_PATTERNS = [
    re.compile(r"(SECRET_KEY\s*[=:]\s*)\S+", re.I),
    re.compile(r"(PASSWORD\s*[=:]\s*)\S+", re.I),
    re.compile(r"(TOKEN\s*[=:]\s*)\S+", re.I),
    re.compile(r"(ENCRYPTION_KEY\s*[=:]\s*)\S+", re.I),
]


class SecretFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage())
        for pat in _SECRET_PATTERNS:
            msg = pat.sub(r"\1***", msg)
        record.msg = msg
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    if settings.is_prod:
        import json

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                log: dict[str, Any] = {
                    "level": record.levelname,
                    "name": record.name,
                    "msg": record.getMessage(),
                }
                if record.exc_info:
                    log["exc"] = self.formatException(record.exc_info)
                return json.dumps(log)

        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
        )
    handler.addFilter(SecretFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
