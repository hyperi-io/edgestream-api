"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/event_destination.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import re
from typing import List, Any

from fastapi import Depends, HTTPException, BackgroundTasks, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.models.event.destination import DestinationRoute as DestinationRouteModel

from edgestream.schemas.event.destination import DestinationCreate, DestinationUpdate
from edgestream.schemas.event.destination_bodies import (
    FetchDestinationBody, DeleteDestinationBody, TemplateTypeBody, ModifySettingBody
)
from edgestream.schemas.event.destination_route_bodies import (
    DestinationRouteListBody, DestinationRouteAddBody,
    DestinationRouteReplaceBody, DestinationRouteDeleteBody,
    DestinationRouteReplaceGlobalBody
)

from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.utils.formatters import load_dynamic_templates
from edgestream.utils.formatters import get_formatted_entity

router = APIRouter()


def validate_destination_name(name: str):
    if not re.fullmatch(r'^[A-Za-z0-9_-]+$', (name or "")):
        raise HTTPException(
            status_code=400,
            detail="Invalid destination name. Allowed characters: A-Z, a-z, 0-9, _, -.",
        )


def validate_destination_type_dynamically(dest_type: str):
    """Verifies the destination type exists in JSON templates on disk."""
    templates = load_dynamic_templates("destination")
    valid_types = [t["type"] for t in templates]
    if dest_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Destination Type '{dest_type}'. Valid types are: {', '.join(valid_types)}."
        )


def _friendly_integrity_error(e: IntegrityError) -> str:
    msg = str(getattr(e, "orig", e))
    if "destination_parameters" in msg or "key" in msg:
        return "Duplicate setting key for this destination."
    if "destination_routes" in msg and "label" in msg:
        return "This destination already has that route label."
    if "destinations" in msg and "name" in msg:
        return "A destination with this name already exists."
    return "Uniqueness violation."


@router.post("/create", status_code=201)
def create_destination(
        *,
        destination_in: DestinationCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    validate_destination_type_dynamically(destination_in.type)

    validate_destination_name(destination_in.name)

    try:
        destination, _ = crud.destination.create(db=db, obj_in=destination_in)

        task_title = f"Create {destination.type} {destination.name}"
        return schedule_task(db, background_tasks, task_title, True)

    except HTTPException:
        raise
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail=_friendly_integrity_error(e))
    except Exception as e:
        Logger.logger.error(f"Destination creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error creating destination.")


# ---------- Routes ----------

@router.post("/routes/list", status_code=200)
def list_destination_routes(
        *,
        body: DestinationRouteListBody,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    dest = crud.destination.get(db, name=body.name)
    if not dest:
        raise HTTPException(status_code=404, detail=f"Destination '{body.name}' not found.")

    routes = crud.destination_route.get_by_destination_id(db, dest.id)
    return {"name": dest.name, "routes": [r.label for r in routes]}


@router.post("/routes/add", status_code=201)
def add_destination_routes(
        *,
        body: DestinationRouteAddBody,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    dest = crud.destination.get(db, name=body.name)
    if not dest:
        raise HTTPException(status_code=404, detail=f"Destination '{body.name}' not found.")

    existing = {r.label for r in crud.destination_route.get_by_destination_id(db, dest.id)}
    to_add: List[str] = []

    for lbl in (body.labels or []):
        lbl = (lbl or "").strip()
        if not lbl or lbl in existing:
            continue
        to_add.append(lbl)

    for lbl in to_add:
        db.add(DestinationRouteModel(label=lbl, destination_id=dest.id))

    if to_add:
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=_friendly_integrity_error(e))

    task_title = f"Add routes to destination {body.name}"
    job = schedule_task(db, background_tasks, task_title, True)
    return {"added": to_add, "job": job}


@router.put("/routes/replace", status_code=201)
def replace_destination_route_label(
        *,
        body: DestinationRouteReplaceBody,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    dest = crud.destination.get(db, name=body.name)
    if not dest:
        raise HTTPException(status_code=404, detail=f"Destination '{body.name}' not found.")

    changed = crud.destination_route.replace(
        db,
        destination_id=dest.id,
        old_label=body.old_label,
        new_label=body.new_label,
    )

    task_title = f"Replace route label on destination {body.name}"
    job = schedule_task(db, background_tasks, task_title, True)
    return {"changed": changed, "job": job}


@router.delete("/routes/delete", status_code=200)
def delete_destination_route_label(
        *,
        body: DestinationRouteDeleteBody,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    dest = crud.destination.get(db, name=body.name)
    if not dest:
        raise HTTPException(status_code=404, detail=f"Destination '{body.name}' not found.")

    deleted = crud.destination_route.delete_by_label(
        db,
        label=body.label,
        destination_id=dest.id,
    )

    task_title = f"Delete route '{body.label}' from destination {body.name}"
    job = schedule_task(db, background_tasks, task_title, True)
    return {"deleted": deleted, "job": job}


@router.put("/routes/replace-global", status_code=201)
def replace_route_label_globally(
        *,
        body: DestinationRouteReplaceGlobalBody,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    changed = crud.destination_route.replace_global(
        db, old_label=body.old_label, new_label=body.new_label
    )
    task_title = "Replace route label globally"
    job = schedule_task(db, background_tasks, task_title, True)
    return {"changed": changed, "job": job}


# ---------- Destination Management ----------

@router.get("/fetch_all", status_code=200)
def fetch_all_destinations(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[Any]:
    destinations = crud.destination.get_all(db=db)
    return [formatted for d in destinations if (formatted := get_formatted_entity(d, "destination"))]


@router.get("/template", status_code=200)
def get_template(
        current_user: User = Depends(get_current_user),
) -> List[Any]:
    return load_dynamic_templates("destination")


@router.post("/template/by-type", status_code=200)
def get_template_by_type(
        *,
        body: TemplateTypeBody,
        current_user: User = Depends(get_current_user),
) -> Any:
    templates = load_dynamic_templates("destination")
    for tmpl in templates:
        if tmpl["type"] == body.type:
            return tmpl
    raise HTTPException(status_code=404, detail=f"Destination type {body.type} not found.")


@router.post("/fetch", status_code=200)
def fetch_destination(
        *,
        body: FetchDestinationBody,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> Any:
    destination_obj = crud.destination.get(db=db, name=body.name)
    if not destination_obj:
        raise HTTPException(status_code=404, detail=f"Destination '{body.name}' not found.")

    formatted = get_formatted_entity(destination_obj, "destination")
    if not formatted:
        raise HTTPException(status_code=400, detail="Destination template missing on disk.")
    return formatted


@router.put("/update", status_code=201)
def update_destination(
        *,
        destination_in: DestinationUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    destination = crud.destination.get(db, name=destination_in.name)
    if not destination:
        raise HTTPException(status_code=404, detail=f"Destination '{destination_in.name}' not found.")

    if destination_in.type and destination_in.type != destination.type:
        validate_destination_type_dynamically(destination_in.type)

    try:
        crud.destination.update(db=db, db_obj=destination, obj_in=destination_in)
        return schedule_task(db, background_tasks, f"Update destination {destination.name}", True)

    except HTTPException:
        raise
    except IntegrityError as e:
        Logger.logger.error(f"Integrity error while updating destination: {e}")
        raise HTTPException(status_code=400, detail=_friendly_integrity_error(e))
    except Exception as e:
        Logger.logger.error(f"Update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during update.")


@router.delete("/delete", status_code=200)
def delete_destination(
        *,
        body: DeleteDestinationBody,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    destination_obj = crud.destination.get(db, name=body.name)
    if not destination_obj:
        raise HTTPException(status_code=404, detail=f"Destination '{body.name}' not found.")

    if destination_obj.system:
        raise HTTPException(status_code=400, detail=f"System destination '{body.name}' cannot be deleted.")

    try:
        crud.destination.delete_by_name(db, name=body.name)
        return schedule_task(db, background_tasks, f"Delete destination {body.name}", True)
    except HTTPException:
        raise


@router.put("/setting/modify", status_code=201)
def modify_setting(
        *,
        body: ModifySettingBody,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """Updates specific destination parameters directly."""
    destination_obj = crud.destination.get(db=db, name=body.name)
    if not destination_obj:
        raise HTTPException(status_code=404, detail=f"Destination '{body.name}' not found.")

    try:
        for updated_setting in body.settings:
            dest_setting = crud.destination_parameter.get_by_key(db, destination_name=body.name,
                                                                 key=updated_setting.key)
            if not dest_setting:
                raise HTTPException(
                    status_code=404,
                    detail=f"Setting '{updated_setting.key}' for destination '{body.name}' not found.",
                )

            crud.destination_parameter.update(db=db, db_obj=dest_setting, obj_in=updated_setting)

        return schedule_task(db, background_tasks, f"Update destination settings ({body.name})", True)

    except HTTPException:
        raise
    except IntegrityError as e:
        Logger.logger.error(f"Integrity error modifying setting: {e}")
        raise HTTPException(status_code=400, detail="Duplicate setting key detected.")
    except Exception as e:
        Logger.logger.error(f"Settings modification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error modifying settings.")
