"""
Project:   edgestream-api
File:      edgestream/services/apt_helpers.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

import re
import subprocess
from typing import List, Dict, Any

from edgestream.core.config import Logger


# ---- Exceptions --------------------------------------------------------------

class RootHelperError(Exception):
    """Base class for privileged update failures."""


class RootHelperNotFound(RootHelperError):
    """The privileged systemd unit or binary wasn't found."""


class RootHelperPrivilegeError(RootHelperError):
    """Policy prevented the action (e.g., polkit denied, not authorized)."""


class RootHelperExecutionError(RootHelperError):
    """The privileged command executed but failed (non-zero exit)."""


# ---- Validation & Internals --------------------------------------------------

# Validates package names to prevent command injection in the CSV string
_PKG_RE = re.compile(r"^[A-Za-z0-9.+-]+$")


def _systemd_start(instance_arg: str) -> None:
    """
    Executes a privileged task by starting a systemd oneshot unit instance.
    Uses 'systemd-escape' to safely format the argument into the unit name.
    """
    try:
        # Escape the argument (e.g., "upgrade:bash,libc6")
        esc = subprocess.run(
            ["systemd-escape", "--template=edgestream-update@.service", instance_arg],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=5
        )
    except FileNotFoundError:
        raise RootHelperNotFound("Binary 'systemd-escape' is missing from the host.")

    if esc.returncode != 0:
        raise RootHelperExecutionError(f"Argument escaping failed: {esc.stdout}")

    unit = (esc.stdout or "").strip()

    try:
        # Start the unit via sudo to bypass interactive agents and NoNewPrivileges limitations
        proc = subprocess.run(
            ["sudo", "/usr/bin/systemctl", "start", "--wait", unit],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=120
        )
    except FileNotFoundError:
        raise RootHelperNotFound("Binary 'sudo' or 'systemctl' is missing from the host.")

    output = (proc.stdout or "").lower()
    rc = proc.returncode

    if rc == 0:
        Logger.logger.info(f"Privileged task successful: {unit}")
        return

    Logger.logger.error(f"Privileged task {unit} (output={output}) (rc={rc}): {output}")

    # Check for specifically classified failures
    if "unit" in output and "not found" in output:
        raise RootHelperNotFound(f"Service template {unit} is not installed.")

    privilege_errors = [
        "access denied", "polkit", "not authorized",
        "authorization failed", "interactive authentication required"
    ]
    if any(err in output for err in privilege_errors):
        raise RootHelperPrivilegeError(
            "Privilege escalation denied. Check Polkit policies for edgestream-update."
        )

    Logger.logger.error(f"Privileged task {unit} failed (rc={rc}): {output}")
    raise RootHelperExecutionError(f"Systemd operation failed: {output}")


# ---- Public API --------------------------------------------------------------

def get_apt_available_packages() -> List[Dict[str, Any]]:
    """
    Retrieves the list of upgradable packages. 
    This does not require root privileges and does not take the APT lock.
    """
    try:
        proc = subprocess.run(
            ["apt", "list", "--upgradable"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10
        )
        output = proc.stdout or ""
    except Exception as e:
        Logger.logger.error(f"Package list retrieval failed: {e}")
        return []

    pkgs: List[Dict[str, Any]] = []
    skip_prefixes = ("Listing", "WARNING", "W:", "N:", "E:", "Err:")

    pkg_line_rx = re.compile(
        r"^([A-Za-z0-9.+-]+)\/\S+\s+(\S+)\s+\S+(?:\s+\[upgradable from:\s*([^\]]+)\])?",
        re.IGNORECASE,
    )

    for raw in output.splitlines():
        line = raw.strip()
        if not line or line.startswith(skip_prefixes):
            continue

        match = pkg_line_rx.match(line)
        if not match:
            continue

        name, candidate, current = match.group(1), match.group(2), (match.group(3) or None)

        if not _PKG_RE.match(name):
            continue

        pkgs.append({
            "package": name,
            "current_version": current,
            "available_version": candidate,
            "archive": None,
            "origin": None,
            "site": None,
            "description": None,
        })

    return pkgs


def apt_update_packagelist() -> None:
    """Refreshes the local APT cache via the systemd privileged helper."""
    _systemd_start("refresh")


def upgrade_packages(pkgs_in: List[str]) -> None:
    """Upgrades a specific list of packages via the systemd privileged helper."""
    if not pkgs_in:
        return

    safe_pkgs = []
    invalid_pkgs = []

    for p in pkgs_in:
        cleaned = (p or "").strip()
        if _PKG_RE.match(cleaned):
            safe_pkgs.append(cleaned)
        else:
            invalid_pkgs.append(p)

    if invalid_pkgs:
        raise ValueError(f"Aborting upgrade: Invalid package names detected: {invalid_pkgs}")

    csv_pkgs = ",".join(safe_pkgs)
    _systemd_start(f"upgrade:{csv_pkgs}")
