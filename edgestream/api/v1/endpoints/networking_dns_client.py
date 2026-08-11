from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.schemas.network.dns_client import (
    DNSCreate,
    DNSUpsert,
    DNSServer,
    DNSDelete
)
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.utils.validators import clean_var, validate_port, validate_ip_or_fqdn

router = APIRouter()


@router.post("", status_code=201)
def create_dns(
        *,
        dns_in: DNSCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Register a new DNS upstream server.
    """
    if not validate_ip_or_fqdn(dns_in.ip_address):
        raise HTTPException(status_code=400, detail="Invalid FQDN or IP address specified.")

    if dns_in.port is not None:
        try:
            validate_port(dns_in.port)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    dns_in.ip_address = clean_var(dns_in.ip_address)

    try:
        crud.dns.create(db=db, obj_in=dns_in)
        return schedule_task(
            db,
            background_tasks,
            f"Configure DNS server {dns_in.ip_address}",
            True,
            "01_dns_settings.yml"
        )
    except Exception as e:
        Logger.logger.error(f"DNS creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error configuring DNS.")


@router.put("", status_code=201)
def upsert_dns_server_entry(
        *,
        dns_in: DNSUpsert,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Update an existing DNS entry or create it if the pair does not exist.
    Used for modifying specific upstream resolvers.
    """
    if not validate_ip_or_fqdn(dns_in.current_ip) or not validate_ip_or_fqdn(dns_in.new_ip):
        raise HTTPException(status_code=400, detail="Invalid FQDN or IP address specified.")

    try:
        validate_port(dns_in.current_port)
        validate_port(dns_in.new_port)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    current_ip = clean_var(dns_in.current_ip)
    new_ip = clean_var(dns_in.new_ip)

    try:
        crud.dns.upsert_by_pair(
            db=db,
            current_ip=current_ip,
            current_port=dns_in.current_port,
            new_ip=new_ip,
            new_port=dns_in.new_port,
        )
        task_msg = f"Update DNS {current_ip}:{dns_in.current_port} → {new_ip}:{dns_in.new_port}"
        return schedule_task(db, background_tasks, task_msg, True, "01_dns_settings.yml")

    except Exception as e:
        Logger.logger.error(f"DNS upsert failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error updating DNS configuration.")


@router.get("", status_code=200, response_model=List[DNSServer])
def get_dns(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[DNSServer]:
    """
    Retrieve all configured DNS upstream servers.
    """
    try:
        # CRUD get_all_for_export uses standardized 2.0 select
        return crud.dns.get_all_for_export(db=db)
    except Exception as e:
        Logger.logger.error(f"Failed to fetch DNS servers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error retrieving DNS list.")


@router.delete("", status_code=200)
def delete_dns(
        *,
        body: DNSDelete,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Remove a DNS server entry from the configuration.
    """
    try:
        deleted = crud.dns.delete(db=db, ip_address=body.ip_address, port=body.port)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"DNS server {body.ip_address}:{body.port} not found."
            )

        return schedule_task(
            db,
            background_tasks,
            f"Delete DNS server {body.ip_address}:{body.port}",
            True,
            "01_dns_settings.yml"
        )
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"DNS deletion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error deleting DNS entry.")
