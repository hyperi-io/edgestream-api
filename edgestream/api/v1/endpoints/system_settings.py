"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/system_settings.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import re
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.schemas.system.system import SystemUpdate, SystemBase
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.services.hostname import get_db_hostname
from edgestream.services.timezone import get_system_timezone, is_valid_timezone

router = APIRouter()


@router.get("", status_code=200, response_model=SystemBase)
def get_system_settings(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> SystemBase:
    """
    Retrieve the current global system configuration.
    Returns a default configuration if the database has not been initialized.
    """
    try:
        system = crud.system.get_system(db)

        if not system:
            return SystemBase(
                hostname=get_db_hostname(),
                org_id="default_org",
                site_id="default_site",
                timezone=get_system_timezone() or "UTC",
            )

        return SystemBase.model_validate(system)

    except Exception as e:
        Logger.logger.error(f"Failed to retrieve system settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="System configuration is unavailable or malformed.",
        )


@router.put("", status_code=201)
def update_system_settings(
        *,
        settings_in: SystemUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Update global system settings and trigger host-level reconfiguration.
    """
    if not re.fullmatch(r'^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}$', settings_in.hostname):
        raise HTTPException(
            status_code=400,
            detail="Invalid hostname. Must start with alphanumeric, max 63 chars, hyphens allowed.",
        )

    id_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-_\.]{0,64}$'
    if not re.fullmatch(id_pattern, settings_in.org_id) or not re.fullmatch(id_pattern, settings_in.site_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid Org/Site ID. Use alphanumeric, dots, underscores, or hyphens.",
        )

    if not is_valid_timezone(settings_in.timezone):
        raise HTTPException(
            status_code=400,
            detail=f"Timezone '{settings_in.timezone}' is not recognized by the system.",
        )

    try:
        system = crud.system.get_system(db)
        if not system:
            crud.system.create(db=db, obj_in=settings_in)
        else:
            crud.system.update(db=db, db_obj=system, obj_in=settings_in)

        # 4. Trigger Configuration Convergence
        task_title = f"System Settings Convergence: {settings_in.hostname}"
        return schedule_task(db, background_tasks, task_title, run_playbook=True)

    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"System settings update failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to apply system settings due to an internal error.",
        )
