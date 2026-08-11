from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from sqlalchemy.orm import Session
from typing import Optional

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.schemas.base import TaskScheduledResponse
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.models.system.user import User

from edgestream.schemas.network.ip_management import (
    IPMgmtUpdate,
    IPMgmtResponse,
    IPMgmtRecord
)

router = APIRouter()


@router.get("", status_code=200, response_model=IPMgmtResponse)
def fetch_ip_address_management(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> IPMgmtResponse:
    """
    Retrieve the IP configuration for both Management and Event Receiver interfaces.
    """
    try:
        ip_mgmt_rows = crud.ip_mgmt.get_all(db=db)

        mgmt: Optional[IPMgmtRecord] = None
        event: Optional[IPMgmtRecord] = None

        for item in ip_mgmt_rows:
            record = IPMgmtRecord.model_validate(item)

            if item.type == "mgmt":
                mgmt = record
            elif item.type == "event":
                event = record

        return IPMgmtResponse(mgmt=mgmt, event=event)

    except Exception as e:
        Logger.logger.error(f"Failed to fetch IP Management data: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while retrieving network interface data."
        )


@router.put("", status_code=201, response_model=TaskScheduledResponse)
def update_ip_address_management(
        *,
        ip_mgmt_in: IPMgmtUpdate = Body(...),
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> TaskScheduledResponse:
    """
    Update interface IP settings (Static/DHCP) and trigger network reconfiguration.
    """
    try:
        success = crud.ip_mgmt.update_ip_mgmt(db=db, obj_in=ip_mgmt_in)

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Could not update network settings. Ensure the payload is valid.",
            )

        return schedule_task(db, background_tasks, "Saving network settings", True)

    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Failed to update IP Management: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while applying network configuration."
        )
