from __future__ import annotations
import uuid
from typing import Any, List, Optional, Union, Dict
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from edgestream.crud.base import CRUDBase
from edgestream.models.system.task import Task, TaskState
from edgestream.schemas.system.task import TaskCreateSchema, TaskUpdateSchema


def _normalize_state(state: Union[str, TaskState]) -> TaskState:
    """Ensures input strings are converted to valid TaskState enum members."""
    if isinstance(state, TaskState):
        return state
    try:
        return TaskState(state.lower())
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid task state: {state!r}")


class CRUDTask(CRUDBase[Task, TaskCreateSchema, TaskUpdateSchema]):
    """
    CRUD operations for tracking asynchronous system tasks.
    """

    def get_all_by_state(self, db: Session, state: Union[str, TaskState]) -> List[Task]:
        """Fetch all tasks currently in a specific state."""
        st = _normalize_state(state)
        return list(
            db.execute(select(Task).where(Task.state == st)).scalars().all()
        )

    def get_by_identifier(self, db: Session, identifier: str) -> Optional[Task]:
        """Fetch a task by its unique UUID/tracking string."""
        return db.execute(
            select(Task).where(Task.identifier == identifier)
        ).scalar_one_or_none()

    def create_new_task(self, db: Session, task_name: str) -> Task:
        """
        Initializes a new background task with a generated UUID.
        """
        db_obj = Task(
            identifier=str(uuid.uuid4()),
            state=TaskState.PENDING,
            task_name=task_name, # Standardized name
        )
        try:
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create task record.") from e

    def update_status(
            self,
            db: Session,
            *,
            db_obj: Task,
            obj_in: Union[TaskUpdateSchema, Dict[str, Any]],
    ) -> Task:
        """
        Advanced update logic for Task tracking.
        - Normalizes state transitions.
        - Automatically captures 'completed_at' on terminal states.
        - Correctly updates integer counters even if they are 0.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        if "state" in update_data and update_data["state"] is not None:
            st = _normalize_state(update_data["state"])
            db_obj.state = st
            if st in (TaskState.COMPLETED, TaskState.FAILED):
                db_obj.completed_at = datetime.now()
            update_data.pop("state", None)

        field_mapping = {
            "task": "task_name",
            "failed": "failed_count"
        }

        allowed_fields = {
            "task", "detail", "processed", "skipped", "failed",
            "status", "completed_at", "artifacts"
        }

        for key, value in update_data.items():
            if key in allowed_fields:
                target_attr = field_mapping.get(key, key)
                if hasattr(db_obj, target_attr):
                    setattr(db_obj, target_attr, value)

        try:
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except Exception as e:
            db.rollback()
            from edgestream.core.config import Logger
            Logger.logger.error(f"Task update failed for {db_obj.identifier}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update task status.")


task = CRUDTask(Task)
