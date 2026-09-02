"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/influx_config.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from edgestream.core.config import Logger, settings
from edgestream.models.system.user import User
from edgestream.services.auth.auth import get_current_user

router = APIRouter()


def _read_kv_file(path_input: str | Path) -> Dict[str, str]:
    """
    Safely reads a Key=Value file (like .env or secrets file).
    Skips comments and malformed lines.
    """
    data = {}
    target_path = Path(path_input)

    try:
        if not target_path.exists():
            return data

        content = target_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()

    except PermissionError:
        Logger.logger.warning("File system permission denied for path: %s", target_path)
    except Exception as e:
        Logger.logger.warning("Unexpected error reading config file at %s: %s", target_path, e)

    return data


def get_influx_secrets() -> Dict[str, Optional[str]]:
    """
    Retrieves InfluxDB credentials. 
    Prioritizes explicit environment variables over file-based secrets.
    """
    env_token = os.getenv("EDGESTREAM_WEB_UI_INFLUX_TOKEN")
    env_pass = os.getenv("EDGESTREAM_WEB_UI_INFLUX_PASSWORD")

    if (env_token and env_token.strip()) or (env_pass and env_pass.strip()):
        return {
            "token": (env_token or "").strip() or None,
            "password": (env_pass or "").strip() or None,
        }

    # Fallback to the local secrets store (KV format)
    kv = _read_kv_file(settings.EDGESTREAM_SECRETS_PATH)
    return {
        "token": kv.get("INFLUXDB_TOKEN"),
        "password": kv.get("INFLUXDB_PASSWORD"),
    }


@router.get("/", response_class=JSONResponse)
async def get_ui_config(
        current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns the frontend configuration parameters.
    Gathers InfluxDB connection details and UI behavior settings.
    """
    secrets = get_influx_secrets()

    is_admin = getattr(current_user, "is_superuser", False)

    config_payload = {
        "influxToken": secrets["token"],
        "tokenAvailable": bool(secrets["token"]),
        "influxOrg": os.getenv("EDGESTREAM_WEB_UI_INFLUX_ORG", "edgestream"),
        "influxUrl": os.getenv("EDGESTREAM_WEB_UI_INFLUX_URL", ":8086"),
        "localStorageKey": os.getenv("EDGESTREAM_WEB_UI_INFLUX_LOCAL_STORAGE_KEY", "influx_visible_series"),
        "updateInterval": int(os.getenv("EDGESTREAM_WEB_UI_INFLUX_UPDATE_INTERVAL", "5000")),
    }

    if is_admin:
        config_payload["influxPassword"] = secrets["password"]

    return config_payload
