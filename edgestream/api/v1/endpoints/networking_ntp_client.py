from typing import List

import validators
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.schemas.network.ntp_client import (
    NTPCreate,
    NTPUpsert,
    NTPDelete,
    NTPServer
)
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.utils.validators import clean_var, validate_port

router = APIRouter()


@router.post("", status_code=201)
def create_ntp(
        *,
        ntp_in: NTPCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Register a new NTP upstream server for system time synchronization.
    """
    if not validators.hostname(ntp_in.ip_address, may_have_port=True):
        raise HTTPException(status_code=400, detail="Invalid FQDN or IP address specified.")

    if ntp_in.port is not None:
        try:
            validate_port(ntp_in.port)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    ip_address = clean_var(ntp_in.ip_address)

    try:
        crud.ntp.create(db=db, obj_in=ntp_in)

        return schedule_task(
            db,
            background_tasks,
            f"Configure NTP server {ip_address}",
            run_playbook=True,
            playbook="01_ntp_settings.yml"
        )
    except Exception as e:
        Logger.logger.error(f"Failed to create NTP server: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error configuring NTP.")


@router.put("", status_code=201)
def upsert_ntp_server_entry(
        *,
        ntp_in: NTPUpsert,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Update an existing NTP entry or create it if the pair does not exist.
    """
    if not validators.hostname(ntp_in.current_ip, may_have_port=True) or \
            not validators.hostname(ntp_in.new_ip, may_have_port=True):
        raise HTTPException(status_code=400, detail="Invalid FQDN or IP address specified.")

    try:
        validate_port(ntp_in.current_port)
        validate_port(ntp_in.new_port)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    current_ip = clean_var(ntp_in.current_ip)
    new_ip = clean_var(ntp_in.new_ip)

    try:
        crud.ntp.upsert_by_pair(
            db=db,
            current_ip=current_ip,
            current_port=ntp_in.current_port,
            new_ip=new_ip,
            new_port=ntp_in.new_port,
        )
        task_msg = f"Update NTP {current_ip}:{ntp_in.current_port} → {new_ip}:{ntp_in.new_port}"
        return schedule_task(db, background_tasks, task_msg, True, "01_ntp_settings.yml")

    except Exception as e:
        Logger.logger.error(f"NTP upsert failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error updating NTP configuration.")


@router.delete("", status_code=200)
def delete_ntp(
        *,
        body: NTPDelete,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Remove an NTP server from the configuration.
    """
    try:
        deleted = crud.ntp.delete(db=db, ip_address=body.ip_address, port=body.port)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"NTP server {body.ip_address}:{body.port} not found.")

        return schedule_task(
            db,
            background_tasks,
            f"Delete NTP server {body.ip_address}:{body.port}",
            True,
            "01_ntp_settings.yml"
        )
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"NTP deletion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error deleting NTP entry.")


@router.get("", status_code=200, response_model=List[NTPServer])
def get_ntp(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[NTPServer]:
    """
    Retrieve all configured Network Time Protocol servers.
    """
    try:
        return crud.ntp.export(db=db)
    except Exception as e:
        Logger.logger.error(f"Failed to fetch NTP servers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error retrieving NTP list.")
