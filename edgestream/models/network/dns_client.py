"""
Project:   edgestream-api
File:      edgestream/models/network/dns_client.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base


class DNS(Base):
    """Configuration for system DNS resolvers."""
    __tablename__ = "networks_dns_servers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
        autoincrement=True
    )
    ip_address: Mapped[str] = mapped_column(
        String(254),
        nullable=False,
        comment="DNS server IP address"
    )
    port: Mapped[int] = mapped_column(
        Integer,
        default=53,
        nullable=False,
        comment="Port for DNS server (default: 53)"
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

    __table_args__ = (
        UniqueConstraint("ip_address", "port", name="uq_networks_dns_ip_port"),
    )

    def __repr__(self) -> str:
        return f"<DNS(ip_address={self.ip_address}, port={self.port})>"
