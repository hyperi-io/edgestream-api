"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/task_status.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.db.db import get_db
from edgestream.services.auth.auth import get_system_or_user
from edgestream.schemas.system.task import TaskResponse, TaskUpdateSchema

router = APIRouter()


@router.get("", response_model=List[TaskResponse])
def get_all_tasks(
        db: Session = Depends(get_db),
        current_identity: Any = Depends(get_system_or_user),
) -> Any:
    """
    Fetch history of all background tasks.
    Returns the most recent 100 tasks by default.
    """
    return crud.task.get_multi(db, limit=100)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task_status(
        task_id: str,
        db: Session = Depends(get_db),
        current_identity: Any = Depends(get_system_or_user),
) -> Any:
    """
    Fetch the status of a specific task by its unique UUID identifier.
    """
    task = crud.task.get_by_identifier(db, identifier=task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    return task


@router.post("/id/{task_id}/update", status_code=status.HTTP_200_OK)
def update_task_status(
        task_id: str,
        payload: TaskUpdateSchema,
        db: Session = Depends(get_db),
        # Validates either a User Session or the Runner's System Token
        identity: Any = Depends(get_system_or_user),
) -> dict:
    """
    Internal endpoint used by the Ansible Runner to report execution progress,
    state changes (PENDING -> RUNNING -> COMPLETED), and log artifacts.
    """
    task_obj = crud.task.get_by_identifier(db, identifier=task_id)
    if not task_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )

    try:
        crud.task.update_status(db, db_obj=task_obj, obj_in=payload)
        return {"status": "success", "task_id": task_id}

    except HTTPException:
        raise
    except Exception as e:
        from edgestream.core.config import Logger
        Logger.logger.error(f"Ansible Runner failed to update task {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task progress."
        )
