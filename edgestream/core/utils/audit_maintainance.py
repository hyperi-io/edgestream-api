"""
Project:   edgestream-api
File:      edgestream/core/utils/audit_maintainance.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import os
import gzip
import json
import datetime
from pathlib import Path
from sqlalchemy import delete
from edgestream.db.session import SessionLocal
from edgestream.core.config import Logger
from edgestream.models.system.audit import AuditEvent


def maintenance_rotate_audit_logs(export_dir: str = "/var/lib/edgestream/audit_backups"):
    """
    CLI Utility: Exports all existing audit events to a compressed JSONL file
    and purges the database table.
    """
    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"audit_export_{timestamp}.jsonl.gz"
    full_path = export_path / filename

    db = SessionLocal()
    try:
        events = db.query(AuditEvent).all()
        if not events:
            print("Audit table is empty. Nothing to rotate.")
            return

        print(f"Exporting {len(events)} events to {full_path}...")

        with gzip.open(full_path, "wt", encoding="utf-8") as f:
            for ev in events:
                data = {
                    "id": ev.id,
                    "event_type": ev.event_type,
                    "result": ev.result,
                    "actor_id": ev.actor_id,
                    "actor_type": ev.actor_type,
                    "ip": ev.ip,
                    "route": ev.route,
                    "status_code": ev.status_code,
                    "created_at": ev.created_at.isoformat() if ev.created_at else None,
                    "details": ev.details
                }
                f.write(json.dumps(data) + "\n")

        print("Export successful. Purging database table...")
        db.execute(delete(AuditEvent))
        db.commit()

        os.chmod(full_path, 0o600)
        print(f"Rotation complete. Database table cleared.")

    except Exception as e:
        db.rollback()
        Logger.logger.error(f"Audit maintenance failed: {e}")
        print(f"FATAL: Maintenance failed. Database rolled back. Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    # Can be run from cli:
    # python3 -m edgestream.core.utils.audit_maintenance
    maintenance_rotate_audit_logs()
