"""
Project:   edgestream-api
File:      edgestream/schemas/system/log_viewer.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from pydantic import Field
from typing import Optional

from edgestream.schemas.base import ESBaseModel

class LogViewerBase(ESBaseModel):
    """
    Base schema for Log Viewer entries.
    """
    id: Optional[int] = Field(
        None,
        description="Unique identifier for the log viewer entry.",
        examples=[1],
    )
    filename: Optional[str] = Field(
        None,
        description="Path or filename of the log file.",
        examples=["/var/log/syslog"],
    )

class CreateLogViewer(LogViewerBase):
    """
    Schema for creating a new log viewer entry.
    """
    filename: str = Field(
        ...,
        description="Path or filename of the log file to be monitored.",
        examples=["/var/log/myapp.log"],
    )

class UpdateLogViewer(ESBaseModel):
    """
    Schema for updating an existing log viewer entry.
    All fields optional to support partial updates.
    """
    filename: Optional[str] = Field(
        None,
        description="Updated path or filename of the log file.",
        examples=["/var/log/updated_syslog.log"],
    )
