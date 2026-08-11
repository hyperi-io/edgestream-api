from typing import Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select, delete
from fastapi import HTTPException
import json

from edgestream.crud.base import CRUDBase
from edgestream.models.event.source import Source, SourceParameter
from edgestream.schemas.event.source_parameter import SourceParameterCreate, SourceParameterUpdate


def _serialize_value(v: Any) -> Any:
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    return v


class CRUDSourceParameter(CRUDBase[SourceParameter, SourceParameterCreate, SourceParameterUpdate]):

    def get(self, db: Session, id: int) -> Optional[SourceParameter]:
        """Retrieve a parameter by its primary key ID."""
        return db.get(SourceParameter, id)

    def get_by_source_id(self, db: Session, source_id: int) -> List[SourceParameter]:
        """Retrieve all parameters associated with a specific source ID."""
        return list(
            db.execute(
                select(SourceParameter).where(SourceParameter.source_id == source_id)
            ).scalars().all()
        )

    def get_by_key(self, db: Session, source_name: str, key: str) -> Optional[SourceParameter]:
        """Retrieve a parameter by its key and the parent source name."""
        source = db.execute(
            select(Source).where(Source.name.ilike(source_name))
        ).scalar_one_or_none()

        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found.")

        param = db.execute(
            select(SourceParameter).where(
                SourceParameter.source_id == source.id,
                SourceParameter.key.ilike(key)
            )
        ).scalar_one_or_none()

        if not param:
            raise HTTPException(
                status_code=404,
                detail=f"Param '{key}' not found for source '{source_name}'."
            )
        return param

    def create(self, db: Session, *, obj_in: SourceParameterCreate) -> SourceParameter:
        """Create a new source parameter, serializing non-string values to JSON."""
        try:
            data = obj_in.model_dump()
            data["value"] = _serialize_value(data.get("value"))

            db_obj = SourceParameter(**data)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except (IntegrityError, SQLAlchemyError):
            db.rollback()
            raise

    def update(
            self, db: Session, *, db_obj: SourceParameter, obj_in: SourceParameterUpdate
    ) -> SourceParameter:
        """Update an existing source parameter."""
        data = obj_in.model_dump(exclude_unset=True)

        if "value" in data:
            data["value"] = _serialize_value(data["value"])

        for field, value in data.items():
            setattr(db_obj, field, value)

        try:
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except (IntegrityError, SQLAlchemyError):
            db.rollback()
            raise

    def delete_by_source_id(self, db: Session, source_id: int) -> int:
        """Bulk delete all parameters for a specific source."""
        try:
            result = db.execute(
                delete(SourceParameter).where(SourceParameter.source_id == source_id)
            )
            db.commit()
            return result.rowcount
        except SQLAlchemyError:
            db.rollback()
            raise


source_parameter = CRUDSourceParameter(SourceParameter)
