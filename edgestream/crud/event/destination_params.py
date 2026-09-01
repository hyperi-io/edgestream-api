"""
Project:   edgestream-api
File:      edgestream/crud/event/destination_params.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select, delete
from fastapi import HTTPException
import json

from edgestream.crud.base import CRUDBase
from edgestream.models.event.destination import Destination, DestinationParameter
from edgestream.schemas.event.destination_parameter import (
    DestinationParameterCreate,
    DestinationParameterUpdate
)


def serialize_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return value


class CRUDDestinationParameter(CRUDBase[DestinationParameter, DestinationParameterCreate, DestinationParameterUpdate]):

    def get(self, db: Session, id: int) -> Optional[DestinationParameter]:
        return db.get(DestinationParameter, id)

    def get_by_destination_id(self, db: Session, destination_id: int) -> List[DestinationParameter]:
        return list(
            db.execute(
                select(DestinationParameter).where(DestinationParameter.destination_id == destination_id)
            ).scalars().all()
        )

    def get_by_key(self, db: Session, destination_name: str, key: str) -> Optional[DestinationParameter]:
        dest = db.execute(
            select(Destination).where(Destination.name.ilike(destination_name))
        ).scalar_one_or_none()

        if not dest:
            raise HTTPException(status_code=404, detail=f"Destination '{destination_name}' not found.")

        return db.execute(
            select(DestinationParameter).where(
                DestinationParameter.destination_id == dest.id,
                DestinationParameter.key.ilike(key)
            )
        ).scalar_one_or_none()

    def create(self, db: Session, *, obj_in: DestinationParameterCreate) -> DestinationParameter:
        try:
            data = obj_in.model_dump()
            data["value"] = serialize_value(data.get("value"))

            db_obj = DestinationParameter(**data)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except (IntegrityError, SQLAlchemyError):
            db.rollback()
            raise

    def update(
            self, db: Session, *, db_obj: DestinationParameter, obj_in: DestinationParameterUpdate
    ) -> DestinationParameter:
        data = obj_in.model_dump(exclude_unset=True)

        if "value" in data:
            data["value"] = serialize_value(data["value"])

        for k, v in data.items():
            setattr(db_obj, k, v)

        try:
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except (IntegrityError, SQLAlchemyError):
            db.rollback()
            raise

    def delete_by_destination_id(self, db: Session, destination_id: int) -> int:
        try:
            result = db.execute(
                delete(DestinationParameter).where(DestinationParameter.destination_id == destination_id)
            )
            db.commit()
            return result.rowcount
        except SQLAlchemyError:
            db.rollback()
            raise


destination_parameter = CRUDDestinationParameter(DestinationParameter)
