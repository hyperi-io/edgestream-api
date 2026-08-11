from __future__ import annotations
import base64
from typing import Dict, List, Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, load_only

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.system.certificate_store import Certificate
from edgestream.schemas.system.certificate_store import (
    CertificateCreate,
    CertificateUpdate,
    CertificateUpload,
    CertificateTypes,
)


class CRUDCertificate(CRUDBase[Certificate, CertificateCreate, CertificateUpdate]):

    def create(self, db: Session, *, obj_in: CertificateCreate) -> Certificate:
        """Standard record creation with a friendly filename error."""
        db_obj = Certificate(**obj_in.model_dump())
        try:
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="Filename already exists in the system")

    def upload(self, db: Session, obj_in: CertificateUpload, contents: bytes) -> Certificate:
        """Stores raw certificate bytes directly into the DB."""
        obj_in.data = contents
        return self.create(db, obj_in=obj_in)

    def update(self, db: Session, *, db_obj: Certificate, obj_in: CertificateUpdate) -> Certificate:
        """Enforces filename uniqueness and updates metadata."""
        update_data = obj_in.model_dump(exclude_unset=True)

        if "filename" in update_data and update_data["filename"] != db_obj.filename:
            existing = db.execute(
                select(Certificate).where(Certificate.filename == update_data["filename"])
            ).scalars().first()
            if existing:
                raise HTTPException(status_code=400, detail="Filename already exists in the system")

        try:
            for field, value in update_data.items():
                setattr(db_obj, field, value)

            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except Exception as e:
            db.rollback()
            Logger.logger.error(f"Error updating certificate: {e}")
            raise HTTPException(status_code=500, detail="Error updating certificate")

    def delete(self, db: Session, *, cert_id: int) -> None:
        """Delete certificate by primary key."""
        cert = db.get(Certificate, cert_id)
        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")
        try:
            db.delete(cert)
            db.commit()
        except Exception as e:
            db.rollback()
            Logger.logger.error(f"Error deleting certificate: {e}")
            raise HTTPException(status_code=500, detail="Error deleting certificate")

    def get_all_summary(self, db: Session) -> List[Dict[str, Any]]:
        """Retrieve certificate metadata without the large binary data blobs."""
        try:
            stmt = (
                select(Certificate)
                .options(
                    load_only(
                        Certificate.id,
                        Certificate.filename,
                        Certificate.type,
                        Certificate.filesize,
                        Certificate.file_extension,
                        Certificate.thumbprint,
                        Certificate.not_after,
                        Certificate.common_name,
                        Certificate.issuer,
                        Certificate.created_at,
                        Certificate.updated_at,
                    )
                )
                .order_by(Certificate.filename.asc())
            )
            rows = db.execute(stmt).scalars().all()

            return [
                {
                    "id": r.id,
                    "filename": r.filename,
                    "type": r.type,
                    "filesize": r.filesize,
                    "file_extension": r.file_extension,
                    "thumbprint": r.thumbprint,
                    "not_after": r.not_after,
                    "common_name": r.common_name,
                    "issuer": r.issuer,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in rows
            ]
        except OperationalError as error:
            Logger.logger.error(f"Operational error: {error}")
            raise HTTPException(status_code=500, detail="Database operational error.")

    def export(self, db: Session) -> Dict[str, List[Dict[str, Any]]]:
        """Standardized export for certificates with Base64 encoding."""
        out: Dict[str, List[Dict[str, Any]]] = {}
        for cert_type in CertificateTypes.list():
            rows = db.execute(
                select(Certificate)
                .where(Certificate.type == cert_type)
                .order_by(Certificate.filename.asc())
            ).scalars().all()

            out[cert_type] = []
            for cert in rows:
                raw = cert.data or b""

                # Attempt UTF-8 (PEM) fallback to None for binary
                try:
                    data_utf8 = raw.decode("utf-8")
                except UnicodeDecodeError:
                    data_utf8 = None

                out[cert_type].append({
                    "filename": cert.filename,
                    "type": cert.type,
                    "size": cert.filesize,
                    "thumbprint": cert.thumbprint,
                    "data": data_utf8,
                    "data_b64": base64.b64encode(raw).decode("ascii"),
                })
        return out


certificate = CRUDCertificate(Certificate)
