from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from edgestream.db.session import Base


class Destination(Base):
    """Represents an Event Destination (Sink/Output)."""
    __tablename__ = "destinations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(256), nullable=False)
    system: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=False)
    fallback: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    routes: Mapped[List[DestinationRoute]] = relationship(
        back_populates="destination",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    parameters: Mapped[List[DestinationParameter]] = relationship(
        back_populates="destination",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DestinationParameter(Base):
    """Configuration settings for a specific Destination."""
    __tablename__ = "destination_parameters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    destination_id: Mapped[int] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    destination: Mapped[Destination] = relationship(back_populates="parameters")

    __table_args__ = (
        UniqueConstraint("destination_id", "key", name="uq_destination_parameter_key"),
    )


class DestinationRoute(Base):
    """Routing rules for a Destination."""
    __tablename__ = "destination_routes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    destination_id: Mapped[int] = mapped_column(
        ForeignKey("destinations.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(1024), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    destination: Mapped[Destination] = relationship(back_populates="routes")

    __table_args__ = (
        UniqueConstraint("destination_id", "label", name="uq_destination_route_label"),
    )
