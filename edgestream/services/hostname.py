"""
Project:   edgestream-api
File:      edgestream/services/hostname.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import socket
from typing import Optional

from edgestream.core.config import Logger
from edgestream.db.session import SessionLocal
from edgestream.models.system.system import System as SystemModel


def get_os_hostname() -> str:
    """Returns the hostname currently set at the Linux OS level."""
    return socket.gethostname()


def _get_system_record(db) -> Optional[SystemModel]:
    """
    Helper to fetch the singleton system record (ID 1).
    Uses the modern SQLAlchemy 2.0 session.get() method.
    """
    try:
        return db.get(SystemModel, 1)
    except Exception as e:
        Logger.logger.debug(f"System record fetch failed: {e}")
        return None


def get_db_hostname() -> str:
    """
    Resolves the hostname from the DB.
    Falls back to OS hostname if DB is empty or inaccessible.
    """
    try:
        with SessionLocal() as db:
            system = _get_system_record(db)
            if system and system.hostname:
                return str(system.hostname)
    except Exception as e:
        Logger.logger.warning(f"DB Hostname resolution failed, using OS default: {e}")

    return get_os_hostname() or "edgestream"


def get_db_org_id() -> str:
    """Retrieves the Organization ID from settings or returns 'edgestream' default."""
    try:
        with SessionLocal() as db:
            system = _get_system_record(db)
            return str(system.org_id) if system and system.org_id else "edgestream"
    except Exception as e:
        Logger.logger.error(f"Failed to resolve Org ID: {e}")
        return "edgestream"


def get_db_site_id() -> str:
    """Retrieves the Site ID from settings or returns 'edgestream' default."""
    try:
        with SessionLocal() as db:
            system = _get_system_record(db)
            return str(system.site_id) if system and system.site_id else "edgestream"
    except Exception as e:
        Logger.logger.error(f"Failed to resolve Site ID: {e}")
        return "edgestream"


def get_db_management_iface() -> Optional[str]:
    """Returns the designated management interface (e.g., 'eth0')."""
    try:
        with SessionLocal() as db:
            system = _get_system_record(db)
            return system.management_iface if system else None
    except Exception as e:
        Logger.logger.error(f"Failed to resolve management interface: {e}")
        return None
