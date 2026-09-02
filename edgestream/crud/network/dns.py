"""
Project:   edgestream-api
File:      edgestream/crud/network/dns.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

# edgestream/core/crud/network/dns.py
from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select, and_

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.network.dns_client import DNS
from edgestream.schemas.network.dns_client import DNSCreate, DNSUpsert

class CrudDNS(CRUDBase[DNS, DNSCreate, DNSUpsert]):

    def export(self, db: Session) -> List[Dict[str, Any]]:
        """
        Standardized export method for the Configuration Exporter.
        """
        rows = db.execute(select(DNS).order_by(DNS.id.asc())).scalars().all()
        return [{"ip_address": r.ip_address, "port": r.port} for r in rows]

    def get_all_for_export(self, db: Session) -> List[dict]:
        """Legacy alias for backward compatibility."""
        return self.export(db)

    def _exists_ip_port(self, db: Session, *, ip_address: str, port: int, exclude_id: Optional[int] = None) -> bool:
        stmt = select(self.model.id).where(
            and_(self.model.ip_address == ip_address, self.model.port == port)
        )
        if exclude_id is not None:
            stmt = stmt.where(self.model.id != exclude_id)
        return db.execute(select(stmt.exists())).scalar()

    def create(self, db: Session, *, obj_in: DNSCreate) -> DNS:
        try:
            data = obj_in.model_dump(exclude_unset=True)
            ip = data["ip_address"]
            port = data.get("port", 53)

            if self._exists_ip_port(db, ip_address=ip, port=port):
                raise HTTPException(status_code=409, detail="DNS (ip_address, port) already exists")

            db_obj = DNS(ip_address=ip, port=port)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="DNS (ip_address, port) already exists")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"DNS create failed: {e}")
            raise HTTPException(status_code=400, detail="Failed to create DNS record")

    def get_by_pair(self, db: Session, *, ip_address: str, port: int) -> Optional[DNS]:
        return db.execute(
            select(self.model).where(
                and_(self.model.ip_address == ip_address, self.model.port == port)
            )
        ).scalar_one_or_none()

    def upsert_by_pair(
        self, db: Session, *, current_ip: str, current_port: int, new_ip: str, new_port: int
    ) -> DNS:
        rec = self.get_by_pair(db, ip_address=current_ip, port=current_port)
        if not rec:
            raise HTTPException(status_code=404, detail="DNS record not found")

        if self._exists_ip_port(db, ip_address=new_ip, port=new_port, exclude_id=rec.id):
            raise HTTPException(status_code=409, detail="Another DNS exists at that IP/Port")

        try:
            rec.ip_address = new_ip
            rec.port = new_port
            db.commit()
            db.refresh(rec)
            return rec
        except Exception as e:
            db.rollback()
            Logger.logger.error(f"DNS upsert failed: {e}")
            raise HTTPException(status_code=400, detail="Failed to update DNS record")

    def delete(self, db: Session, *, ip_address: str, port: int) -> bool:
        rec = self.get_by_pair(db, ip_address=ip_address, port=port)
        if not rec:
            raise HTTPException(status_code=404, detail="DNS record not found")
        db.delete(rec)
        db.commit()
        return True

dns = CrudDNS(DNS)
