from typing import Any, Dict, Optional, Union

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from edgestream.crud.base import CRUDBase
from edgestream.models.system.system import System
from edgestream.schemas.system.system import (
    SystemCreate,
    SystemUpdate,
    SystemOrgIDUpdate,
    SystemSiteIDUpdate,
    SystemTimezoneUpdate,
)


class CRUDSystem(CRUDBase[System, SystemCreate, SystemUpdate]):
    """
    CRUD operations for the singleton System configuration.
    Enforces a single-row policy for global appliance identity.
    """

    def export(self, db: Session) -> Dict[str, Any]:
        """
        Unified export method for the Configuration Exporter.
        Serializes the core identity of the appliance.
        """
        sys = self.get_or_create(db)
        return {
            "hostname": sys.hostname,
            "org_id": sys.org_id,
            "site_id": sys.site_id,
            "timezone": sys.timezone,
        }

    def get_system(self, db: Session) -> Optional[System]:
        """Retrieve the singleton system record."""
        return db.execute(select(System)).scalars().first()

    def get_or_create(self, db: Session) -> System:
        """
        Fetch the system row or initialize with defaults.
        Guarantees that at least one row exists.
        """
        sys = self.get_system(db)
        if sys:
            return sys

        sys = System()
        db.add(sys)
        try:
            db.commit()
            db.refresh(sys)
            return sys
        except SQLAlchemyError:
            db.rollback()
            return self.get_system(db)

    def create(self, db: Session, *, obj_in: SystemCreate) -> System:
        """
        Enforce singleton creation. If a row exists, update it instead.
        """
        existing = self.get_system(db)
        if existing:
            return self.update(db, db_obj=existing, obj_in=obj_in)

        db_obj = System(**obj_in.model_dump())
        try:
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to initialize system.") from e

    def update(
            self,
            db: Session,
            *,
            db_obj: System,
            obj_in: Union[SystemUpdate, Dict[str, Any]],
    ) -> System:
        """Update the singleton record with allow-listed fields."""
        try:
            if hasattr(obj_in, "model_dump"):
                update_data = obj_in.model_dump(exclude_unset=True)
            else:
                update_data = dict(obj_in)

            allowed = {"hostname", "site_id", "org_id", "timezone"}
            for field, value in update_data.items():
                if field in allowed:
                    setattr(db_obj, field, value)

            db.commit()
            db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update system identity.") from e

    # Convenience wrappers for specific UI actions
    def update_org_id(self, db: Session, *, db_obj: System, obj_in: SystemOrgIDUpdate) -> System:
        return self.update(db, db_obj=db_obj, obj_in={"org_id": obj_in.org_id})

    def update_site_id(self, db: Session, *, db_obj: System, obj_in: SystemSiteIDUpdate) -> System:
        return self.update(db, db_obj=db_obj, obj_in={"site_id": obj_in.site_id})

    def update_timezone(self, db: Session, *, db_obj: Session, obj_in: SystemTimezoneUpdate) -> System:
        return self.update(db, db_obj=db_obj, obj_in={"timezone": obj_in.timezone})


system = CRUDSystem(System)
