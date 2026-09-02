"""
Project:   edgestream-api
File:      edgestream/crud/system/log_viewer.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from edgestream.crud.base import CRUDBase
from edgestream.models.system.log_viewer import LogViewer
from edgestream.schemas.system.log_viewer import CreateLogViewer, UpdateLogViewer


class CRUDLogViewer(CRUDBase[LogViewer, CreateLogViewer, UpdateLogViewer]):
    """
    CRUD operations for managing log file paths and monitoring status
    in the Log Viewer interface.
    """

    def export(self, db: Session) -> List[Dict[str, Any]]:
        """
        Unified export method for the Configuration Exporter.
        Serializes the whitelist of monitored log files.
        """
        rows = self.get_all(db)
        return [
            {
                "filename": r.filename,
                "enabled": bool(r.enabled)
            }
            for r in rows
        ]

    def get_all(self, db: Session) -> List[LogViewer]:
        """
        Retrieve all LogViewer records using SQLAlchemy 2.0 syntax.
        """
        return list(db.execute(select(LogViewer)).scalars().all())

    def get_enabled(self, db: Session) -> List[LogViewer]:
        """
        Retrieve only logs that are currently marked as enabled for monitoring.
        """
        return list(
            db.execute(
                select(LogViewer).where(LogViewer.enabled == True)
            ).scalars().all()
        )


log_viewer = CRUDLogViewer(LogViewer)
