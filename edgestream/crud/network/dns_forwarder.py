from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase

from edgestream.models.network.dns_forwarder import DNSForwarder
from edgestream.schemas.network.dns_forwarder import DNSForwarderCreate, DNSForwarderUpdate, ListDNSForwarderCreate


class CRUDDNSForwarder(CRUDBase[DNSForwarder, DNSForwarderCreate, DNSForwarderUpdate]):

    def export(self, db: Session) -> List[Dict[str, Any]]:
        """
        Unified export method for the Configuration Exporter.
        """
        rows = db.execute(
            select(DNSForwarder).order_by(DNSForwarder.domain.asc())
        ).scalars().all()

        return [
            {
                "domain": r.domain,
                "ip_address": r.ip_address,
                "port": r.port
            }
            for r in rows
        ]

    def create_all(self, db: Session, *, obj_in: ListDNSForwarderCreate) -> List[DNSForwarder]:
        rows = [
            DNSForwarder(domain=fwd.domain, ip_address=fwd.ip_address, port=fwd.port)
            for fwd in obj_in.dns_forwarders
        ]
        try:
            db.add_all(rows)
            db.commit()
            for r in rows:
                db.refresh(r)
            return rows
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"DNSForwarder create failed: {e}")
            raise HTTPException(status_code=400, detail="Failed to create DNS forwarders")

    def delete(self, db: Session, domain: str) -> bool:
        stmt = select(DNSForwarder).where(DNSForwarder.domain == domain)
        rec = db.execute(stmt).scalar_one_or_none()

        if not rec:
            raise HTTPException(status_code=404, detail="DNS Forwarder not found")

        db.delete(rec)
        db.commit()
        return True


dns_forwarder = CRUDDNSForwarder(DNSForwarder)
