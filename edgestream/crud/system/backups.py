from typing import Any, Dict, Optional, Union, List
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.system.backup import Backup
from edgestream.schemas.system.backup import BackupUpdate, BackupCreate


class CRUDBackup(CRUDBase[Backup, BackupCreate, BackupUpdate]):
    """
    CRUD operations for system backup configurations (File, S3, GCS).
    """

    def export(self, db: Session) -> Dict[str, Dict[str, Any]]:
        """
        Unified export method for the Configuration Exporter.
        Returns a dictionary of backup configurations keyed by provider.
        """
        rows = self.get_all(db)
        return {
            row.provider.lower(): {
                "enabled": bool(row.enabled),
                "path": row.path or "",
                "bucket_name": row.bucket_name or "",
                "region": row.region or "",
                "retention": row.retention or "30d",
                "schedule": row.schedule or "12h",
                "access_key_id": row.access_key_id or "",
                "secret_access_key": row.secret_access_key or "",
                "endpoint_url": row.endpoint_url or "",
                "gcs_project_id": row.gcs_project_id or "",
                "gcs_credentials_json": row.gcs_credentials_json or "",
            }
            for row in rows
        }

    def get_backup(self, db: Session) -> Optional[Backup]:
        """Retrieves the first backup configuration found (legacy singleton behavior)."""
        return db.execute(select(Backup)).scalars().first()

    def get_all(self, db: Session) -> List[Backup]:
        """Retrieves all backup configurations ordered by provider name."""
        return list(
            db.execute(
                select(Backup).order_by(Backup.provider.asc())
            ).scalars().all()
        )

    def get_by_provider(self, db: Session, provider: str) -> Optional[Backup]:
        """Retrieves a backup configuration for a specific provider."""
        return db.execute(
            select(Backup).where(Backup.provider == provider)
        ).scalars().first()

    def upsert_by_provider(self, db: Session, provider: str, obj_in: Union[BackupUpdate, Dict[str, Any]]) -> Backup:
        """
        Updates an existing provider configuration or creates a new one if it doesn't exist.
        """
        row = self.get_by_provider(db, provider)

        if hasattr(obj_in, "model_dump"):
            data = obj_in.model_dump(exclude_unset=True)
        else:
            data = dict(obj_in)

        data["provider"] = provider.lower()  # Normalize case

        if row:
            return super().update(db=db, db_obj=row, obj_in=data)

        try:
            return super().create(db=db, obj_in=BackupCreate(**data))
        except IntegrityError:
            db.rollback()
            row = self.get_by_provider(db, provider)
            if row:
                return super().update(db=db, db_obj=row, obj_in=data)
            raise

    def list_enabled(self, db: Session) -> List[Backup]:
        """Returns all backup targets currently marked as enabled."""
        return list(
            db.execute(
                select(Backup).where(Backup.enabled == True)
            ).scalars().all()
        )

    def create(self, db: Session, *, obj_in: BackupCreate) -> Backup:
        """
        Specialized create that ensures only one config per provider.
        """
        existing = self.get_by_provider(db, obj_in.provider)
        if existing:
            return self.update(db, db_obj=existing, obj_in=obj_in)

        try:
            db_obj = Backup(**obj_in.model_dump())
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError as e:
            db.rollback()
            Logger.logger.error(f"Failed to create backup row for {obj_in.provider}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Backup configuration for provider '{obj_in.provider}' already exists."
            ) from e


backup = CRUDBackup(Backup)
