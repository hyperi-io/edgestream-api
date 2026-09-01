"""
Project:   edgestream-api
File:      edgestream/schemas/network/ip_management.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

from typing import Optional
import ipaddress

from pydantic import Field, field_validator, model_validator
from edgestream.schemas.base import ESBaseModel


class IPMgmtRecord(ESBaseModel):
    """
    Representation of a single network interface configuration.
    Supports both static and DHCP assignment.
    """
    iface: str = Field(default="", description="The OS device name (e.g., eth0).")
    mac_address: str = Field(default="", description="Hardware MAC address.")
    family: str = Field(default="ipv4", description="Address family: 'ipv4' or 'ipv6'.")
    dhcp: bool = Field(default=False, description="Enable DHCP for this interface.")
    ip_address: Optional[str] = Field(None, description="Static IP address.")
    netmask: Optional[str] = Field(None, description="Subnet mask.")
    gateway: Optional[str] = Field(None, description="Default gateway IP.")
    default: bool = Field(default=False, description="Whether this is the system default route.")

    @field_validator("family", mode="before")
    @classmethod
    def check_family(cls, v: str) -> str:
        if v is None or str(v).strip() == "":
            return "ipv4"
        s = str(v).lower().strip()
        if s not in {"ipv4", "ipv6"}:
            raise ValueError("Invalid IP family. Must be one of ['ipv4', 'ipv6'].")
        return s

    @field_validator("gateway", mode="before")
    @classmethod
    def check_gateway(cls, v: Optional[str]) -> Optional[str]:
        # Treat "", "null", None as not set
        if v in (None, "", "null"):
            return None
        s = str(v).strip()
        try:
            ipaddress.ip_address(s)
        except ValueError as e:
            raise ValueError(f"Invalid gateway format: {e}")
        return s

    @model_validator(mode="after")
    def validate_static_vs_dhcp(self) -> IPMgmtRecord:
        """
        Ensures that static configurations have the necessary IP/Mask info.
        """
        # If DHCP is False (Static mode), we require IP and Mask
        if not self.dhcp:
            ip = (self.ip_address or "").strip()
            mask = (self.netmask or "").strip()

            if not ip:
                raise ValueError("ip_address is required for static configurations.")
            if not mask:
                raise ValueError("netmask is required for static configurations.")

            # Validate the static IP format
            try:
                ipaddress.ip_address(ip)
            except ValueError as e:
                raise ValueError(f"Invalid static IP address: {e}")

        return self


class IPMgmt(ESBaseModel):
    """
    Container for dual-interface management (Management and Event streams).
    """
    mgmt: Optional[IPMgmtRecord] = Field(None, description="Primary management interface settings.")
    event: Optional[IPMgmtRecord] = Field(None, description="Secondary event/data interface settings.")


class IPMgmtCreate(IPMgmt):
    """Schema for creating interface records."""
    pass


class IPMgmtUpdate(IPMgmt):
    """Schema for updating interface records."""
    pass


class IPMgmtResponse(IPMgmt):
    """Schema for API responses returning interface state."""
    pass


class IPMgmtDelete(ESBaseModel):
    """Used to clear a specific interface configuration."""
    ip_type: str = Field(..., description="The interface role to delete: 'mgmt' or 'event'.")

    @field_validator("ip_type", mode="before")
    @classmethod
    def check_ip_type(cls, v: str) -> str:
        s = (v or "").strip().lower()
        if s not in {"mgmt", "event"}:
            raise ValueError("ip_type must be 'mgmt' or 'event'.")
        return s
