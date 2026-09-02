"""
Project:   edgestream-api
File:      edgestream/crud/network/static_host.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List, Any, Dict
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.network.static_host import StaticHost as StaticHostModel
from edgestream.schemas.network.static_host import StaticHostCreate, StaticHostUpsert


class CrudStaticHost(CRUDBase[StaticHostModel, StaticHostCreate, StaticHostUpsert]):

    def export(self, db: Session) -> List[Dict[str, Any]]:
        """
        Standardized export method for the Configuration Exporter.
        """
        rows = db.execute(
            select(StaticHostModel).order_by(StaticHostModel.host.asc())
        ).scalars().all()

        return [
            {
                "host": r.host,
                "ip_address": r.ip_address
            }
            for r in rows
        ]

    def create(self, db: Session, *, obj_in: StaticHostCreate) -> StaticHostModel:
        stmt = select(self.model).where(self.model.host == obj_in.host)
        if db.execute(stmt).scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Static host with this host already exists")

        try:
            db_obj = StaticHostModel(**obj_in.model_dump(exclude_unset=True))
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError as e:
            db.rollback()
            Logger.logger.error(f"StaticHost create integrity error: {e}")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Static host already exists")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"StaticHost create failed: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create static host record")

    def upsert_by_host(
            self,
            db: Session,
            *,
            current_host: str,
            new_host: str,
            new_ip_address: str
    ) -> StaticHostModel:
        # Fetch current record
        stmt = select(self.model).where(self.model.host == current_host)
        rec = db.execute(stmt).scalar_one_or_none()

        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Static host not found")

        # If renaming, check if new name is taken
        if new_host != current_host:
            check_stmt = select(self.model).where(self.model.host == new_host)
            if db.execute(check_stmt).scalar_one_or_none():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Static host with new_host already exists")

        try:
            rec.host = new_host
            rec.ip_address = new_ip_address
            db.commit()
            db.refresh(rec)
            return rec
        except Exception as e:
            db.rollback()
            Logger.logger.error(f"StaticHost upsert failed: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update static host record")

    def delete(self, db: Session, *, host: str) -> bool:
        stmt = select(self.model).where(self.model.host == host)
        rec = db.execute(stmt).scalar_one_or_none()

        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Static host not found")

        db.delete(rec)
        db.commit()
        return True


static_host = CrudStaticHost(StaticHostModel)
