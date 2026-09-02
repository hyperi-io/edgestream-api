"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/networking_dns_forwarding.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List

import validators
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.schemas.network.dns_forwarder import (
    DNSForwarderDelete,
    DNSForwarderBase,
    DNSForwarderUpdate,
    DNSForwarderCreate
)
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.utils.validators import clean_var, validate_port, validate_ip

router = APIRouter()


@router.post("", status_code=201)
def create_dns_forwarder(
        *,
        fwd: DNSForwarderCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Register a new DNS domain-specific forwarder.
    """
    if not validators.hostname(fwd.domain):
        raise HTTPException(status_code=400, detail="Invalid domain specified.")

    if not validate_ip(fwd.ip_address):
        raise HTTPException(status_code=400, detail="Invalid IP address for forwarder target.")

    if fwd.port is not None:
        try:
            validate_port(fwd.port)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    fwd.domain = clean_var(fwd.domain)
    fwd.ip_address = clean_var(fwd.ip_address)

    try:
        created = crud.dns_forwarder.create(db=db, obj_in=fwd)
        if not created:
            raise HTTPException(status_code=400, detail="Failed to persist DNS Forwarder.")

        return schedule_task(
            db, background_tasks, f"Add DNS forwarder for {fwd.domain}", True, "01_dns_settings.yml"
        )
    except Exception as e:
        Logger.logger.error(f"Failed to create DNS forwarder: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error configuring forwarder.")


@router.put("", status_code=201)
def update_dns_forwarder(
        *,
        fwd_in: DNSForwarderUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Update an existing DNS forwarder entry by ID.
    """
    if not validators.hostname(fwd_in.domain):
        raise HTTPException(status_code=400, detail="Invalid domain specified.")

    if not validate_ip(fwd_in.ip_address):
        raise HTTPException(status_code=400, detail="Invalid IP address specified.")

    if fwd_in.port is not None:
        try:
            validate_port(fwd_in.port)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    fwd_in.domain = clean_var(fwd_in.domain)
    fwd_in.ip_address = clean_var(fwd_in.ip_address)

    db_obj = crud.dns_forwarder.get(db, id=fwd_in.id)
    if not db_obj:
        raise HTTPException(status_code=404, detail=f"DNS Forwarder with ID {fwd_in.id} not found.")

    try:
        crud.dns_forwarder.update(db=db, db_obj=db_obj, obj_in=fwd_in)
        return schedule_task(
            db, background_tasks, f"Update DNS forwarder for {fwd_in.domain}", True, "01_dns_settings.yml"
        )
    except Exception as e:
        Logger.logger.error(f"Failed to update DNS forwarder {fwd_in.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error updating forwarder.")


@router.get("", status_code=200, response_model=List[DNSForwarderBase])
def get_dns_forwarders(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[DNSForwarderBase]:
    """
    Retrieve all configured domain-specific DNS forwarders.
    """
    try:
        return crud.dns_forwarder.export(db=db)
    except Exception as e:
        Logger.logger.error(f"Failed to fetch DNS forwarders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error retrieving forwarder list.")


@router.delete("", status_code=200)
def delete_dns_forwarder(
        *,
        body: DNSForwarderDelete,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Delete a DNS forwarder by its target domain.
    """
    try:
        deleted = crud.dns_forwarder.delete(db=db, domain=body.domain)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"DNS Forwarder for domain '{body.domain}' not found.")

        return schedule_task(
            db, background_tasks, f"Delete DNS forwarder for {body.domain}", True, "01_dns_settings.yml"
        )
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Failed to delete DNS forwarder: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error deleting forwarder.")
