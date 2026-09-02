"""
Project:   edgestream-api
File:      edgestream/services/network_summary.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

import json
from subprocess import check_output, CalledProcessError
from typing import Any, Dict, List, Optional, Set, Tuple

from edgestream.db.session import SessionLocal
from edgestream.models.network.ip_management import IPManagement
from edgestream.core.config import Logger


def _safe_ip_json(cmd: List[str]) -> List[Dict[str, Any]]:
    """
    Safely executes an iproute2 command with JSON output.
    Returns an empty list if the command fails or output is malformed.
    """
    try:
        out = check_output(cmd, text=True)
        return json.loads(out) if out.strip() else []
    except (CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
        Logger.logger.debug(f"iproute2 command {cmd} failed: {e}")
        return []


def get_network_summary(db: Optional[SessionLocal] = None) -> Dict[str, Any]:
    """
    Correlates Linux kernel network state with Hub database settings to categorize
    interfaces into Management, Events, and Other groups.
    """
    addr_json = _safe_ip_json(["ip", "-j", "addr"])
    route_json = _safe_ip_json(["ip", "-j", "route"])

    default_gw_by_iface: Dict[str, str] = {}
    routes_by_iface: Dict[str, List[Dict[str, Any]]] = {}

    for r in route_json:
        dev = r.get("dev")
        if not dev:
            continue

        if r.get("dst") == "default" and r.get("via"):
            default_gw_by_iface[dev] = r.get("via")

        routes_by_iface.setdefault(dev, []).append({
            "dst": r.get("dst"),
            "via": r.get("via"),
            "src": r.get("prefsrc") or r.get("src"),
            "proto": r.get("protocol") or r.get("proto"),
            "metric": r.get("metric"),
        })

    static_pairs: Set[Tuple[str, str]] = set()
    mgmt_ifaces: Set[str] = set()
    event_ifaces: Set[str] = set()

    effective_db = db or SessionLocal()
    try:
        rows = effective_db.query(IPManagement).all()
        for row in rows:
            if (row.family or "").lower() == "ipv4":
                static_pairs.add((row.iface, row.ip_address))

            iface_type = (row.type or "").lower()
            if iface_type == "mgmt":
                mgmt_ifaces.add(row.iface)
            elif iface_type in {"event", "events"}:
                event_ifaces.add(row.iface)
    except Exception as e:
        Logger.logger.error(f"Failed to query IP management for summary: {e}")
    finally:
        if db is None:
            effective_db.close()

    items: List[Dict[str, Any]] = []
    for link in addr_json:
        iface = link.get("ifname")
        if not iface or iface == "lo":
            continue

        ipv4_info = [a for a in link.get("addr_info", []) if a.get("family") == "inet"]

        if not ipv4_info:
            items.append({
                "iface": iface,
                "label": f"{iface}: (no IPv4)",
                "mode": "unknown",
                "details": {
                    "ip": None, "netmask": None, "cidr": None,
                    "gateway": default_gw_by_iface.get(iface),
                    "routes": routes_by_iface.get(iface, []),
                },
            })
            continue

        addr_data = ipv4_info[0]
        ip = addr_data.get("local")
        prefixlen = addr_data.get("prefixlen")

        # Calculate human-readable netmask from CIDR prefix
        netmask = None
        if isinstance(prefixlen, int) and 0 <= prefixlen <= 32:
            mask_bits = (0xffffffff << (32 - prefixlen)) & 0xffffffff
            netmask = ".".join(str((mask_bits >> (8 * i)) & 0xff) for i in [24, 16, 8, 0])

        # Determine configuration mode
        is_dynamic = bool(addr_data.get("dynamic", False)) or "dynamic" in (addr_data.get("flags") or [])
        if ip and (iface, ip) in static_pairs:
            mode = "static"
        elif is_dynamic:
            mode = "dhcp"
        else:
            mode = "unknown"

        label = f"{iface}: {ip}/{prefixlen} ({mode})" if ip and prefixlen is not None else f"{iface}: (no IPv4)"

        items.append({
            "iface": iface,
            "label": label,
            "mode": mode,
            "details": {
                "ip": ip,
                "netmask": netmask,
                "cidr": f"{ip}/{prefixlen}" if ip and prefixlen is not None else None,
                "gateway": default_gw_by_iface.get(iface),
                "routes": routes_by_iface.get(iface, []),
            },
        })

    groups: List[Dict[str, Any]] = []
    if mgmt_ifaces or event_ifaces:
        mgmt_items = [it for it in items if it["iface"] in mgmt_ifaces]
        event_items = [it for it in items if it["iface"] in event_ifaces]
        others = [it for it in items if it["iface"] not in (mgmt_ifaces | event_ifaces)]

        if mgmt_items: groups.append({"title": "Management Interface(s)", "items": mgmt_items})
        if event_items: groups.append({"title": "Events Interface(s)", "items": event_items})
        if others: groups.append({"title": "Other Interface(s)", "items": others})
    else:
        groups.append({"title": "All Network Interface(s)", "items": items})

    return {"groups": groups}
