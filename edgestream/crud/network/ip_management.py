from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select, delete

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.network.ip_management import IPManagement
from edgestream.schemas.network.ip_management import (
    IPMgmtCreate,
    IPMgmtUpdate
)


class CRUDIPMgmt(CRUDBase[IPManagement, IPMgmtCreate, IPMgmtUpdate]):

    def export(self, db: Session) -> List[Dict[str, Any]]:
        """
        Standardized export method for the Configuration Exporter.
        """
        rows = db.execute(
            select(IPManagement).order_by(IPManagement.type.asc())
        ).scalars().all()

        return [
            {
                "type": r.type,
                "iface": r.iface,
                "mac_address": r.mac_address,
                "family": r.family,
                "dhcp": r.dhcp,
                "ip_address": r.ip_address,
                "netmask": r.netmask,
                "gateway": r.gateway,
                "default": r.default,
            }
            for r in rows
        ]

    def get_by_type(self, db: Session, ip_type: str) -> Optional[IPManagement]:
        return db.execute(
            select(IPManagement).where(IPManagement.type == ip_type)
        ).scalar_one_or_none()

    def delete(self, db: Session, ip_type: str) -> bool:
        """Atomic delete by type."""
        stmt = delete(IPManagement).where(IPManagement.type == ip_type)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0

    def create(self, db: Session, *, obj_in: IPMgmtCreate) -> List[IPManagement]:
        rows: List[IPManagement] = []
        try:
            if obj_in.mgmt:
                data = obj_in.mgmt.model_dump()
                rows.append(IPManagement(**{**data, "type": "mgmt"}))
            if obj_in.event:
                data = obj_in.event.model_dump()
                rows.append(IPManagement(**{**data, "type": "event"}))

            db.add_all(rows)
            db.commit()
            for r in rows:
                db.refresh(r)
            return rows
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"IPMgmt create failed: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create IP management records")

    def update_ip_mgmt(self, db: Session, obj_in: IPMgmtUpdate) -> List[IPManagement]:
        """
        Replace mgmt/event IP configs atomically.
        """
        try:
            db.execute(delete(IPManagement).where(IPManagement.type.in_(["mgmt", "event"])))

            rows: List[IPManagement] = []
            if obj_in.mgmt:
                mgmt = obj_in.mgmt.model_dump(exclude_none=False)
                mgmt.setdefault("default", False)
                rows.append(IPManagement(**{**mgmt, "type": "mgmt"}))

            if obj_in.event:
                event = obj_in.event.model_dump(exclude_none=False)
                event.setdefault("default", False)
                rows.append(IPManagement(**{**event, "type": "event"}))

            if rows:
                db.add_all(rows)
            db.commit()
            for r in rows:
                db.refresh(r)
            return rows
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"IPMgmt update failed: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update IP management records")


ip_mgmt = CRUDIPMgmt(IPManagement)
