"""
Project:   edgestream-api
File:      edgestream/services/timezone.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

import pytz
import tzlocal

from edgestream.core.config import Logger
from edgestream.db.session import SessionLocal
from edgestream.models.system.system import System as SystemModel


def get_system_timezone() -> str:
    """
    Detects the current timezone set at the Linux OS level.
    Returns the IANA timezone string (e.g., 'America/New_York').
    """
    try:
        local_tz = tzlocal.get_localzone()
        return str(local_tz)
    except Exception as e:
        Logger.logger.warning(f"Could not detect OS timezone: {e}")
        return "UTC"


def is_valid_timezone(timezone_string: str) -> bool:
    """
    Validates a string against the IANA timezone database.
    """
    if not timezone_string:
        return False
    try:
        pytz.timezone(timezone_string)
        return True
    except (pytz.UnknownTimeZoneError, AttributeError, TypeError):
        return False


def get_db_timezone() -> str:
    """
    Retrieves the configured timezone from the Hub database.
    Falls back to 'UTC' if the database is uninitialized or inaccessible.
    """
    try:
        with SessionLocal() as db:
            system = db.get(SystemModel, 1)

            if system and system.timezone:
                return str(system.timezone)

    except Exception as e:
        Logger.logger.error(f"Database timezone resolution failed: {e}")

    return "UTC"
