"""
Project:   edgestream-api
File:      edgestream/models/network/ip_management.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base


class IPManagement(Base):
    """Configuration for system network interfaces and IP assignment."""
    __tablename__ = "networks_ip_managements"  # Pluralized for consistency

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
        autoincrement=True
    )

    # Interface Metadata
    type: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        comment="Type of interface (e.g., mgmt, event)"
    )
    iface: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        comment="Interface name (e.g., eth0)"
    )
    mac_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="MAC Address"
    )
    family: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        comment="IP family (e.g., ipv4, ipv6)"
    )

    # Configuration Logic
    dhcp: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag to use DHCP instead of static configuration"
    )

    # Static IP Details (Null if DHCP is enabled)
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="Assigned IP address"
    )
    netmask: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="Subnet mask"
    )
    gateway: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="Gateway address"
    )

    # Routing
    default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Default outbound interface"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        comment="Timestamp when the entry was created"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        comment="Timestamp when the entry was last updated"
    )

    def __repr__(self) -> str:
        return f"<IPManagement(iface={self.iface}, type={self.type}, dhcp={self.dhcp})>"
