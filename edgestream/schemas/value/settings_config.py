from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal, Union
from pydantic import BaseModel, Field, ConfigDict


# ---------- Domain blocks ----------
class System(BaseModel):
    hostname: str
    timezone: str
    org_id: str
    site_id: str

    model_config = ConfigDict(from_attributes=True)


class Backup(BaseModel):
    enabled: bool = False
    provider: Literal["file", "s3", "gcs"] = "file"
    path: str = ""
    bucket_name: str = ""
    region: str = ""

    # Credentials/Endpoints added here to match the "unfilled" logic
    endpoint_url: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""
    gcs_project_id: str = ""
    gcs_credentials_json: str = ""

    retention: str = "30d"
    schedule: str = "12h"

    model_config = ConfigDict(from_attributes=True)


# ---------- Root export envelope ----------
class Configuration(BaseModel):
    version: int = 1

    system: Union[System, Dict[str, Any]] = Field(default_factory=dict)

    networks: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)

    sources: List[Dict[str, Any]] = Field(default_factory=list)
    transforms: List[Dict[str, Any]] = Field(default_factory=list)
    destinations: List[Dict[str, Any]] = Field(default_factory=list)

    certificates: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)

    vpn: List[Dict[str, Any]] = Field(default_factory=list)

    advanced: Dict[str, str] = Field(default_factory=dict)

    logs: List[Dict[str, Any]] = Field(default_factory=list)

    backup: Optional[Union[Backup, Dict[str, Any]]] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra='ignore'
    )
