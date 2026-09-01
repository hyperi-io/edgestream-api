"""
Project:   edgestream-api
File:      edgestream/schemas/network/vpn_client.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

from fastapi import HTTPException, status
import ipaddress
import re
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Literal, List

from pydantic import Field, field_validator, model_validator, RootModel

from edgestream.schemas.base import ESBaseModel

VPN_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]$")

def validate_safe_name(v: str) -> str:
    """Shared utility to enforce safe VPN names across all schemas."""
    if not VPN_NAME_RE.match(v):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid VPN name. Must be alphanumeric and hyphens only (3-63 chars)."
        )
    return v

class VPNType(str, Enum):
    openvpn = "openvpn"
    wireguard = "wireguard"

class MTUMode(str, Enum):
    auto = "auto"
    custom = "custom"

class MSSMode(str, Enum):
    auto = "auto"
    custom = "custom"
    off = "off"

# -------- Request Models --------

class VPNRunRequest(ESBaseModel):
    name: str = Field(..., description="The unique name of the VPN profile.")
    action: Literal["start", "stop", "restart"]

    @field_validator("name")
    @classmethod
    def name_must_be_safe(cls, v: str) -> str:
        return validate_safe_name(v)

class VPNDeleteRequest(ESBaseModel):
    name: Optional[str] = None
    id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def name_must_be_safe(cls, v: str) -> str:
        if v is not None:
            return validate_safe_name(v)
        return v

class VPNRoute(ESBaseModel):
    dst: str = Field(..., description="CIDR or IP, e.g. 1.2.3.4/32 or 10.0.0.0/8")
    proto: Literal["tcp", "udp", "any"] = "any"
    ports: Optional[str] = Field(
        default=None,
        description='Port list or range: "443", "80,443", "1000-2000"',
    )
    comment: Optional[str] = None

    @model_validator(mode="after")
    def _validate_dst(self) -> "VPNRoute":
        try:
            if "/" in self.dst:
                ipaddress.ip_network(self.dst, strict=False)
            else:
                ipaddress.ip_address(self.dst)
        except Exception:
            raise ValueError("dst must be a valid IP or CIDR")
        return self

class VPNAdvancedSettings(ESBaseModel):
    mtu_mode: MTUMode = MTUMode.custom
    mtu_value: Optional[int] = 1420
    mss_mode: MSSMode = MSSMode.custom
    mss_value: Optional[int] = 1380

    @model_validator(mode="after")
    def _validate_modes(self) -> "VPNAdvancedSettings":
        if self.mtu_mode == MTUMode.custom:
            if self.mtu_value is None:
                raise ValueError("mtu_value is required when mtu_mode=custom")
            if not (576 <= self.mtu_value <= 9000):
                raise ValueError("mtu_value must be between 576 and 9000")
        elif self.mtu_mode == MTUMode.auto:
            object.__setattr__(self, 'mtu_value', None)

        if self.mss_mode == MSSMode.custom:
            if self.mss_value is None:
                raise ValueError("mss_value is required when mss_mode=custom")
            if not (536 <= self.mss_value <= 8960):
                raise ValueError("mss_value must be between 536 and 8960")
        elif self.mss_mode != MSSMode.custom:
            object.__setattr__(self, 'mss_value', None)

        return self

class VPNProfileBase(ESBaseModel):
    name: str
    vpn_type: VPNType = VPNType.openvpn
    autoconnect: bool = False
    kill_switch: bool = False
    table_id: Optional[int] = None
    routes: List[VPNRoute] = Field(default_factory=list)
    advanced: VPNAdvancedSettings = Field(default_factory=VPNAdvancedSettings)

    # --- OpenVPN Credentials ---
    auth_username: Optional[str] = Field(default=None, description="OpenVPN authentication username")
    auth_password: Optional[str] = Field(default=None, description="OpenVPN authentication password")

    @field_validator("name")
    @classmethod
    def name_must_be_safe(cls, v: str) -> str:
        return validate_safe_name(v)

class VPNUploadSettings(ESBaseModel):
    vpn_type: VPNType = VPNType.openvpn
    autoconnect: bool = False
    advanced: VPNAdvancedSettings = Field(default_factory=VPNAdvancedSettings)

class VPNCreateRequest(VPNProfileBase):
    file_content: Optional[str] = Field(
        default=None,
        description="Raw configuration file content (UTF-8 string or Base64)"
    )
    filename: Optional[str] = "config.conf"

class VPNUpdateSettings(ESBaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    vpn_type: Optional[VPNType] = None
    autoconnect: Optional[bool] = None
    kill_switch: Optional[bool] = None
    table_id: Optional[int] = None
    filename: Optional[str] = None
    file_content: Optional[str] = Field(
        default=None,
        description="Raw configuration file content (UTF-8 string or Base64)"
    )
    routes: Optional[List[VPNRoute]] = None
    advanced: Optional[VPNAdvancedSettings] = None

    # --- OpenVPN Credentials ---
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_must_be_safe(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_safe_name(v)
        return v

class VPNNameRequest(ESBaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_must_be_safe(cls, v: str) -> str:
        return validate_safe_name(v)

class VPNUpdate(ESBaseModel):
    filename: Optional[str] = None

class VPNUpload(ESBaseModel):
    name: str
    filename: str = "filename.ovpn"
    vpn_type: VPNType = VPNType.openvpn
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    filesize: int = 0
    autoconnect: bool = False
    kill_switch: bool = False
    table_id: Optional[int] = None
    routes: List[VPNRoute] = Field(default_factory=list)
    advanced: VPNAdvancedSettings = Field(default_factory=VPNAdvancedSettings)

    # --- OpenVPN Credentials ---
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_must_be_safe(cls, v: str) -> str:
        return validate_safe_name(v)

class VPNUploadResponse(ESBaseModel):
    id: int
    name: str
    filename: str = "filename.ovpn"
    vpn_type: VPNType = VPNType.openvpn
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    filesize: int = 0
    autoconnect: Optional[bool] = False
    advanced: VPNAdvancedSettings = Field(default_factory=VPNAdvancedSettings)

    # --- OpenVPN Credentials ---
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None

class VPNProfileOut(ESBaseModel):
    id: int
    name: str
    vpn_type: VPNType
    autoconnect: Optional[bool] = False
    kill_switch: Optional[bool] = False
    table_id: Optional[int] = None
    routes: List[VPNRoute] = Field(default_factory=list)
    filename: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    filesize: int = 0
    advanced: VPNAdvancedSettings = Field(default_factory=VPNAdvancedSettings)

    # --- OpenVPN Credentials ---
    auth_username: Optional[str] = None
    # Password omitted intentionally for security

class VPNStatusOut(ESBaseModel):
    state: str = "unknown"
    enabled: Optional[bool] = False
    uptime_seconds: Optional[int] = None
    rx_bytes: Optional[int] = None
    tx_bytes: Optional[int] = None
    tunnel_address: Optional[str] = None
    endpoint_address: Optional[str] = None
    last_error: Optional[str] = None

class VPNStatusMapOut(RootModel):
    """
    Mapping of VPN name to its current status.
    """
    root: Dict[str, VPNStatusOut]

    def __iter__(self):
        return iter(self.root)

    def items(self):
        return self.root.items()
