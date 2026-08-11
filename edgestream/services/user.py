from __future__ import annotations

import datetime
import subprocess
import shutil
import platform
import os
import re
from typing import List, Optional

import psutil
from fastapi import HTTPException, status

from edgestream.core.config import Logger
from edgestream.schemas.system.system import LastUser


def get_current_active_users() -> List[dict]:
    """
    Retrieves a simple list of currently logged-in OS users.
    Primarily used for high-level system telemetry.
    """
    ps_users = psutil.users()
    users = []
    for user in ps_users:
        users.append({
            "name": user.name,
            "terminal": user.terminal,
            "host": user.host,
            "started": user.started,
            "pid": getattr(user, "pid", None),
        })
    return users


def _fallback_from_psutil() -> List[LastUser]:
    """
    Portable fallback: Returns currently logged-in users 
    formatted as LastUser objects when the 'last' command fails.
    """
    out: List[LastUser] = []
    now = datetime.datetime.now()
    for u in psutil.users():
        started_dt = datetime.datetime.fromtimestamp(u.started) if u.started else now
        dur = now - started_dt
        duration_str = "{:02}:{:02}".format(dur.seconds // 3600, (dur.seconds % 3600) // 60)

        out.append(
            LastUser(
                username=u.name,
                terminal=u.terminal or "?",
                host=u.host or "?",
                logged_in=started_dt.strftime("%a %b %d %H:%M"),
                duration=duration_str,
                active=True,
            )
        )
    return out


def get_last_users() -> List[LastUser]:
    """
    Parses the system login history (wtmp) using the 'last' command.
    Includes logic to identify currently active vs. historical sessions.
    """
    is_linux = platform.system().lower() == "linux"

    if os.getenv("EDGESTREAM_STRICT_LAST", "").lower() == "true" and not is_linux:
        Logger.logger.error("STRICT_LAST check failed: Platform is not Linux")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The 'last' command requires a Linux-based environment."
        )

    if not is_linux:
        return _fallback_from_psutil()

    last_path = shutil.which("last") or "/usr/bin/last"
    if not os.path.exists(last_path):
        Logger.logger.warning(f"'last' utility not found at {last_path}; falling back to psutil.")
        return _fallback_from_psutil()

    try:
        proc = subprocess.run(
            [last_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=3.0,
        )
    except Exception as exc:
        Logger.logger.error(f"Error executing 'last' command: {exc}; using psutil fallback.")
        return _fallback_from_psutil()

    active_rx = re.compile(
        r"([^ ]+)\s+(system boot|[^ ]+)\s+([^ ]+)\s+([A-Za-z]{3} [A-Za-z]{3} \d+ \d+:\d+).*still logged in"
    )
    inactive_rx = re.compile(
        r"([^ ]+)\s+(system boot|[^ ]+)\s+([^ ]+)\s+([A-Za-z]{3} [A-Za-z]{3} \d+ \d+:\d+).*\(([^)]+)\)"
    )

    def parse_line(line: str) -> Optional[LastUser]:
        if match := active_rx.search(line):
            try:
                start_ts = datetime.datetime.strptime(
                    f"{datetime.datetime.now().year} {match.group(4)}", "%Y %a %b %d %H:%M"
                )
                duration = datetime.datetime.now() - start_ts
                duration_str = "{:02}:{:02}".format(duration.seconds // 3600, (duration.seconds % 3600) // 60)
            except ValueError:
                duration_str = "00:00"

            return LastUser(
                username=match.group(1),
                terminal=match.group(2),
                host=match.group(3),
                logged_in=match.group(4),
                duration=duration_str,
                active=True,
            )

        if match := inactive_rx.search(line):
            if match.group(2) == "system boot":
                return None  # Skip system boot entries

            return LastUser(
                username=match.group(1),
                terminal=match.group(2),
                host=match.group(3),
                logged_in=match.group(4),
                duration=match.group(5),
                active=False,
            )
        return None

    users = [entry for line in proc.stdout.splitlines() if (entry := parse_line(line))]
    return users
