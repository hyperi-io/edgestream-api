"""
Project:   edgestream-api
File:      edgestream/models/system/audit.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Any, Dict

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, func, JSON as SA_JSON
from sqlalchemy.types import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB
from edgestream.db.session import Base


class JSONBCompat(TypeDecorator):
    """
    Uses JSONB on PostgreSQL, generic JSON elsewhere (SQLite/MySQL).
    """
    impl = SA_JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(SA_JSON())


class AuditEvent(Base):
    """System-wide audit logging for security and compliance tracking."""
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        comment="Event occurrence timestamp"
    )

    event_type: Mapped[str] = mapped_column(String(64), index=True)  # e.g. login_success
    result: Mapped[Optional[str]] = mapped_column(String(16))  # success|failure

    # Identity and Target
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    actor_type: Mapped[Optional[str]] = mapped_column(String(32))

    subject_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    subject_type: Mapped[Optional[str]] = mapped_column(String(32))

    # Request Metadata
    request_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(String(256))
    route: Mapped[Optional[str]] = mapped_column(String(128))
    method: Mapped[Optional[str]] = mapped_column(String(8))
    status_code: Mapped[Optional[int]] = mapped_column(Integer)

    # Contextual Data
    reason: Mapped[Optional[str]] = mapped_column(String(256))
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONBCompat,
        comment="Arbitrary JSON payload with event details"
    )

    def __repr__(self) -> str:
        return f"<AuditEvent(event_type={self.event_type}, actor={self.actor_id}, result={self.result})>"
