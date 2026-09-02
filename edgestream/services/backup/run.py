"""
Project:   edgestream-api
File:      edgestream/services/backup/run.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from edgestream.core.config import Logger
from edgestream.services.config.exporter import export_yaml_configuration
from edgestream import crud
from edgestream.services.backup.providers import build_provider, prune_old
from edgestream.services.hostname import get_db_hostname, get_db_site_id, get_db_org_id


def _make_key(prefix: str, *, hostname: str, site_id: str, org_id: str, ts: datetime | None = None) -> str:
    stamp = (ts or datetime.utcnow()).strftime("%Y%m%dT%H%M%SZ")
    fname = f"{hostname}-{site_id}-{org_id}-config-{stamp}.yaml"
    p = (prefix or "").strip("/")
    return f"{p}/{fname}" if p else fname


def export_yaml_to_bytes(db: Session) -> bytes:
    export_yaml_configuration(db)  # writes to env-configured path
    directory_path = os.getenv("EDGESTREAM_CONFIGURATION_DIR")
    file_name = os.getenv("EDGESTREAM_CONFIGURATION")
    return (Path(directory_path) / file_name).read_bytes()


def run_backup_once(db: Session) -> dict:
    """
    Run backup for ALL enabled targets (file/s3/gcs).
    Returns a compact report.
    """
    targets = crud.backup.list_enabled(db)
    if not targets:
        return {"detail": "No enabled backup targets."}

    data = export_yaml_to_bytes(db)
    meta = dict(hostname=get_db_hostname(), site_id=get_db_site_id(), org_id=get_db_org_id())

    results: List[Dict[str, Any]] = []
    for cfg in targets:
        provider_name = (cfg.provider or "file").lower()
        try:
            provider = build_provider(cfg)
            key = _make_key(prefix=(cfg.path or ""), **meta)
            bucket = "" if provider_name == "file" else (cfg.bucket_name or "")
            provider.put(bytes_data=data, bucket=bucket, key=key)

            deleted = 0
            try:
                deleted = prune_old(
                    provider,
                    bucket=bucket,
                    prefix=(cfg.path or ""),
                    retention=(cfg.retention or "30d"),
                )
            except Exception as e:
                Logger.logger.warning(f"[backup:{provider_name}] retention prune failed: {e}")

            results.append({"provider": provider_name, "object": key, "deleted_old": deleted, "ok": True})
        except Exception as e:
            Logger.logger.error(f"[backup:{provider_name}] failed: {e}")
            results.append({"provider": provider_name, "error": str(e), "ok": False})

    return {"detail": "Backup completed", "results": results}
