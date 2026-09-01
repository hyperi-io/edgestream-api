"""
Project:   edgestream-api
File:      edgestream/services/background/ansible_tasks.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

import os
import json
import uuid
from typing import Optional

from fastapi import HTTPException, BackgroundTasks, status
from filelock import FileLock

from edgestream import crud
from edgestream.core.config import settings, Logger
from edgestream.db.session import SessionLocal
from edgestream.models.system.task import TaskState
from edgestream.services.config.exporter import export_yaml_configuration
from edgestream.schemas.system.task import TaskCreateSchema

# -------- Constants --------
QUEUE_DIR = os.getenv("EDGESTREAM_ANSIBLE_QUEUE", "/var/lib/edgestream/ansible-queue")


def _safe_lock_path() -> str:
    base = os.getenv("EDGESTREAM_RUN_DIR", "/var/lib/edgestream/run")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "edgestream-api.lock")


def _resolve_playbook_file(playbook_override: Optional[str]) -> str:
    fn = (playbook_override or settings.EDGESTREAM_TASK).strip()
    return os.path.basename(fn)


def _ansible_disabled() -> bool:
    return os.getenv("EDGESTREAM_DISABLE_ANSIBLE", "False").lower() == "true"


def enqueue_ansible_task(playbook_file: str, extra_vars: Optional[dict] = None, task_id: Optional[str] = None) -> str:
    os.makedirs(QUEUE_DIR, exist_ok=True)
    tid = task_id or str(uuid.uuid4())
    task_data = {
        "id": tid,
        "playbook": playbook_file,
        "extra_vars": extra_vars or {},
    }
    path = os.path.join(QUEUE_DIR, f"{tid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(task_data, f)
    return tid


# -------- Public API --------

def run_task(identifier: str, run_playbook: bool = True, playbook: Optional[str] = None) -> None:
    """
    Background worker: Exports configuration and enqueues Ansible jobs.
    """
    db = SessionLocal()
    try:
        lock = FileLock(_safe_lock_path())
        with lock:
            task_obj = crud.task.get_by_identifier(db, identifier)
            if not task_obj:
                Logger.logger.error(f"Background task {identifier} not found in DB.")
                return

            crud.task.update_status(db, db_obj=task_obj,
                                    obj_in={"state": TaskState.RUNNING, "detail": "Exporting system configuration..."})

            # Force a database commit here.
            db.commit()

            export_yaml_configuration(db)

            if run_playbook and not _ansible_disabled():
                playbook_file = _resolve_playbook_file(playbook)
                try:
                    enqueue_ansible_task(playbook_file=playbook_file, task_id=identifier)
                    Logger.logger.info(f"Queued Ansible task {identifier} using {playbook_file}")

                    crud.task.update_status(db, db_obj=task_obj,
                                            obj_in={"state": TaskState.QUEUED,
                                                    "detail": "Waiting for system runner..."})
                except Exception as error:
                    Logger.logger.exception("Failed to enqueue Ansible task")
                    crud.task.update_status(db, db_obj=task_obj,
                                            obj_in={"state": TaskState.FAILED, "detail": f"Queue error: {error}"})
            else:
                crud.task.update_status(db, db_obj=task_obj,
                                        obj_in={"state": TaskState.COMPLETED,
                                                "detail": "Config saved (No sync required)"})

    except Exception as error:
        Logger.logger.exception(f"Background task {identifier} encountered a fatal error")
        with SessionLocal() as error_db:
            err_task = crud.task.get_by_identifier(error_db, identifier)
            if err_task:
                crud.task.update_status(error_db, db_obj=err_task,
                                        obj_in={"state": TaskState.FAILED, "detail": f"System error: {str(error)}"})
    finally:
        db.close()


def schedule_task(
        db,
        background_tasks: BackgroundTasks,
        task_name: str,
        run_playbook: bool = True,
        playbook: Optional[str] = None,
):
    """
    Creates a Task record and schedules the background worker.
    """
    try:
        new_task_id = str(uuid.uuid4())
        # The schema now uses task_name, matching the DB Model
        task_in = TaskCreateSchema(
            identifier=new_task_id,
            task_name=task_name
        )

        task = crud.task.create(db=db, obj_in=task_in)

        background_tasks.add_task(run_task, task.identifier, run_playbook, playbook)

        return {"identifier": task.identifier, "detail": "System reconfiguration initiated."}

    except Exception as error:
        Logger.logger.error(f"Failed to schedule background task: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scheduling failure: {error}"
        )
