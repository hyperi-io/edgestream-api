"""
Project:   edgestream-api
File:      edgestream/crud/event/destination_routes.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select, delete, update
from fastapi import HTTPException

from edgestream.crud.base import CRUDBase
from edgestream.models.event.destination import DestinationRoute
from edgestream.schemas.event.destination_route import DestinationRouteCreate, DestinationRouteUpdate


class CRUDDestinationRoute(CRUDBase[DestinationRoute, DestinationRouteCreate, DestinationRouteUpdate]):

    def get(self, db: Session, id: int) -> Optional[DestinationRoute]:
        """Retrieve a destination route by its primary key id."""
        return db.get(DestinationRoute, id)

    def get_by_destination_id(self, db: Session, destination_id: int) -> List[DestinationRoute]:
        """Retrieve all routes for a given destination id."""
        return list(
            db.execute(
                select(DestinationRoute)
                .where(DestinationRoute.destination_id == destination_id)
                .order_by(DestinationRoute.id.asc())
            ).scalars().all()
        )

    def get_by_label(self, db: Session, label: str, destination_id: Optional[int] = None) -> List[DestinationRoute]:
        """Retrieve routes by label. Optionally scope to a destination."""
        stmt = select(DestinationRoute).where(DestinationRoute.label == label)
        if destination_id is not None:
            stmt = stmt.where(DestinationRoute.destination_id == destination_id)

        return list(db.execute(stmt.order_by(DestinationRoute.id.asc())).scalars().all())

    def replace(self, db: Session, destination_id: int, old_label: str, new_label: str) -> int:
        """Swap a label for a specific destination."""
        old_label, new_label = (old_label or "").strip(), (new_label or "").strip()
        if not old_label or not new_label:
            raise HTTPException(status_code=400, detail="Labels cannot be empty.")

        conflict = db.execute(
            select(DestinationRoute).where(
                DestinationRoute.destination_id == destination_id,
                DestinationRoute.label == new_label
            )
        ).scalar_one_or_none()

        if conflict:
            raise HTTPException(status_code=400, detail=f"Label '{new_label}' already exists.")

        result = db.execute(
            update(DestinationRoute)
            .where(DestinationRoute.destination_id == destination_id, DestinationRoute.label == old_label)
            .values(label=new_label)
        )

        try:
            db.commit()
            return result.rowcount
        except (IntegrityError, SQLAlchemyError) as e:
            db.rollback()
            raise HTTPException(status_code=400, detail="Error during label replacement") from e

    def update(self, db: Session, *, db_obj: DestinationRoute, obj_in: DestinationRouteUpdate) -> DestinationRoute:
        """Update a specific route record."""
        update_data = obj_in.model_dump(exclude_unset=True)
        new_label = update_data.get("label")

        if new_label and new_label != db_obj.label:
            conflict = db.execute(
                select(DestinationRoute).where(
                    DestinationRoute.destination_id == db_obj.destination_id,
                    DestinationRoute.label == new_label,
                    DestinationRoute.id != db_obj.id
                )
            ).scalar_one_or_none()

            if conflict:
                raise HTTPException(status_code=400, detail=f"Label '{new_label}' already exists.")
            db_obj.label = new_label

        try:
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except (IntegrityError, SQLAlchemyError) as e:
            db.rollback()
            raise HTTPException(status_code=400, detail="Update failed due to constraint violation") from e

    def delete_by_label(self, db: Session, label: str, destination_id: Optional[int] = None) -> int:
        """Delete routes by label."""
        stmt = delete(DestinationRoute).where(DestinationRoute.label == label)
        if destination_id is not None:
            stmt = stmt.where(DestinationRoute.destination_id == destination_id)

        try:
            result = db.execute(stmt)
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"No routes found with label '{label}'")
            db.commit()
            return result.rowcount
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Error during deletion") from e

    def delete_by_destination_id(self, db: Session, destination_id: int) -> int:
        """Delete all routes for a specific destination."""
        try:
            result = db.execute(
                delete(DestinationRoute).where(DestinationRoute.destination_id == destination_id)
            )
            db.commit()
            return result.rowcount
        except SQLAlchemyError:
            db.rollback()
            raise

    def replace_global(self, db: Session, old_label: str, new_label: str) -> int:
        """Global find-and-replace for a label across all destinations, with deduping."""
        rows = db.execute(
            select(DestinationRoute).where(DestinationRoute.label == old_label)
        ).scalars().all()

        if not rows:
            return 0

        changed = 0
        try:
            for r in rows:
                conflict = db.execute(
                    select(DestinationRoute).where(
                        DestinationRoute.destination_id == r.destination_id,
                        DestinationRoute.label == new_label
                    )
                ).scalar_one_or_none()

                if conflict:
                    db.delete(r)  # Dedupe: delete old if new already exists
                else:
                    r.label = new_label
                changed += 1

            db.commit()
            return changed
        except (IntegrityError, SQLAlchemyError) as e:
            db.rollback()
            raise HTTPException(status_code=500, detail="Global replace failed") from e


destination_route = CRUDDestinationRoute(DestinationRoute)
