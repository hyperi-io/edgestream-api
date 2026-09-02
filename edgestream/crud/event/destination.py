"""
Project:   edgestream-api
File:      edgestream/crud/event/destination.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List, Dict, Tuple, Any, Optional
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, select
import json

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.event.destination import Destination, DestinationParameter, DestinationRoute
from edgestream.schemas.event.destination import DestinationCreate, DestinationUpdate


def _serialize_value(v: Any) -> Any:
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    return v


class CRUDDestination(CRUDBase[Destination, DestinationCreate, DestinationUpdate]):

    def get(self, db: Session, name: str) -> Optional[Destination]:
        return db.execute(
            select(Destination).where(Destination.name.ilike(name))
        ).scalar_one_or_none()

    def get_by_id(self, db: Session, id: int) -> Optional[Destination]:
        return db.get(Destination, id)

    def get_all(self, db: Session) -> List[Destination]:
        return list(
            db.execute(
                select(Destination).options(selectinload(Destination.parameters))
            ).scalars().all()
        )

    def count_enabled(self, db: Session) -> int:
        return db.execute(
            select(func.count(Destination.id)).where(Destination.enabled.is_(True))
        ).scalar() or 0

    def export(self, db: Session) -> List[Dict[str, Any]]:
        """Standardized export using destination name for routing."""
        items = db.execute(
            select(Destination)
            .options(
                selectinload(Destination.parameters),
                selectinload(Destination.routes)
            )
        ).scalars().all()

        return [
            {
                "name": d.name,
                "type": d.type,
                "enabled": bool(d.enabled),
                "system": bool(d.system),
                "fallback": bool(d.fallback),
                "settings": {p.key: p.value for p in d.parameters if p.value is not None},
                "routes": [r.label for r in d.routes]
            }
            for d in items
        ]

    def create(self, db: Session, *, obj_in: DestinationCreate) -> Tuple[Destination, Dict[str, Any]]:
        try:
            db_obj = Destination(
                name=obj_in.name,
                type=obj_in.type,
                enabled=bool(obj_in.enabled),
                system=bool(obj_in.system),
                fallback=bool(obj_in.fallback),
            )

            # Process Routes
            seen_routes = set()
            for label in (obj_in.routes or []):
                label = (label or "").strip()
                if label and label not in seen_routes:
                    db_obj.routes.append(DestinationRoute(label=label))
                    seen_routes.add(label)

            # Process Settings
            seen_keys = set()
            for setting in (obj_in.settings or []):
                key = (setting.key or "").strip()
                if not key or key in seen_keys or setting.value is None:
                    continue

                val = _serialize_value(setting.value)
                db_obj.parameters.append(DestinationParameter(key=key, value=val))
                seen_keys.add(key)

            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj, {"parameters": db_obj.parameters}

        except IntegrityError as e:
            db.rollback()
            Logger.logger.error(f"Integrity error creating destination: {e}")
            raise HTTPException(status_code=400, detail="Destination or parameter constraint violation.")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"DB error creating destination: {e}")
            raise HTTPException(status_code=500, detail="Database error during destination creation.")

    def update(self, db: Session, *, db_obj: Destination, obj_in: DestinationUpdate) -> Tuple[Destination, Dict[str, Any]]:
        if obj_in.type and db_obj.type != obj_in.type:
            raise HTTPException(status_code=400, detail="Changing type is unsupported.")

        try:
            for field in ["system", "enabled", "fallback", "name"]:
                val = getattr(obj_in, field, None)
                if val is not None:
                    setattr(db_obj, field, val)

            if obj_in.routes is not None:
                for old_route in list(db_obj.routes):
                    db.delete(old_route)
                    db_obj.routes.remove(old_route)
                db.flush()

                seen_routes = set()
                for label in obj_in.routes:
                    label = (label or "").strip()
                    if label and label not in seen_routes:
                        db_obj.routes.append(DestinationRoute(label=label))
                        seen_routes.add(label)

            if obj_in.settings is not None:
                for old_param in list(db_obj.parameters):
                    db.delete(old_param)
                db_obj.parameters.clear()
                db.flush()

                seen_keys = set()
                for setting in obj_in.settings:
                    key = (setting.key or "").strip()
                    if not key or key in seen_keys or setting.value is None:
                        continue

                    val = _serialize_value(setting.value)
                    db_obj.parameters.append(DestinationParameter(key=key, value=val))
                    seen_keys.add(key)

            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj, {"parameters": db_obj.parameters}

        except IntegrityError as e:
            db.rollback()
            raise HTTPException(status_code=400, detail="Uniqueness violation updating destination.")
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Database error during update.")

    def delete_by_name(self, db: Session, *, name: str) -> None:
        db_obj = self.get(db, name)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Destination not found.")
        try:
            db.delete(db_obj)
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=400, detail="Error deleting destination.")


destination = CRUDDestination(Destination)
