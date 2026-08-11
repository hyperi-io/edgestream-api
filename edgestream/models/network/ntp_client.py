from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base


class NTP(Base):
    """Configuration for system NTP (Network Time Protocol) servers."""
    __tablename__ = "networks_ntp_servers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
        autoincrement=True
    )
    ip_address: Mapped[str] = mapped_column(
        String(254),
        nullable=False,
        comment="NTP server IP address or hostname"
    )
    port: Mapped[int] = mapped_column(
        Integer,
        default=123,
        nullable=False,
        comment="Port for NTP server (default: 123)"
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
        UniqueConstraint("ip_address", "port", name="uq_networks_ntp_ip_port"),
    )

    def __repr__(self) -> str:
        return f"<NTP(server={self.ip_address}, port={self.port})>"
