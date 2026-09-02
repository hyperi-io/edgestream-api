"""
Project:   edgestream-api
File:      edgestream/services/interfaces.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

import os
import socket
import psutil
import platform
import netifaces
from typing import List, Dict, Optional

from edgestream.core.config import Logger
from edgestream.db.session import SessionLocal
from edgestream.models.network.ip_management import IPManagement


def get_interfaces() -> List[Dict[str, Optional[str]]]:
    """
    Scans the OS for physical and virtual network interfaces.
    Returns details including device name, MAC, IP, and default gateways.
    """
    try:
        default_gw = netifaces.gateways().get("default", {})
    except (OSError, AttributeError) as e:
        Logger.logger.warning(f"Failed to resolve default gateway: {e}")
        default_gw = {}

    # Guard: Ensure we are on a compatible Linux environment
    if platform.system().lower() != "linux" or not os.path.isdir("/sys/class/net"):
        return []

    # Resolve Default Gateway details
    # netifaces returns: {AF_INET: (ip, interface)}
    gw_info = default_gw.get(netifaces.AF_INET, (None, None))
    default_gw_addr, default_gw_device = gw_info[0], gw_info[1]

    try:
        # Exclude 'lo' (loopback)
        all_ifaces = [iface for iface in os.listdir("/sys/class/net") if iface != "lo"]
    except OSError:
        return []

    if_addrs = psutil.net_if_addrs()
    interfaces = []

    for iface in all_ifaces:
        addrs = if_addrs.get(iface, [])

        # AF_INET = IPv4
        ip_info = next((a for a in addrs if a.family == socket.AF_INET), None)
        # AF_LINK = MAC Address (on Linux/Unix)
        mac_info = next((a for a in addrs if a.family == psutil.AF_LINK), None)

        interfaces.append({
            "device": iface,
            "mac_address": getattr(mac_info, "address", None),
            "ip_address": getattr(ip_info, "address", None),
            "netmask": getattr(ip_info, "netmask", None),
            "gateway": default_gw_addr if iface == default_gw_device else None,
        })

    return interfaces


def get_ipv6_addresses() -> List[str]:
    """Retrieves all global and link-local IPv6 addresses from the host."""
    ps_net_if_addrs = psutil.net_if_addrs()
    ipv6_list = []
    for iface_name in ps_net_if_addrs:
        for addr in ps_net_if_addrs[iface_name]:
            if addr.family == socket.AF_INET6:
                ipv6_list.append(addr.address)
    return ipv6_list


def get_ipv4_addresses() -> List[str]:
    """
    Retrieves the management and event IP addresses from the DB.
    Used for system identification and telemetry.
    """
    ip_addresses = []
    with SessionLocal() as db:
        try:
            for iface_type in ["mgmt", "event"]:
                record = db.query(IPManagement).filter(IPManagement.type == iface_type).first()
                if record and record.ip_address:
                    ip_addresses.append(record.ip_address)
                else:
                    ip_addresses.append("0.0.0.0")
        except Exception as exc:
            Logger.logger.error(f"Failed to retrieve IP Management addresses from DB: {exc}")
            return ["0.0.0.0", "0.0.0.0"]

    return ip_addresses
