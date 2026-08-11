from typing import Any, Dict, Generic, Optional, Type, TypeVar, Union, List

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select, delete, asc
from sqlalchemy.orm import Session

from edgestream.db.session import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**
        * `model`: A SQLAlchemy model class
        """
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """Fetch a single record by primary key."""
        return db.get(self.model, id)

    def get_multi(
            self, db: Session, *, skip: int = 0, limit: int = 5000
    ) -> List[ModelType]:
        """Fetch multiple records with pagination and explicit ordering."""
        statement = select(self.model).order_by(asc(self.model.id)).offset(skip).limit(limit)
        return list(db.execute(statement).scalars().all())

    def get_all(self, db: Session) -> List[ModelType]:
        """Fetch all records for a model."""
        return list(db.execute(select(self.model)).scalars().all())

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record, ensuring JSON-compatible serialization."""
        obj_in_data = jsonable_encoder(obj_in.model_dump())

        db_obj = self.model(**obj_in_data)  # type: ignore
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
            self,
            db: Session,
            *,
            db_obj: ModelType,
            obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        Standardized update logic.
        Ensures that unset fields in the schema are not overwritten in the DB.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: Any) -> Optional[ModelType]:
        """Alias for delete logic."""
        obj = db.get(self.model, id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj

    def delete(self, db: Session, *, id: Any) -> Optional[ModelType]:
        """Standard delete wrapper."""
        return self.remove(db, id=id)

    def delete_all(self, db: Session) -> int:
        """
        Bulk delete all records
        """
        result = db.execute(delete(self.model))
        db.commit()
        return result.rowcount
