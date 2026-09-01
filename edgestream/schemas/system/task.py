"""
Project:   edgestream-api
File:      edgestream/schemas/system/task.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from edgestream.models.system.task import TaskState

class TaskBase(BaseModel):
    task_name: Optional[str] = None
    status: Optional[str] = None
    detail: Optional[str] = None
    processed: int = 0
    skipped: int = 0
    # FIX: Changed from 'failed' to 'failed_count' to match SQLAlchemy Model
    failed_count: int = 0

class TaskCreateSchema(TaskBase):
    identifier: str
    task_name: str

class TaskUpdateSchema(TaskBase):
    state: Optional[TaskState] = None

class TaskResponse(TaskBase):
    id: int
    identifier: str
    state: TaskState
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
