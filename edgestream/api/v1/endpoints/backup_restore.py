"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/backup_restore.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import os
from typing import Annotated, List, Dict, Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import settings, Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.services.auth.auth import get_system_or_user, get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.services.config.exporter import export_yaml_configuration
from edgestream.services.config.importer import import_settings
from edgestream.schemas.system.backup import (
    BackupTargetResponse, BackupTargetsResponse
)

router = APIRouter()


@router.get("/export", status_code=200)
def export_collector_configuration(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_system_or_user),
) -> FileResponse:
    """
    Manually export a collector configuration backup file (.yaml).
    """
    directory_path = os.getenv("EDGESTREAM_CONFIGURATION_DIR", settings.EDGESTREAM_CONFIGURATION_DIR)
    file_path = os.getenv("EDGESTREAM_CONFIGURATION", settings.EDGESTREAM_CONFIGURATION)

    try:
        filename = os.path.join(directory_path, file_path)
        export_yaml_configuration(db)  # Generate configuration
        return FileResponse(
            path=filename,
            media_type="application/x-yaml",
            filename=file_path,
        )
    except Exception as error:
        Logger.logger.error(f"Error exporting config: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate or export configuration file.")


@router.post("/restore", status_code=201)
async def restore_collector_configuration(
        config_yaml: Annotated[UploadFile, File()],
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Restore Collector configuration from a configuration backup file (.yaml).
    """
    try:
        contents = await config_yaml.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        import_settings(yaml.safe_load(contents), db)
        return schedule_task(db, background_tasks, "Restoring collector config", run_playbook=True)

    except yaml.YAMLError as yaml_error:
        raise HTTPException(status_code=400, detail=f"Invalid YAML content: {yaml_error}")
    except HTTPException:
        raise
    except Exception as error:
        Logger.logger.error(f"Restore failed: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error restoring configuration.")


@router.post("/install", status_code=201)
async def install_collector_configuration(
        config_yaml: Annotated[UploadFile, File()],
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Install Collector configuration from a configuration backup file (.yaml).
    """
    try:
        contents = await config_yaml.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        import_settings(yaml.safe_load(contents), db)
        return schedule_task(db, background_tasks, "Installing collector config", run_playbook=True,
                             playbook="restore.yml")

    except yaml.YAMLError as yaml_error:
        raise HTTPException(status_code=400, detail=f"Invalid YAML content: {yaml_error}")
    except HTTPException:
        raise
    except Exception as error:
        Logger.logger.error(f"Installation failed: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error installing configuration.")


@router.get("", response_model=BackupTargetsResponse, status_code=200)
async def configuration_backup_get(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> BackupTargetsResponse:
    """
    Return one backup row per provider (file/s3/gcs).
    """
    try:
        rows = crud.backup.get_all(db)
        by_prov = {(r.provider or "").lower(): r for r in rows}

        targets: List[BackupTargetResponse] = []
        for prov in ("file", "s3", "gcs"):
            if prov in by_prov:
                targets.append(BackupTargetResponse.model_validate(by_prov[prov]))
            else:
                targets.append(BackupTargetResponse(
                    enabled=False,
                    provider=prov,
                    path="",
                    bucket_name="",
                    region="",
                    access_key_id="",
                    secret_access_key="",
                    endpoint_url="",
                    gcs_project_id="",
                    gcs_credentials_json="",
                    retention="30d",
                    schedule="12h"
                ))
        return BackupTargetsResponse(targets=targets)

    except Exception as error:
        Logger.logger.error(f"Error retrieving backup targets: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to retrieve backup targets.")


@router.post("", status_code=201)
async def configuration_backup_post(
        payload: Dict[str, Any],
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Upsert backup targets (supports both bulk and legacy single-object payloads).
    """
    try:
        items = payload["targets"] if isinstance(payload.get("targets"), list) else [payload]

        for item in items:
            provider = (item.get("provider") or "").lower()
            if provider not in ("file", "s3", "gcs"):
                raise HTTPException(status_code=400, detail=f"Unsupported provider: {item.get('provider')}")

            crud.backup.upsert_by_provider(db, provider, item)

        return schedule_task(db, background_tasks, "Updating backup targets.", True)

    except HTTPException:
        raise
    except Exception as error:
        Logger.logger.error(f"Error setting backup targets: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to set backup targets.")
