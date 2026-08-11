from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.schemas.event.syslog import (
    SyslogPortCreate,
    SyslogPortUpdate,
    SyslogPort,
    SyslogPortDelete
)
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.models.system.user import User
from edgestream.services.port_manager import port_in_use

router = APIRouter()


@router.post("", status_code=201)
def create_syslog_port(
        *,
        syslog_port_in: SyslogPortCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Create a new syslog-ng listener as a Source.
    Validates port availability before persisting.
    """
    listen_protocols = [p.protocol for p in syslog_port_in.protocols]
    for proto in listen_protocols:
        result = port_in_use(db, port=syslog_port_in.port, protocol=proto)
        if result.get("inuse"):
            raise HTTPException(
                status_code=400,
                detail=f"Port {syslog_port_in.port}/{proto} is already in use by {result.get('service')}."
            )
    try:
        source, _ = crud.syslog.create(db=db, obj_in=syslog_port_in)

        job_name = f"Create syslog listener {getattr(source, 'name', 'syslog')}"
        return schedule_task(db, background_tasks, job_name, True)

    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Failed to create syslog listener: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error creating syslog listener.")


@router.put("", status_code=201)
def update_syslog_port(
        *,
        syslog_port_in: SyslogPortUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Update an existing syslog listener configuration by its unique source name.
    """
    try:
        listen_protocols = [p.protocol for p in syslog_port_in.protocols]
        for proto in listen_protocols:
            result = port_in_use(db, port=syslog_port_in.port, protocol=proto)
            if result.get("inuse") and result.get("service") != syslog_port_in.name:
                raise HTTPException(
                    status_code=400,
                    detail=f"Target port {syslog_port_in.port} in use by {result.get('service')}."
                )

        crud.syslog.update_by_name(db=db, obj_in=syslog_port_in)

        return schedule_task(
            db, background_tasks, f"Update syslog listener {syslog_port_in.name}", True
        )

    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Failed to update syslog listener {syslog_port_in.name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error updating syslog listener.")


@router.get("", status_code=200, response_model=List[SyslogPort])
def fetch_syslog_ports(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[SyslogPort]:
    """
    Retrieve all configured syslog listeners.
    """
    try:
        return crud.syslog.list(db=db)
    except Exception as e:
        Logger.logger.error(f"Failed to fetch syslog listeners: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching syslog listeners.")


@router.delete("", status_code=200)
def delete_syslog_port(
        *,
        body: SyslogPortDelete,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Remove a syslog listener configuration by unique source name.
    """
    try:
        crud.syslog.delete_by_name(db=db, name=body.name)

        return schedule_task(
            db, background_tasks, f"Delete syslog listener {body.name}", True
        )

    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Failed to delete syslog listener {body.name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error deleting syslog listener.")
