from typing import List

import validators
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.schemas.network.static_host import (
    StaticHostCreate,
    StaticHostUpsert,
    StaticHost,
    StaticHostDelete
)
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.utils.validators import clean_var, validate_ip

router = APIRouter()


@router.post("", status_code=201)
def create_static_host_record(
        *,
        shr_in: StaticHostCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Create a local static DNS host mapping (overrides upstream DNS).
    """
    if not validators.hostname(shr_in.host, maybe_simple=True):
        raise HTTPException(status_code=400, detail="Invalid hostname specified.")

    if not validate_ip(shr_in.ip_address):
        raise HTTPException(status_code=400, detail="Invalid IP address specified.")

    shr_in.host = clean_var(shr_in.host)
    shr_in.ip_address = clean_var(shr_in.ip_address)

    try:
        crud.static_host.create(db=db, obj_in=shr_in)

        return schedule_task(
            db, background_tasks,
            f"Add static host {shr_in.host}",
            True, "01_dns_settings.yml"
        )
    except Exception as e:
        Logger.logger.error(f"Static host creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error adding host record.")


@router.put("", status_code=201)
def upsert_static_host_record(
        *,
        shr_in: StaticHostUpsert,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Update an existing host record or create it if the current host name isn't found.
    """
    if not validators.hostname(shr_in.current_host) or not validators.hostname(shr_in.new_host):
        raise HTTPException(status_code=400, detail="Invalid hostname specified.")

    if not validate_ip(shr_in.new_ip_address):
        raise HTTPException(status_code=400, detail="Invalid target IP address specified.")

    current_host = clean_var(shr_in.current_host)
    new_host = clean_var(shr_in.new_host)
    new_ip = clean_var(shr_in.new_ip_address)

    try:
        crud.static_host.upsert_by_host(
            db=db,
            current_host=current_host,
            new_host=new_host,
            new_ip_address=new_ip,
        )

        return schedule_task(
            db, background_tasks,
            f"Update Static Host {current_host} → {new_host}",
            True, "01_dns_settings.yml"
        )
    except Exception as e:
        Logger.logger.error(f"Static host update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error updating host record.")


@router.get("", status_code=200, response_model=List[StaticHost])
def get_static_hosts(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[StaticHost]:
    """
    Retrieve all local static host mappings.
    """
    try:
        return crud.static_host.export(db=db)
    except Exception as e:
        Logger.logger.error(f"Failed to fetch static hosts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error retrieving host list.")


@router.delete("", status_code=200)
def delete_static_host_record(
        *,
        body: StaticHostDelete,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Remove a static host mapping from the configuration.
    """
    try:
        deleted = crud.static_host.delete(db=db, host=body.host)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Host record for '{body.host}' not found.")

        return schedule_task(
            db, background_tasks, f"Delete static host {body.host}",
            True, "01_dns_settings.yml"
        )
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Static host deletion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error deleting host record.")
