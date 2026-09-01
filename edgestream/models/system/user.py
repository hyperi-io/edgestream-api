"""
Project:   edgestream-api
File:      edgestream/models/system/user.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base

class User(Base):
    """System user accounts and authentication data."""
    __tablename__ = "users"  # Standardized to plural

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        index=True,
        comment="Unique identifier for the user"
    )

    # Profile Information
    full_name: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Full name"
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String(256),
        nullable=True,
        comment="Display name (Optional override)"
    )

    # Authentication
    email: Mapped[str] = mapped_column(
        String(256),
        unique=True,
        nullable=False,
        index=True,
        comment="User's email address (normalized to lowercase)"
    )
    hashed_password: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Hashed password for the user"
    )
    otp_secret: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        comment="Optional OTP secret for 2FA"
    )

    # Permissions & Status
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag to indicate if the user is a superuser"
    )
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag to indicate if the user is approved"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        comment="Timestamp when the user was created"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        comment="Timestamp of the last update"
    )

    # Indexes
    __table_args__ = (
        Index("ix_users_approved_created", "is_approved", "created_at"),
        Index("ix_users_superuser", "is_superuser"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, superuser={self.is_superuser})>"
