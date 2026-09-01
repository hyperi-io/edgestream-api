"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/certificate_store.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from io import BytesIO
from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, BackgroundTasks
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.schemas.system.certificate_store import (
    CertificateUpdate,
    CertificateUpload,
    CertificateTypes,
)
from edgestream.schemas.value.certs_response import (
    IncorrectCertResponse,
    CorrectCertResponse,
)
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.utils.validators import validate_privatekey, validate_certificate, certificate_thumbprint, \
    parse_certificate_metadata

router = APIRouter()

# Map common mimetypes to enforced extensions for DB CHECK constraints
_MIME_TO_EXT = {
    "application/x-x509-ca-cert": ".crt",
    "application/pkix-cert": ".crt",
    "application/x-pem-file": ".pem",
    "application/pem-certificate-chain": ".pem",
    "application/pkcs8": ".key",
    "application/octet-stream": ".pem",
}

_EXT_TO_MIME = {
    ".pem": "application/x-pem-file",
    ".crt": "application/x-x509-ca-cert",
    ".key": "application/pkcs8",
}


@router.post("/upload", status_code=201)
async def upload_cert(
        file: Annotated[UploadFile, File()],
        file_type: Annotated[CertificateTypes, Form()],
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Upload a certificate, private key, or CA bundle to the database.
    Validates cryptographic integrity before saving.
    """
    contents = await file.read()
    ft = file_type.value.lower()

    if ft not in CertificateTypes.list():
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be: {CertificateTypes.list()}")

    # Cryptographic Validation
    try:
        if ft == "private_key":
            validate_privatekey(contents)
        else:
            validate_certificate(contents)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cryptographic validation failed: {str(e)}")

    thumbprint = ""
    if ft == "certificate_authority":
        try:
            thumbprint = certificate_thumbprint(contents)
        except Exception:
            pass

    meta = parse_certificate_metadata(contents) if ft != "private_key" else {}

    # Normalize extension to satisfy DB constraints
    ext = (Path(file.filename).suffix or "").lower()
    if ext not in {".pem", ".crt", ".key"}:
        ext = _MIME_TO_EXT.get((file.content_type or "").lower(), ".pem")

    new_cert_schema = CertificateUpload(
        filename=file.filename,
        filesize=len(contents),
        type=ft,
        thumbprint=thumbprint,
        file_extension=ext,
        not_after=meta.get("not_after"),
        common_name=meta.get("common_name"),
        issuer=meta.get("issuer"),
    )

    try:
        cert = crud.certificate.upload(db=db, obj_in=new_cert_schema, contents=contents)
        task_title = f"Upload certificate file {cert.filename}"
        return schedule_task(db, background_tasks, task_title, run_playbook=True)

    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Certificate upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred during upload.")


@router.delete("/{cert_id}", status_code=201)
def delete_cert(
        cert_id: int,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Delete a certificate by ID and trigger system reconfiguration.
    """
    try:
        crud.certificate.delete(db=db, cert_id=cert_id)

        return schedule_task(db, background_tasks, "Delete certificate file", run_playbook=True)

    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Certificate deletion failed for ID {cert_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during certificate deletion.")


@router.get("/download/{id}", responses={200: {"model": CorrectCertResponse}, 404: {"model": IncorrectCertResponse}})
async def download_cert(
        id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    Retrieve binary certificate data for download.
    """
    cert = crud.certificate.get(db, id=id)
    if not cert or not cert.data:
        raise HTTPException(status_code=404, detail="Certificate data not found.")

    mime = _EXT_TO_MIME.get((cert.file_extension or "").lower(), "application/octet-stream")

    return StreamingResponse(
        BytesIO(cert.data),
        media_type=mime,
        headers={"Content-Disposition": f"attachment; filename={cert.filename}"}
    )


@router.get("", status_code=200)
def fetch_certs(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Fetch certificate metadata (excludes binary data for performance).
    """
    try:
        certificates = crud.certificate.get_all_summary(db)
        return {"results": list(certificates)}
    except Exception as error:
        Logger.logger.error(f"Failed to fetch certificates: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving certificate list.")


@router.put("/{id}", status_code=201)
def update_cert(
        id: int,
        cert_in: CertificateUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Update certificate metadata (e.g., filename) and refresh system state.
    """
    cert = crud.certificate.get(db, id=id)
    if not cert:
        raise HTTPException(status_code=404, detail=f"Certificate {id} not found.")

    try:
        updated_cert = crud.certificate.update(db=db, db_obj=cert, obj_in=cert_in)
        return schedule_task(db, background_tasks, f"Update certificate {updated_cert.filename}", run_playbook=True)

    except HTTPException:
        raise
    except Exception as error:
        Logger.logger.error(f"Certificate update failed: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating certificate.")
