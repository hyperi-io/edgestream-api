from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base


class StaticRoute(Base):
    """Static network routing entries for the system routing table."""
    __tablename__ = "networks_static_routes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)

    # All fields required for a valid OS route command
    to: Mapped[str] = mapped_column(
        String(45), nullable=False, comment="Destination network/address (CIDR)"
    )
    via: Mapped[str] = mapped_column(
        String(45), nullable=False, comment="Gateway address (Next hop)"
    )
    device: Mapped[str] = mapped_column(
        String(45), nullable=False, comment="Network interface (e.g., eth0)"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("to", "via", "device", name="uq_networks_static_route_to_via_device"),
    )

    def __repr__(self) -> str:
        return f"<StaticRoute(to={self.to}, via={self.via}, device={self.device})>"
