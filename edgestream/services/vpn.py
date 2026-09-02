"""
Project:   edgestream-api
File:      edgestream/services/vpn.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
from typing import Optional, Tuple, Dict, Any

import pexpect
import psutil

from edgestream.core.config import Logger


def _norm_type(vpn_type: Any) -> str:
    """Standardizes Enum or String types to lower-case string."""
    return vpn_type.value.lower() if hasattr(vpn_type, "value") else str(vpn_type).lower()


# ----------------------------
# Systemd & Path Conventions
# ----------------------------

def vpn_unit(name: str, vpn_type: str) -> str:
    """Returns the standardized systemd unit name."""
    vtype = _norm_type(vpn_type)
    if vtype == "wireguard":
        return f"wg-quick@{name}.service"
    return f"openvpn-client@{name}.service"


def vpn_log_path(name: str, vpn_type: str) -> str:
    """Determines the log file location for the VPN process."""
    base = "/var/log/edgestream-api"
    vtype = _norm_type(vpn_type)
    prefix = "wireguard" if vtype == "wireguard" else "openvpn"
    return os.path.join(base, f"{prefix}-{name}.log")


# ----------------------------
# Service Monitoring
# ----------------------------

def service_state(name: str, vpn_type: str) -> Tuple[bool, str]:
    """Queries systemd for the ActiveState of the VPN unit."""
    unit = vpn_unit(name, vpn_type)
    try:
        status = subprocess.check_output(
            ["systemctl", "show", "-p", "ActiveState", "--value", unit],
        ).decode(sys.stdout.encoding or "utf-8").strip()

        if status == "inactive":
            status = "stopped"
        # Capitalize first letter (e.g., Active, Inactive, Failed)
        return True, status.capitalize()
    except Exception as error:
        Logger.logger.error(f"Failed to query systemd for {unit}: {error}")
        return False, "Unknown"


def service_uptime_seconds(name: str, vpn_type: str) -> Optional[int]:
    """
    Calculates uptime by comparing system monotonic time
    against the unit's ActiveEnterTimestampMonotonic.
    """
    unit = vpn_unit(name, vpn_type)
    try:
        # Get start time in microseconds
        r = subprocess.run(
            ["systemctl", "show", unit, "-p", "ActiveEnterTimestampMonotonic", "--value"],
            capture_output=True, text=True
        )
        if r.returncode != 0 or not r.stdout.strip() or r.stdout.strip() == "0":
            return None
        active_usec = int(r.stdout.strip())

        # Get current system uptime
        with open("/proc/uptime", "r") as f:
            up_now = float(f.read().split()[0])

        now_usec = int(up_now * 1_000_000)
        if now_usec <= active_usec:
            return None

        return int((now_usec - active_usec) / 1_000_000)
    except Exception:
        return None


# ----------------------------
# Network Interface Logic
# ----------------------------

def get_vpn_interface(name: str, vpn_type: str) -> Dict[str, Any]:
    """
    Resolves the network device and IP assigned to a VPN profile.
    Priority: WireGuard (iface=name) > OpenVPN (iface=tun-es-name) > Any tun/tap.
    """
    vtype = _norm_type(vpn_type)

    if vtype == "wireguard":
        ip, mask = _iface_ipv4_addr(name)
        return {"device": name, "ip_address": ip, "netmask": mask}

    # Custom Hub-prefixed tunnel for OpenVPN
    preferred = f"tun-es-{name}"
    if os.path.exists(f"/sys/class/net/{preferred}"):
        ip, mask = _iface_ipv4_addr(preferred)
        return {"device": preferred, "ip_address": ip, "netmask": mask}

    for device, addrs in psutil.net_if_addrs().items():
        if device.startswith(("tun", "tap")):
            for snic in addrs:
                if snic.family == socket.AF_INET:
                    return {
                        "device": device,
                        "ip_address": snic.address,
                        "netmask": snic.netmask,
                    }
    return {}


def _iface_ipv4_addr(iface: str) -> Tuple[Optional[str], Optional[str]]:
    """Helper to fetch IPv4 info for a specific interface."""
    try:
        addrs = psutil.net_if_addrs().get(iface) or []
        for snic in addrs:
            if snic.family == socket.AF_INET:
                return snic.address, snic.netmask
        return None, None
    except Exception:
        return None, None


# ----------------------------
# Verification & Validation
# ----------------------------

def verify_vpn(name: str, vpn_type: str, config_path: str) -> Tuple[bool, str]:
    """Entry point for dry-running a VPN configuration before activation."""
    if not os.path.isfile(config_path):
        return False, "Configuration file not found."

    vtype = _norm_type(vpn_type)
    return _verify_wireguard(config_path) if vtype == "wireguard" else _verify_openvpn(config_path)


def _verify_openvpn(file_path: str) -> Tuple[bool, str]:
    """Tests OpenVPN config by attempting a short-lived connection."""
    server_address, server_port = None, 1194  # Default port

    with open(file_path, "r") as f:
        for line in f:
            if line.strip().startswith("remote "):
                tokens = line.split()
                if len(tokens) >= 2:
                    server_address = tokens[1]
                    if len(tokens) > 2:
                        server_port = tokens[2]
                break

    if not server_address:
        return False, "Malformed OVPN: 'remote' directive missing."

    try:
        socket.gethostbyname(server_address)
    except socket.error as e:
        return False, f"DNS Resolution failed for {server_address}: {e}"

    try:
        cmd = f"openvpn --config {file_path} --connect-timeout 5 --verb 3"
        child = pexpect.spawn(cmd, timeout=15)

        # Look for successful handshakes or fatal errors
        idx = child.expect([
            "Initialization Sequence Completed",
            "AUTH_FAILED",
            "Cannot load CA certificate",
            "TLS Error: TLS key negotiation failed",
            pexpect.EOF,
            pexpect.TIMEOUT
        ])

        child.before.decode(errors='ignore') if child.before else ""
        child.close()

        if idx == 0:
            return True, f"Connection to {server_address}:{server_port} verified."
        elif idx == 1:
            return False, "Authentication Failed (check credentials)."
        elif idx == 3:
            return False, "TLS Negotiation Failed (check firewall/certs)."

        return False, f"Verification failed. Server {server_address} might be unreachable."

    except Exception as e:
        return False, f"Verification process error: {e}"


def _verify_wireguard(file_path: str) -> Tuple[bool, str]:
    """Validates WireGuard configuration syntax and endpoint resolution."""
    endpoint_re = re.compile(r"^\s*Endpoint\s*=\s*(.+)\s*$", re.IGNORECASE)
    endpoint = None

    with open(file_path, "r") as f:
        for line in f:
            if m := endpoint_re.match(line):
                endpoint = m.group(1).strip()
                break

    if not endpoint:
        return False, "WireGuard config missing 'Endpoint'."

    # Parse Host from Host:Port or [IPv6]:Port
    host = endpoint.rsplit(":", 1)[0].strip("[]")
    try:
        socket.gethostbyname(host)
        return True, f"WireGuard endpoint {endpoint} is valid."
    except socket.error as e:
        return False, f"Could not resolve WireGuard endpoint {host}: {e}"


# ----------------------------
# Statistics (Live Data)
# ----------------------------

def wireguard_stats(iface: str) -> Dict[str, Any]:
    """Parses 'wg show dump' to get real-time handshake and traffic data."""
    try:
        r = subprocess.run(["wg", "show", iface, "dump"], capture_output=True, text=True)
        if r.returncode != 0: return {}

        lines = r.stdout.splitlines()
        if len(lines) < 2: return {}

        peer = lines[1].split("\t")
        return {
            "server": peer[2] if len(peer) > 2 else None,
            "latest_handshake": int(peer[4]) if len(peer) > 4 and peer[4].isdigit() else 0,
            "rx_bytes": int(peer[5]) if len(peer) > 5 and peer[5].isdigit() else 0,
            "tx_bytes": int(peer[6]) if len(peer) > 6 and peer[6].isdigit() else 0,
        }
    except Exception:
        return {}
