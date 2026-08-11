import json
import os
import re
import subprocess
import tempfile
from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger, settings
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.schemas.event.transform import TransformCreate, TransformUpdate
from edgestream.schemas.event.transform_bodies import FetchTransformBody, DeleteTransformBody
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.services.vrl_parser import parse_condition

router = APIRouter()

# Supported transform types
TRANSFORM_SUPPORTED_TYPES = {"filter"}

DATADIR = os.getenv("EDGESTREAM_TMP_DIR", settings.EDGESTREAM_TMP_DIR) or tempfile.gettempdir()

# Template for validation via Vector binary
FILTER_TEMPLATE = """\
data_dir: "{datadir}"

sources:
  source_in:
    type: stdin

transforms:
  {transform_name}:
    type: filter
    inputs:
      - source_in
    condition:
      type: vrl
      source: '{transform_condition}'

sinks:
  sink_out:
    type: console
    inputs:
      - {transform_name}
    encoding:
      codec: json
"""


def _validate_name(name: str):
    """Ensures names match system-safe regex."""
    if not re.fullmatch(r"^[A-Za-z0-9_-]+$", (name or "")):
        raise HTTPException(
            status_code=400,
            detail="Invalid transform name. Use: letters, digits, underscores, and hyphens.",
        )


def _validate_and_extract_vrl(transform_in: TransformCreate | TransformUpdate) -> str:
    """
    Validates transform type and syntax. 
    If using QueryBuilder, it parses the JSON into raw VRL.
    """
    if (transform_in.type or "").lower() not in TRANSFORM_SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transform type. Supported: {sorted(TRANSFORM_SUPPORTED_TYPES)}.",
        )

    syntax = (transform_in.query_syntax or "").lower()
    if syntax == "query_builder":
        if not transform_in.query_builder:
            raise HTTPException(status_code=400, detail="Missing query builder data.")
        try:
            qb = transform_in.query_builder
            if isinstance(qb, str):
                qb = json.loads(qb)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid query builder JSON: {e.msg}")
        return parse_condition(qb)

    elif syntax == "vrl":
        if not transform_in.query_raw:
            raise HTTPException(status_code=400, detail="Missing raw VRL filter script.")
        return transform_in.query_raw

    else:
        raise HTTPException(status_code=400, detail="Unsupported syntax. Use 'query_builder' or 'vrl'.")


def _validate_vrl_with_vector(name: str, vrl_condition: str):
    """Dry-run validation using the Vector binary."""
    tmpdir = os.getenv("EDGESTREAM_TMP_DIR", settings.EDGESTREAM_TMP_DIR) or tempfile.gettempdir()
    os.makedirs(tmpdir, exist_ok=True)

    filled = FILTER_TEMPLATE.format(
        datadir=DATADIR,
        transform_name=name,
        transform_condition=vrl_condition.replace("'", "''")
    )

    tmpfile = os.path.join(tmpdir, f"validate_{os.urandom(8).hex()}.yaml")
    try:
        with open(tmpfile, "w") as f:
            f.write(filled)

        result = subprocess.run(
            ["vector", "validate", "--skip-healthchecks", tmpfile],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            error_output = result.stderr or result.stdout
            Logger.logger.info(f"VRL Validation Error: {error_output}")
            raise HTTPException(status_code=400, detail=f"VRL Syntax Error: {error_output}")

    finally:
        if os.path.exists(tmpfile):
            os.remove(tmpfile)


@router.post("/create", status_code=201)
def create_transform(
        *,
        transform_in: TransformCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    _validate_name(transform_in.name)
    vrl_condition = _validate_and_extract_vrl(transform_in)
    _validate_vrl_with_vector(transform_in.name, vrl_condition)

    try:
        transform_obj = crud.transform.create(db=db, obj_in=transform_in)
        return schedule_task(db, background_tasks, f"Create transform {transform_obj.name}", True)
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Transform creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error creating transform.")


@router.get("/fetch_all", status_code=200)
def fetch_all_transforms(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[Any]:
    transforms = crud.transform.get_all(db=db)
    return [
        {
            "name": t.name,
            "description": t.description,
            "type": t.type,
            "parent": t.parent,
            "query_syntax": t.query_syntax,
            "query_builder": t.query_builder,
            "query_raw": t.query_raw,
            "enabled": t.enabled,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }
        for t in transforms
    ]


@router.post("/fetch", status_code=200)
def fetch_transform(
        *,
        body: FetchTransformBody,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> Any:
    t = crud.transform.get(db, name=body.name)
    if not t:
        raise HTTPException(status_code=404, detail=f"Transform '{body.name}' not found.")
    return {
        "name": t.name,
        "description": t.description,
        "type": t.type,
        "parent": t.parent,
        "query_syntax": t.query_syntax,
        "query_builder": t.query_builder,
        "query_raw": t.query_raw,
        "enabled": t.enabled,
    }


@router.get("/parents", status_code=200)
def fetch_parents(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> List[str]:
    """Return a list of available input sources (parents) for transforms."""
    return crud.source.get_all_sources(db=db)


@router.put("/update", status_code=201)
def update_transform(
        *,
        transform_in: TransformUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    t = crud.transform.get(db, name=transform_in.name)
    if not t:
        raise HTTPException(status_code=404, detail=f"Transform '{transform_in.name}' not found.")

    vrl_condition = _validate_and_extract_vrl(transform_in)
    _validate_vrl_with_vector(transform_in.name, vrl_condition)

    try:
        updated = crud.transform.update(db=db, db_obj=t, obj_in=transform_in)
        return schedule_task(db, background_tasks, f"Update transform {updated.name}", True)
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Transform update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error updating transform.")


@router.delete("/delete", status_code=200)
def delete_transform(
        *,
        body: DeleteTransformBody,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    t = crud.transform.get(db, name=body.name)
    if not t:
        raise HTTPException(status_code=404, detail=f"Transform '{body.name}' not found.")

    try:
        crud.transform.delete(db, name=body.name)
        return schedule_task(db, background_tasks, f"Delete transform {body.name}", True)
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Transform deletion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during deletion.")
