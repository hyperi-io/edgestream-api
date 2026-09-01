"""
Project:   edgestream-api
File:      edgestream/crud/network/ntp.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import and_

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.network.ntp_client import NTP
from edgestream.schemas.network.ntp_client import NTPCreate, NTPUpsert


class CrudNTP(CRUDBase[NTP, NTPCreate, NTPUpsert]):

    def _exists_ip_port(
        self, db: Session, *, ip_address: str, port: int, exclude_id: Optional[int] = None
    ) -> bool:
        q = db.query(self.model.id).filter(
            and_(
                self.model.ip_address == ip_address,
                self.model.port == port,
            )
        )
        if exclude_id is not None:
            q = q.filter(self.model.id != exclude_id)
        return db.query(q.exists()).scalar()  # True if a row exists

    def create(self, db: Session, *, obj_in: NTPCreate) -> NTP:
        try:
            data = obj_in.model_dump(exclude_unset=True)
            # ensure default port when omitted
            port = data.get("port", 123)

            if self._exists_ip_port(db, ip_address=data["ip_address"], port=port):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="NTP (ip_address, port) already exists")

            db_obj = NTP(**{**data, "port": port})
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="NTP (ip_address, port) already exists")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"NTP create failed: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create NTP records")

    def get_by_ip(self, db: Session, *, ip_address: str) -> Optional[NTP]:
        return db.query(self.model).filter(self.model.ip_address == ip_address).first()

    def upsert_by_pair(
        self, db: Session, *, current_ip: str, current_port: int, new_ip: str, new_port: int
    ) -> NTP:
        rec = (
            db.query(self.model)
              .filter(and_(self.model.ip_address == current_ip,
                           self.model.port == current_port))
              .first()
        )
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NTP record not found")

        if self._exists_ip_port(db, ip_address=new_ip, port=new_port, exclude_id=rec.id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another NTP with the same (ip_address, port) already exists")

        try:
            rec.ip_address = new_ip
            rec.port = new_port
            db.commit()
            db.refresh(rec)
            return rec
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another NTP with the same (ip_address, port) already exists")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"NTP upsert failed: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update NTP record")

    def update_by_ip(self, db: Session, *, ip_address: str, port: Optional[int]) -> NTP:
        rec = self.get_by_ip(db, ip_address=ip_address)
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NTP record not found")
        try:
            if port is not None:
                if self._exists_ip_port(db, ip_address=rec.ip_address, port=port, exclude_id=rec.id):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another NTP with the same (ip_address, port) already exists")
                rec.port = port
            db.commit()
            db.refresh(rec)
            return rec
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another NTP with the same (ip_address, port) already exists")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"NTP update failed: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update NTP record")

    def delete(self, db: Session, *, ip_address: str, port: int) -> bool:
        rec = (
            db.query(self.model)
              .filter(and_(self.model.ip_address == ip_address,
                           self.model.port == port))
              .first()
        )
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NTP record {ip_address}:{port} not found"
            )
        db.delete(rec)
        db.commit()
        return True

    def export(self, db: Session) -> List[dict]:
        """
        Unified export method for the Configuration Exporter.
        Returns a list of NTP server configurations.
        """
        from sqlalchemy import select

        rows = db.execute(select(NTP).order_by(NTP.id.asc())).scalars().all()

        return [
            {
                "ip_address": r.ip_address,
                "port": r.port
            }
            for r in rows
        ]

ntp = CrudNTP(NTP)
