"""
Project:   edgestream-api
File:      edgestream/crud/event/syslog.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List, Tuple, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from edgestream.schemas.event.syslog import (
    SyslogPortCreate,
    SyslogPortUpdate,
    SyslogPort,
)
from edgestream.schemas.event.source import SourceCreate, SourceUpdate
from edgestream import crud
from edgestream.services.port_manager import get_settings_value


class CrudSyslog:
    """
    A specialized facade over crud.source specifically for managing syslog-ng listeners.
    """

    def create(self, db: Session, *, obj_in: SyslogPortCreate) -> Tuple[Any, Any]:
        """Creates a syslog-ng source with specific network parameters."""
        listen = [p.protocol for p in obj_in.protocols]

        data = {
            "name": obj_in.label,
            "type": "syslog_ng",
            "system": False,
            "enabled": True,
            "settings": [
                {"key": "port", "value": str(obj_in.port)},
                {"key": "tcp", "value": str("tcp" in listen).lower()},
                {"key": "udp", "value": str("udp" in listen).lower()},
            ],
        }
        return crud.source.create(db=db, obj_in=SourceCreate(**data))

    def update_by_name(self, db: Session, *, obj_in: SyslogPortUpdate) -> Any:
        """Updates an existing syslog listener by name."""
        src = crud.source.get(db, name=obj_in.name)
        if not src:
            raise HTTPException(status_code=404, detail="Syslog source not found.")

        listen = [p.protocol for p in obj_in.protocols]

        data = {
            "name": src.name,
            "type": "syslog_ng",
            "system": False,
            "enabled": True,
            "settings": [
                {"key": "port", "value": str(obj_in.port)},
                {"key": "tcp", "value": str("tcp" in listen).lower()},
                {"key": "udp", "value": str("udp" in listen).lower()},
            ],
        }

        updated, _ = crud.source.update(db=db, db_obj=src, obj_in=SourceUpdate(**data))
        return updated

    def delete_by_name(self, db: Session, *, name: str) -> bool:
        """Deletes a syslog listener."""
        src = crud.source.get(db, name=name)
        if not src:
            raise HTTPException(status_code=404, detail="Syslog source not found.")
        crud.source.delete_by_name(db, name=name)
        return True

    def list(self, db: Session) -> List[SyslogPort]:
        """Lists all syslog listeners, parsing the underlying source parameters."""
        rows = crud.source.get_all_syslog(db=db)
        out: List[SyslogPort] = []

        for row in rows:
            try:
                protos = []
                for p in ("tcp", "udp"):
                    v = get_settings_value(p, row.parameters)
                    if str(v).strip().lower() in ("1", "true", "yes"):
                        protos.append({"protocol": p})

                out.append(
                    SyslogPort(
                        id=row.id,
                        name=row.name,
                        port=int(get_settings_value("port", row.parameters)),
                        label=row.name,
                        protocols=protos,
                    )
                )
            except Exception:
                continue
        return out


syslog = CrudSyslog()
