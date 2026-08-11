from typing import List, Optional, Any, Dict
import json

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.event.transform import Transform
from edgestream.schemas.event.transform import TransformCreate, TransformUpdate
from edgestream.services.vrl_parser import parse_condition


class CRUDTransform(CRUDBase[Transform, TransformCreate, TransformUpdate]):

    def get(self, db: Session, name: str) -> Optional[Transform]:
        """Retrieve a transform by name (case-insensitive)."""
        if not name:
            return None
        return db.execute(
            select(Transform).where(func.lower(Transform.name) == name.lower())
        ).scalar_one_or_none()

    def get_by_id(self, db: Session, id: int) -> Optional[Transform]:
        """Retrieve a transform by primary key."""
        return db.get(Transform, id)

    def get_all(self, db: Session) -> List[Transform]:
        """Retrieve all transforms ordered by name."""
        return list(
            db.execute(
                select(Transform).order_by(Transform.name.asc())
            ).scalars().all()
        )

    def export(self, db: Session) -> List[Dict[str, Any]]:
        """
        Export transforms with VRL parsing for query_builder types.
        """
        out: List[Dict[str, Any]] = []
        transforms = self.get_all(db)

        for t in transforms:
            vrl_condition = t.query_raw

            # If it's a builder-based query parse it to VRL for the export
            if (t.query_syntax or "").lower() == "query_builder" and t.query_builder:
                try:
                    qb = json.loads(t.query_builder)
                    vrl_condition = parse_condition(qb)
                except Exception as e:
                    Logger.logger.error(f"VRL parse failed for transform '{t.name}': {e}")
                    vrl_condition = None

            out.append({
                "name": t.name,
                "description": t.description,
                "type": t.type,
                "parent": t.parent,
                "query_syntax": t.query_syntax,
                "query_builder": t.query_builder,
                "query_raw": vrl_condition,
                "enabled": t.enabled,
            })
        return out

    def create(self, db: Session, *, obj_in: TransformCreate) -> Transform:
        """Create a new transform record."""
        try:
            data = obj_in.model_dump()
            db_obj = Transform(**data)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="Transform with this name already exists.")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"Transform creation failed: {e}")
            raise HTTPException(status_code=500, detail="Database error during creation.")

    def update(self, db: Session, *, db_obj: Transform, obj_in: TransformUpdate) -> Transform:
        """Update an existing transform with business logic guards."""
        update_data = obj_in.model_dump(exclude_unset=True)

        # Business Logic Guards
        if "type" in update_data and update_data["type"] != db_obj.type:
            raise HTTPException(status_code=400, detail="Changing transform type is unsupported.")

        if "name" in update_data and update_data["name"] != db_obj.name:
            raise HTTPException(status_code=400, detail="Renaming transforms is unsupported.")

        try:
            for field, value in update_data.items():
                setattr(db_obj, field, value)

            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="Transform name must be unique.")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"Transform update failed: {e}")
            raise HTTPException(status_code=500, detail="Database error during update.")

    def delete(self, db: Session, *, name: str) -> None:
        """Delete a transform by name."""
        db_obj = self.get(db, name)
        if not db_obj:
            raise HTTPException(status_code=404, detail=f"Transform '{name}' not found.")
        try:
            db.delete(db_obj)
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"Transform deletion failed: {e}")
            raise HTTPException(status_code=400, detail="Failed to delete transform.")


transform = CRUDTransform(Transform)
