"""
Project:   edgestream-api
File:      edgestream/models/network/vpn_client.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
import hashlib
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    LargeBinary,
    Boolean,
    func,
    Enum as SAEnum,
    Index,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, validates
from edgestream.db.session import Base

from edgestream.schemas.network.vpn_client import VPNType, MTUMode, MSSMode

VPN_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]$")


class VPNConfig(Base):
    """Configuration and binary data for VPN clients (WireGuard, OpenVPN, etc.)."""
    __tablename__ = "vpn_configs"  # Pluralized for consistency

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    vpn_type: Mapped[VPNType] = mapped_column(
        SAEnum(VPNType), nullable=False
    )

    # File Metadata
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    filesize: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    data_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Connection Logic
    autoconnect: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # OpenVPN Credentials
    auth_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    auth_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # MTU Settings
    mtu_mode: Mapped[MTUMode] = mapped_column(
        SAEnum(MTUMode, name="vpn_mtu_mode"),
        nullable=False,
        default=MTUMode.auto,
    )
    mtu_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=1420)

    # MSS Settings
    mss_mode: Mapped[MSSMode] = mapped_column(
        SAEnum(MSSMode, name="vpn_mss_mode"),
        nullable=False,
        default=MSSMode.auto,
    )
    mss_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=1380)

    # Policy Routing
    table_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)

    # Static Routes
    routes: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_vpn_configs_type_autoconnect", "vpn_type", "autoconnect"),
        Index("ix_vpn_configs_table_id", "table_id", unique=True),
    )

    # --- Validators ---
    @validates("name")
    def validate_name(self, key, name):
        if not VPN_NAME_RE.match(name):
            raise ValueError(
                "Security Violation: VPN name contains illegal characters. "
                "Only alphanumeric characters and hyphens are permitted."
            )
        return name

    @validates("table_id")
    def validate_table_id(self, key, table_id):
        if table_id is None:
            return None
        # Linux reserved tables: 0 (unspec), 253 (default), 254 (main), 255 (local)
        if table_id in [0, 253, 254, 255]:
            raise ValueError(f"Table ID {table_id} is reserved by the Linux kernel.")
        if not (1 <= table_id <= 32768):
            raise ValueError("Table ID must be between 1 and 32768.")
        return table_id

    @validates("mtu_value", "mss_value")
    def validate_networking_values(self, key, value):
        if value is None:
            return None
        if key == "mtu_value" and not (576 <= value <= 9000):
            raise ValueError("MTU must be between 576 and 9000.")
        if key == "mss_value" and not (536 <= value <= 8960):
            raise ValueError("MSS must be between 536 and 8960.")
        return value

    # --- Helper Methods ---
    def set_data(self, blob: bytes) -> None:
        """Sets binary data and automatically calculates metadata."""
        self.data = blob
        self.filesize = len(blob)
        self.data_sha256 = hashlib.sha256(blob).hexdigest()

    def __repr__(self) -> str:
        return f"<VPNConfig(name={self.name}, type={self.vpn_type}, autoconnect={self.autoconnect})>"
