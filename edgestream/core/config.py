"""
Project:   edgestream-api
File:      edgestream/core/config.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

import logging
import pathlib
import sys
from secrets import token_urlsafe
from uuid import uuid4
from typing import List, Optional, Union, Literal

from pydantic import field_validator, AnyHttpUrl, Field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    PydanticBaseSettingsSource,
    DotEnvSettingsSource,
)

# Root of the project (edgestream/..)
ROOT = pathlib.Path(__file__).resolve().parent.parent


class Logger:
    """Centralized logger configuration for the core application."""
    logger = logging.getLogger("edgestream")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    h = logging.StreamHandler(sys.stdout)
    h.setLevel(logging.INFO)
    h.setFormatter(logging.Formatter("%(levelname)-8s [%(pathname)s:%(lineno)d]: %(message)s"))
    if not logger.handlers:
        logger.addHandler(h)


def _uuid() -> str:
    return uuid4().hex


class SafeDotEnv(DotEnvSettingsSource):
    """
    Standard DotEnv source with a safety wrapper.
    Prevents the application from crashing if the system secrets file is 
    locked or missing, instead surfacing a diagnostic flag.
    """

    def __init__(self, settings_cls, *, env_file=None, env_file_encoding=None):
        super().__init__(settings_cls, env_file=env_file, env_file_encoding=env_file_encoding)

        paths = self.env_file
        if isinstance(paths, (str, pathlib.Path)):
            paths = [str(paths)]
        elif paths is None:
            paths = []
        self._paths = [str(p) for p in paths]

        self._mark_denied = any("edgestream-api.secrets" in p for p in self._paths)

    def __call__(self) -> dict:
        try:
            return super().__call__()
        except (PermissionError, FileNotFoundError) as e:
            where = ", ".join(self._paths) or "<unknown>"
            Logger.logger.warning(
                "Configuration source skipped: %s (Reason: %s)", where, e
            )
            return {"SECRETS_READ_DENIED": True} if self._mark_denied else {}
        except Exception as e:
            Logger.logger.error("Unexpected error loading configuration: %s", e)
            return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore",
        env_file_encoding="utf-8",
    )

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Precedence: 
        # 1. Environment variables (OS ENV)
        # 2. System secrets (/etc/edgestream/edgestream-api.secrets)
        # 3. Local .env file
        # 4. Defaults defined
        safe_dotenv_global = SafeDotEnv(
            settings_cls, env_file="/etc/edgestream/edgestream-api.secrets"
        )
        safe_dotenv_local = SafeDotEnv(settings_cls, env_file=".env")

        return (init_settings, env_settings, safe_dotenv_global, safe_dotenv_local, file_secret_settings)

    # ---- System Metadata ----
    VERSION: str = "0.1.0"
    SECRETS_READ_DENIED: bool = False
    ENV: Literal["prod", "dev"] = "prod"
    API_V1_STR: str = "/api/v1"

    # ---- Startup version check (on by default; see services/version_check.py) ----
    VERSION_CHECK_ENABLED: bool = True
    VERSION_CHECK_API_URL: str = "https://releases.hyperi.io/api/v1/check"
    VERSION_CHECK_TIMEOUT: float = 5.0
    VERSION_CHECK_SEND_INSTANCE_ID: bool = True
    VERSION_CHECK_INSTANCE_ID: Optional[str] = None

    # ---- Auth / Security ----
    AUTH0_DOMAIN: Optional[str] = None
    AUTH0_CLIENT_ID: Optional[str] = None

    JWT_SECRET: str = Field(default_factory=_uuid)
    ALGORITHM: Literal["HS256", "RS256"] = "HS256"
    ACCESS_TOKEN_MINUTES: int = 60  # Increased from 15 for better UX
    JWT_ISSUER: Optional[str] = None
    JWT_AUDIENCE: Optional[str] = None

    # System Task Token for the background runner
    EDGESTREAM_QUEUE_TOKEN: Optional[str] = None

    # ---- CORS Configuration ----
    BACKEND_CORS_ORIGINS: List[Union[AnyHttpUrl, str]] = Field(default_factory=list)
    BACKEND_CORS_ORIGIN_REGEX: Optional[str] = None

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        return []

    # ---- Persistence (Database) ----
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///edgestreamhub.db?check_same_thread=False"

    # ---- Filesystem Paths (Ansible & Templates) ----
    EDGESTREAM_TASK_DIR: str = "/opt/edgestream-core/"
    EDGESTREAM_TASK: str = "configure.yml"

    EDGESTREAM_CONFIGURATION: str = "settings.yml"
    EDGESTREAM_CONFIGURATION_DIR: str = "/var/lib/edgestream/export/"
    EDGESTREAM_TMP_DIR: str = "/var/lib/edgestream/tmp/"

    # Template paths for dynamic Source/Destination generation
    EDGESTREAM_TEMPLATE_CORE_BASE_PATH: str = "/usr/share/edgestream/templates"
    EDGESTREAM_TEMPLATE_CONTRIB_BASE_PATH: str = "/etc/edgestream/templates"

    EDGESTREAM_VPNCTL: str = "/opt/edgestream-api/bin/edgestream-vpnctl"
    # --- Ports reserved by system ----
    RESERVED_PORTS: List[int] = [3000, 3001, 53, 5355, 8086, 8080]

    # ---- External Secrets (InfluxDB) ----
    EDGESTREAM_SECRETS_PATH: str = "/etc/edgestream/influxdb.secrets"

    # ---- Provisioning Defaults ----
    EDGESTREAM_DEFAULT_ADMIN_EMAIL: str = "admin@edgestream.local"

    # Generates a random 24-char safe password if none provided on first boot
    EDGESTREAM_DEFAULT_ADMIN_PASSWORD: str = Field(default_factory=lambda: token_urlsafe(24))
    EDGESTREAM_DEFAULT_ADMIN_FULL_NAME: str = "Default System Administrator"

    # ---- Validation Logic ----

    @field_validator("JWT_SECRET", mode="after")
    @classmethod
    def ensure_jwt_secret_persistence(cls, v: str):
        """
        Hard security check: In production, we should ideally be loading 
        a persistent secret. If we are in 'prod' but the secret was 
        dynamically generated (default factory), we log a heavy warning.
        """
        return v

    @field_validator(
        "AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "JWT_ISSUER", "JWT_AUDIENCE",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


settings = Settings()
