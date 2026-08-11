from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Any, List

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.models.system.user import User
from edgestream.schemas.system.advanced_setting import (
    AdvancedSettingBase,
    AdvancedSettingCreate,
)
from edgestream.schemas.value.advanced_settings_response import (
    DeleteAdvancedSettingResponse,
)
from edgestream.services.port_manager import port_in_use

router = APIRouter()


def _safelower(x: Any) -> str:
    return str(x or "").strip().lower()


def check_port_availability(db: Session, advanced_settings: List[AdvancedSettingBase]) -> None:
    """
    Validates port availability for settings ending in 'listen_port'.
    Raises HTTPException 400 if a port conflict is detected.
    """
    for setting in advanced_settings:
        label_lc = _safelower(getattr(setting, "label", None))
        if not label_lc.endswith("listen_port"):
            continue

        raw_val = getattr(setting, "value", None) or getattr(setting, "default_value", None)

        try:
            port = int(raw_val)
        except (TypeError, ValueError):
            continue  # Not a numeric port, skip validation

        if port <= 0:
            continue

        result = port_in_use(db, port=port, protocol=None) or {}
        if not result.get("inuse"):
            continue

        owner = _safelower(result.get("service"))
        # Allow if the port is owned by the same logical setting
        if owner == label_lc:
            continue

        # Port conflict detected
        proto = result.get("protocol") or "tcp/udp"
        owner_disp = owner or "an unknown service"

        details = []
        if result.get("unit"): details.append(f"unit {result['unit']}")
        if result.get("pid"): details.append(f"pid {result['pid']}")
        extra_txt = f" ({', '.join(details)})" if details else ""

        raise HTTPException(
            status_code=400,
            detail=f"Port {port}/{proto} is already in use by {owner_disp}{extra_txt}."
        )


@router.put("", status_code=201)
def update_advanced_settings(
        *,
        advanced_settings_in: List[AdvancedSettingBase],
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Update advanced settings in bulk and trigger background reconfiguration.
    """
    try:
        check_port_availability(db, advanced_settings_in)
        crud.advanced_setting.update_bulk(db=db, obj_in=advanced_settings_in)

        return schedule_task(db, background_tasks, "Update advanced settings", True)

    except HTTPException:
        # Pass through 400 errors from check_port_availability
        raise
    except Exception as e:
        Logger.logger.error(f"Bulk settings update failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to update settings due to an internal server error."
        )


@router.get("", status_code=200, response_model=List[AdvancedSettingBase])
def fetch_advanced_settings(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[AdvancedSettingBase]:
    """
    Retrieve all advanced settings.
    """
    try:
        return crud.advanced_setting.get_all(db)
    except Exception as e:
        Logger.logger.error(f"Failed to fetch advanced settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching settings.")


@router.post("/setting", status_code=201)
def create_advanced_setting(
        *,
        advanced_setting_in: AdvancedSettingCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Create a single advanced setting and trigger background reconfiguration.
    """
    try:
        # Check port if this specific setting is a port
        check_port_availability(db, [advanced_setting_in])
        crud.advanced_setting.create(db=db, obj_in=advanced_setting_in)

        return schedule_task(db, background_tasks, "Create advanced setting", True)

    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Setting creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error creating setting.")


@router.delete("/setting", status_code=200, response_model=DeleteAdvancedSettingResponse)
def delete_advanced_setting(
        label: str,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Delete an advanced setting by its label and trigger background reconfiguration.
    """
    try:
        crud.advanced_setting.delete_by_label(db=db, label=label)

        return schedule_task(db, background_tasks, "Delete advanced setting", True)

    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Setting deletion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error deleting setting.")
