from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base


class DNSForwarder(Base):
    """Configuration for domain-specific DNS forwarding rules."""
    __tablename__ = "networks_dns_forwarders"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
        autoincrement=True
    )
    domain: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="Domain name to forward requests for"
    )
    ip_address: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
        comment="Forwarding server IP address"
    )
    port: Mapped[int] = mapped_column(
        Integer,
        default=53,
        nullable=False,
        comment="Port for forwarding server (default: 53)"
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
        return f"<DNSForwarder(domain={self.domain}, forward_to={self.ip_address}:{self.port})>"
