from __future__ import annotations

import io
import os
import tempfile
from typing import Any, Dict

from ruamel.yaml import YAML, RoundTripRepresenter
from fastapi import HTTPException
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import settings, Logger
from edgestream.schemas.value.settings_config import Configuration
from filelock import FileLock


class NonAliasingRTRepresenter(RoundTripRepresenter):
    """Prevents YAML aliases (*id001) for human-readable and Ansible-friendly output."""
    def ignore_aliases(self, data):
        return True


def sequence_indent_four(s: str) -> str:
    """Post-processor to ensure nested YAML lists use 4-space indentation."""
    levels, ret_val = [], ""
    for line in s.splitlines(True):
        ls = line.lstrip()
        indent = len(line) - len(ls)
        if ls.startswith("- "):
            if not levels or indent > levels[-1]:
                levels.append(indent)
            elif indent < levels[-1]:
                levels.pop()
        else:
            while levels and indent <= levels[-1]:
                levels.pop()
        ret_val += "  " * len(levels) + line
    return ret_val


def export_yaml_configuration(db: Session) -> None:
    """
    Serializes the entire Hub database into a single YAML file.
    Uses a FileLock and Atomic Replace to ensure system stability.
    """
    try:
        # Construct the strict model using our unified CRUD export API
        cfg = Configuration(
            version=1,
            system=crud.system.export(db=db),  # Unified
            sources=crud.source.export(db=db),
            transforms=crud.transform.export(db=db),
            destinations=crud.destination.export(db=db),
            certificates=crud.certificate.export(db=db),
            networks={
                "ntp": crud.ntp.export(db=db),
                "dns": crud.dns.export(db=db),
                "static_hosts": crud.static_host.export(db=db),
                "dns_forwarders": crud.dns_forwarder.export(db=db),
                "static_routes": crud.static_route.export(db=db),
                "ip_management": crud.ip_mgmt.export(db=db),
            },
            vpn=crud.vpnclient.export(db=db),
            advanced=crud.advanced_setting.export(db=db),
            logs=crud.log_viewer.export(db=db),
            backup=crud.backup.export(db=db),  # Unified - handles all providers
            users=crud.user.export(db=db),    # Added: includes accounts (minus passwords)
        )

        yml = YAML()
        yml.Representer = NonAliasingRTRepresenter

        buf = io.StringIO()
        # Use model_dump() to ensure Pydantic validates the structure
        yml.dump(cfg.model_dump(exclude_none=True), buf, transform=sequence_indent_four)

        # Filesystem Write Logic
        dir_path = settings.EDGESTREAM_CONFIGURATION_DIR
        file_name = settings.EDGESTREAM_CONFIGURATION
        target_path = os.path.join(dir_path, file_name)

        os.makedirs(dir_path, exist_ok=True)

        # Synchronized atomic write
        lock_file = os.path.join(settings.EDGESTREAM_TMP_DIR, "config-export.lock")
        os.makedirs(os.path.dirname(lock_file), exist_ok=True)

        with FileLock(lock_file):
            with tempfile.NamedTemporaryFile("w", dir=dir_path, delete=False) as tmp:
                tmp.write(buf.getvalue())
                tmp.flush()
                os.fsync(tmp.fileno())
                tmp_path = tmp.name

            os.chmod(tmp_path, 0o600)  # Secure: Only readable by the API user
            os.replace(tmp_path, target_path)

        Logger.logger.info(f"System configuration exported successfully to {target_path}")

    except Exception as error:
        Logger.logger.error(f"Configuration export failed: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate system configuration file.")