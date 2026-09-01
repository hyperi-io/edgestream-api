"""
Project:   edgestream-api
File:      edgestream/services/uptime.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

import datetime
import time
from typing import Dict, Union

import psutil


def _format_period(delta: datetime.timedelta, pattern: str) -> str:
    """
    Helper to extract time components from a timedelta and apply a format string.
    """
    d = {"d": delta.days}
    d["h"], rem = divmod(delta.seconds, 3600)
    d["m"], d["s"] = divmod(rem, 60)
    return pattern.format(**d)


def get_uptime() -> Dict[str, Union[int, str]]:
    """
    Calculates the system uptime since the last boot.
    Returns both raw seconds and a context-aware human-readable string.
    """
    uptime_seconds = int(time.time() - psutil.boot_time())

    thresholds = [
        (60, "{s} secs"),
        (120, "{m} min {s} secs"),
        (3600, "{m} mins {s} secs"),
        (7200, "{h} hour {m} mins {s} secs"),
        (86400, "{h} hours {m} mins {s} secs"),
        (172800, "{d} day {h} hours {m} mins {s} secs"),
    ]

    for limit, pattern in thresholds:
        if uptime_seconds < limit:
            formatted = _format_period(datetime.timedelta(seconds=uptime_seconds), pattern)
            break
    else:
        formatted = _format_period(
            datetime.timedelta(seconds=uptime_seconds),
            "{d} days {h} hours {m} mins {s} secs"
        )

    return {
        "secs": uptime_seconds,
        "human_readable": formatted
    }
