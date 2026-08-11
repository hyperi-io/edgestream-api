import re
from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.schemas.event.source import SourceCreate, SourceUpdate
from edgestream.schemas.event.source_bodies import TemplateTypeBody, FetchSourceBody, DeleteSourceBody
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.services.port_manager import find_mode, extract_port, port_in_use
from edgestream.utils.formatters import load_dynamic_templates
from edgestream.utils.formatters import get_formatted_entity

router = APIRouter()


def validate_source_type_dynamically(source_type: str):
    """Checks if the requested type exists in core or contrib JSON templates."""
    templates = load_dynamic_templates("source")
    valid_types = [t["type"] for t in templates]
    if source_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Source Type '{source_type}'. Valid types are: {', '.join(valid_types)}."
        )


@router.post("/create", status_code=201)
def create_source(
        *,
        source_in: SourceCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    validate_source_type_dynamically(source_in.type)

    if not re.fullmatch(r"^[A-Za-z0-9_-]+$", source_in.name or ""):
        raise HTTPException(
            status_code=400,
            detail="Invalid source name. Use letters, digits, underscores, or hyphens only."
        )

    if (source_in.type or "").lower() == "netflow":
        if crud.source.get_by_type(db=db, type_name="netflow"):
            raise HTTPException(status_code=400, detail="Only one NetFlow source is permitted per system.")

    mode = find_mode(source_in.settings)
    for setting in (source_in.settings or []):
        if setting.key == "address":
            port = extract_port(setting.value)
            if port:
                result = port_in_use(db, port=port, protocol=mode)
                if result.get("inuse"):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Port {port} is already in use by service: {result.get('service')}."
                    )

    try:
        src, _ = crud.source.create(db=db, obj_in=source_in)
        task_title = f"Create {src.type} {src.name}"
        return schedule_task(db, background_tasks, task_title, True, playbook="01_source_settings.yml")
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Failed to create source: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error creating source.")


@router.get("/fetch_all", status_code=200)
def fetch_all_sources(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[Any]:
    sources = crud.source.get_all(db=db)
    return [formatted for s in sources if (formatted := get_formatted_entity(s, "source"))]


@router.get("/template", status_code=200)
def get_template(current_user: User = Depends(get_current_user)) -> List[Any]:
    return load_dynamic_templates("source")


@router.post("/template/by-type", status_code=200)
def get_template_by_type(
        *,
        body: TemplateTypeBody,
        current_user: User = Depends(get_current_user),
) -> Any:
    templates = load_dynamic_templates("source")
    for tmpl in templates:
        if tmpl["type"] == body.type:
            return tmpl
    raise HTTPException(status_code=404, detail=f"Source type '{body.type}' not found.")


@router.post("/fetch", status_code=200)
def fetch_source(
        *,
        body: FetchSourceBody,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> Any:
    src = crud.source.get(db=db, name=body.name)
    if not src:
        raise HTTPException(status_code=404, detail=f"Source '{body.name}' not found.")

    formatted = get_formatted_entity(src, "source")
    if not formatted:
        raise HTTPException(status_code=400, detail="Source template missing on disk.")
    return formatted


@router.put("/update", status_code=201)
def update_source(
        *,
        source_in: SourceUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    src = crud.source.get(db, name=source_in.name)
    if not src:
        raise HTTPException(status_code=404, detail=f"Source '{source_in.name}' not found.")

    if source_in.type and source_in.type != src.type:
        validate_source_type_dynamically(source_in.type)

    # Port change validation
    existing_port = extract_port(next((p.value for p in src.parameters if p.key == "address"), ""))
    mode = find_mode(source_in.settings)
    for setting in (source_in.settings or []):
        if setting.key == "address":
            port = extract_port(setting.value)
            if port and port != existing_port:
                result = port_in_use(db, port=port, protocol=mode)
                if result.get("inuse"):
                    raise HTTPException(status_code=400, detail=f"Port {port} in use by {result.get('service')}.")

    try:
        crud.source.update(db=db, db_obj=src, obj_in=source_in)
        return schedule_task(db, background_tasks, f"Update source {src.name}", True, playbook="01_source_settings.yml")
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Update failed for source {source_in.name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during source update.")


@router.delete("/delete", status_code=200)
def delete_source(
        *,
        body: DeleteSourceBody,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    src = crud.source.get(db, name=body.name)
    if not src:
        raise HTTPException(status_code=404, detail=f"Source '{body.name}' not found.")

    if src.system:
        raise HTTPException(status_code=400, detail=f"System source '{body.name}' cannot be deleted.")

    try:
        crud.source.delete_by_name(db, name=body.name)
        return schedule_task(db, background_tasks, f"Delete source {body.name}", True, playbook="01_source_settings.yml")
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Deletion failed for source {body.name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during source deletion.")
