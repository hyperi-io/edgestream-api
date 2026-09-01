"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/system_services.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations
import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import psutil
import requests
import yaml
from fastapi import APIRouter

from edgestream.core.config import settings, Logger

router = APIRouter()

# Prioritize environment variable over standardized install paths
CONFIG_PATHS = [
    os.environ.get("EDGESTREAM_SERVICES_CONFIG") or "/etc/edgestream/services.yml",
    "/opt/edgestream-core/config/services.yml",
]


@dataclass
class ServiceCheck:
    key: str
    name: str
    unit: str
    ports: List[Any]
    health_url: Optional[str] = None
    optional: bool = False
    disabled: bool = False


def _load_config() -> List[ServiceCheck]:
    """Resolves the service monitoring configuration file."""
    path = next((p for p in CONFIG_PATHS if p and os.path.exists(p)), None)

    if not path:
        # Minimum operational defaults if config is missing
        cfg = {
            "services": [
                {"key": "vector", "name": "Vector Pipeline", "unit": "vector.service", "ports": []},
                {"key": "syslog", "name": "System Logger", "unit": "rsyslog.service", "ports": []},
            ]
        }
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                if path.endswith(".json"):
                    cfg = json.load(f)
                else:
                    cfg = yaml.safe_load(f) or {}
        except Exception as e:
            Logger.logger.error(f"Failed to parse services config at {path}: {e}")
            cfg = {"services": []}

    return [
        ServiceCheck(
            key=s.get("key") or s.get("unit"),
            name=s.get("name") or s.get("unit"),
            unit=s.get("unit", ""),
            ports=s.get("ports") or [],
            health_url=s.get("health_url"),
            optional=bool(s.get("optional", False)),
            disabled=bool(s.get("disabled", False)),
        )
        for s in cfg.get("services", [])
    ]


def _systemctl_show(unit: str) -> Dict[str, str]:
    """Query systemd for unit properties via dbus-proxy (subprocess)."""
    props = [
        "ActiveState", "SubState", "ExecMainPID", "UnitFileState",
        "InactiveExitTimestampMonotonic", "ActiveEnterTimestampMonotonic"
    ]
    try:
        cp = subprocess.run(
            ["systemctl", "show", unit, f"--property={','.join(props)}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, timeout=2
        )
        if cp.returncode != 0:
            return {}
    except subprocess.TimeoutExpired:
        Logger.logger.warning(f"Systemctl query timed out for {unit}")
        return {}
    except Exception:
        return {}

    data: Dict[str, str] = {}
    for line in (cp.stdout or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def _since_seconds(props: Dict[str, str]) -> Optional[int]:
    """Calculate uptime based on systemd monotonic timestamps."""
    try:
        active_enter = int(props.get("ActiveEnterTimestampMonotonic", "0"))
        if active_enter > 0:
            # systemd monotonic is in microseconds
            now_us = int(time.monotonic() * 1_000_000)
            return max(0, (now_us - active_enter) // 1_000_000)
    except Exception:
        pass
    return None


def _port_open_tcp(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    """Check if a TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _udp_port_bound(port: int, host: Optional[str] = None) -> bool:
    """Check if a process is listening on the specified UDP port."""
    try:
        conns = psutil.net_connections(kind="udp")
        wildcards = {"0.0.0.0", "::", "*"}
        for c in conns:
            if c.laddr and c.laddr.port == port:
                l_ip = c.laddr.ip
                if host in (None, "", "127.0.0.1"):
                    if l_ip in wildcards or l_ip == "127.0.0.1":
                        return True
                elif l_ip in wildcards or l_ip == host:
                    return True
    except Exception:
        pass
    return False


def _normalize_port_spec(item: Any, default_host: str = "127.0.0.1") -> Dict[str, Any]:
    """Normalizes various port specification formats (int, str, dict)."""
    if isinstance(item, int):
        return {"host": default_host, "port": item, "proto": "tcp"}

    if isinstance(item, str):
        s = item.strip()
        proto = "tcp"
        if "/" in s:
            s, proto = s.rsplit("/", 1)
            proto = proto.lower()

        host = default_host
        if s.startswith("["):  # IPv6 Support
            end = s.find("]")
            if end != -1 and ":" in s[end:]:
                host = s[1:end]
                port = int(s[end + 2:])
            else:
                raise ValueError(f"Invalid IPv6 port spec: {item}")
        elif ":" in s:
            host, p = s.rsplit(":", 1)
            port = int(p)
        else:
            port = int(s)

        return {"host": host, "port": port, "proto": proto}

    if isinstance(item, dict):
        return {
            "host": item.get("host", default_host),
            "port": int(item["port"]),
            "proto": item.get("proto", "tcp").lower(),
        }
    return {"host": default_host, "port": 0, "proto": "tcp"}


def _http_ok(url: str, timeout: float = 1.0) -> bool:
    """
    Perform a health check against a service's HTTP status endpoint.
    Handles SSL and Connection errors gracefully.
    """
    try:
        r = requests.get(url, timeout=timeout, verify=True, allow_redirects=True)
        return 200 <= r.status_code < 400
    except requests.exceptions.SSLError:
        Logger.logger.warning(f"Health check SSL validation failed for {url}")
        return False
    except requests.exceptions.ConnectionError:
        # Service is likely down or port is closed
        return False
    except Exception as e:
        Logger.logger.debug(f"Health check failed for {url}: {e}")
        return False


def _pid_stats(pid_str: str) -> Dict[str, Any]:
    """Gather CPU and Memory metrics for a specific process ID."""
    try:
        pid = int(pid_str)
        if pid <= 0: return {}
        p = psutil.Process(pid)
        with p.oneshot():
            return {
                "pid": pid,
                "cpu_pct": round(p.cpu_percent(interval=None), 1),
                "mem_pct": round(p.memory_percent(), 1)
            }
    except Exception:
        return {}


def _derive_status(active: str, ports_ok: bool, http_ok: Optional[bool], disabled: bool) -> str:
    """Determine the status enum for the UI."""
    if disabled: return "disabled"
    if active != "active": return "down"
    if http_ok is False or not ports_ok: return "degraded"
    return "healthy"


@router.get("/status", summary="Service health overview")
def get_services_status() -> Dict[str, Any]:
    """
    Analyzes systemd services, process metrics, and network listeners 
    to provide a comprehensive system health report.
    """
    checks = _load_config()
    results: List[Dict[str, Any]] = []

    for c in checks:
        props = _systemctl_show(c.unit)
        active = props.get("ActiveState", "unknown")

        pid_info = _pid_stats(props.get("ExecMainPID", "0"))

        ports_ok = True
        port_results = []
        for p in c.ports:
            spec = _normalize_port_spec(p)
            ok = _udp_port_bound(spec["port"], spec["host"]) if spec["proto"] == "udp" else _port_open_tcp(spec["port"],
                                                                                                           spec["host"])
            port_results.append({**spec, "ok": ok})
            if not ok: ports_ok = False

        http_ok = _http_ok(c.health_url) if c.health_url else None
        current_status = _derive_status(active, ports_ok, http_ok, c.disabled)

        results.append({
            "key": c.key,
            "name": c.name,
            "unit": c.unit,
            "enabled": props.get("UnitFileState", "unknown"),
            "active": active,
            "substate": props.get("SubState", "unknown"),
            "uptime_seconds": _since_seconds(props),
            "pid": pid_info.get("pid"),
            "cpu_pct": pid_info.get("cpu_pct"),
            "mem_pct": pid_info.get("mem_pct"),
            "ports": port_results,
            "ports_ok": ports_ok,
            "health_url": c.health_url,
            "http_ok": http_ok,
            "optional": c.optional,
            "disabled": c.disabled,
            "status": current_status,
        })

    monitored = [r for r in results if not r["optional"] and not r["disabled"]]
    if any(r["status"] == "down" for r in monitored):
        overall = "down"
    elif any(r["status"] == "degraded" for r in monitored):
        overall = "degraded"
    else:
        overall = "healthy"

    return {"overall": overall, "services": results, "version": settings.VERSION}
