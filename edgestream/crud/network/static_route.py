"""
Project:   edgestream-api
File:      edgestream/crud/network/static_route.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select, and_

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.network.static_route import StaticRoute as StaticRouteModel
from edgestream.schemas.network.static_route import (
    StaticRouteCreate,
    StaticRouteUpsert,
)


class CRUDStaticRoute(CRUDBase[StaticRouteModel, StaticRouteCreate, StaticRouteUpsert]):

    def export(self, db: Session) -> List[Dict[str, Any]]:
        """
        Standardized export method for the Configuration Exporter.
        """
        rows = db.execute(
            select(StaticRouteModel).order_by(StaticRouteModel.id.asc())
        ).scalars().all()

        return [
            {
                "to": r.to,
                "via": r.via,
                "device": r.device
            }
            for r in rows
        ]

    def get_by_triplet(
            self, db: Session, *, to: str, via: str, device: str
    ) -> Optional[StaticRouteModel]:
        """Fetch a specific route by the destination/gateway/interface triplet."""
        return db.execute(
            select(self.model).where(
                and_(
                    self.model.to == to,
                    self.model.via == via,
                    self.model.device == device,
                )
            )
        ).scalar_one_or_none()

    def create(self, db: Session, *, obj_in: StaticRouteCreate) -> StaticRouteModel:
        try:
            rec = StaticRouteModel(to=obj_in.to, via=obj_in.via, device=obj_in.device)
            db.add(rec)
            db.commit()
            db.refresh(rec)
            return rec
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Static route already exists")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"StaticRoutes create failed: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create static route")

    def upsert_by_triplet(
            self,
            db: Session,
            *,
            current_to: str,
            current_via: str,
            current_device: str,
            new_to: str,
            new_via: str,
            new_device: str,
    ) -> StaticRouteModel:
        rec = self.get_by_triplet(db, to=current_to, via=current_via, device=current_device)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Static route not found")

        # If triplet changes, ensure the new one doesn't exist
        if (current_to, current_via, current_device) != (new_to, new_via, new_device):
            if self.get_by_triplet(db, to=new_to, via=new_via, device=new_device):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Static route with new data already exists")

        try:
            rec.to = new_to
            rec.via = new_via
            rec.device = new_device
            db.commit()
            db.refresh(rec)
            return rec
        except Exception as e:
            db.rollback()
            Logger.logger.error(f"StaticRoutes upsert failed: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update static route")

    def delete(self, db: Session, *, to: str, via: str, device: str) -> bool:
        rec = self.get_by_triplet(db, to=to, via=via, device=device)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Static route not found")
        db.delete(rec)
        db.commit()
        return True


static_route = CRUDStaticRoute(StaticRouteModel)
