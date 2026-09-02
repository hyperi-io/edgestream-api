"""
Project:   edgestream-api
File:      edgestream/models/system/backup.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base


class Backup(Base):
    """Configuration for system backup targets (File, S3, GCS)."""
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider: Mapped[str] = mapped_column(
        String(256), default="file", nullable=False, comment="Backup Provider (file|s3|gcs)"
    )
    retention: Mapped[str] = mapped_column(
        String(256), default="30d", nullable=False, comment="Retention period (e.g., 30d)"
    )
    schedule: Mapped[str] = mapped_column(
        String(256), default="12h", nullable=False, comment="Cron or interval schedule"
    )

    bucket_name: Mapped[Optional[str]] = mapped_column(
        String(256), default="edgestream", nullable=True
    )
    path: Mapped[Optional[str]] = mapped_column(
        String(1024), default="", nullable=True
    )
    region: Mapped[Optional[str]] = mapped_column(
        String(256), default="", nullable=True
    )

    # Credentials
    access_key_id: Mapped[Optional[str]] = mapped_column(
        String(256), default="local", nullable=True
    )
    secret_access_key: Mapped[Optional[str]] = mapped_column(
        String(256), default="local", nullable=True
    )

    # Cloud Specific Extensions
    endpoint_url: Mapped[Optional[str]] = mapped_column(
        String(512), default="", nullable=True, comment="S3-compatible endpoint"
    )
    gcs_project_id: Mapped[Optional[str]] = mapped_column(
        String(256), default="", nullable=True
    )
    gcs_credentials_json: Mapped[Optional[str]] = mapped_column(
        String(8192), default="", nullable=True, comment="GCS Credentials JSON"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("provider", name="uq_backup_provider"),
    )

    def __repr__(self) -> str:
        return f"<Backup(provider={self.provider}, enabled={self.enabled})>"
