from __future__ import annotations

import json
import re
import socket
import struct
import fcntl
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Request,
    status
)
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.db.session import SessionLocal
from edgestream.models.system.user import User
from edgestream.schemas.base import TaskScheduledResponse
from edgestream.schemas.value.vpn_response import SuccessfulVPNCommandRun
from edgestream.schemas.network.vpn_client import (
    VPNStatusOut,
    VPNProfileOut,
    VPNCreateRequest,
    VPNUpload,
    VPNRunRequest,
    VPNDeleteRequest,
    VPNUpdateSettings
)
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.services.background.audit_tasks import enqueue_audit
from edgestream.services.vpn import service_state

router = APIRouter()

# Path to wireguard status daemon output
WG_STATUS_FILE = Path("/run/edgestream/wg-status.json")

VPN_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]$")


# -----------------------------------------------------------------------------
# Security & Validation Helpers
# -----------------------------------------------------------------------------

def validate_vpn_name(name: str):
    if not VPN_NAME_RE.match(name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid VPN name. Use letters, numbers, and hyphens (3-63 chars)."
        )


def _unit_name(name: str, vtype: str) -> str:
    """Standardizes systemd unit naming conventions."""
    vtype_lower = vtype.lower()
    if vtype_lower == "wireguard":
        return f"wg-quick@{name}.service"
    elif vtype_lower == "openvpn":
        return f"openvpn-client@{name}.service"
    return f"{vtype}@{name}.service"


def _audit(
        background: BackgroundTasks,
        request: Request,
        *,
        event_type: str,
        result: str,
        current_user: User,
        details: Dict[str, Any] | None = None,
        status_code: int | None = None,
):
    enqueue_audit(
        background,
        SessionLocal,
        request,
        event_type=event_type,
        result=result,
        actor_id=str(current_user.id),
        actor_type="user",
        subject_type="vpn",
        details=details or {},
        status_code=status_code,
    )


# -----------------------------------------------------------------------------
# Real-time Status Monitoring
# -----------------------------------------------------------------------------

def _sysctl_is_enabled(unit: str) -> bool:
    """Checks if the VPN is set to start on boot."""
    try:
        r = subprocess.run(
            ["systemctl", "is-enabled", unit],
            capture_output=True, text=True, timeout=2
        )
        return r.returncode == 0 and r.stdout.strip() == "enabled"
    except Exception:
        return False


def _iface_name_for_vpn(name: str, vtype: str) -> str:
    """Returns the actual network interface name created by the driver/systemd."""
    vtype_lower = vtype.lower()
    if vtype_lower == "openvpn":
        return f"tun-es-{name}"
    return name  # WireGuard uses the interface name directly (e.g., 'Myvpn')


def _get_iface_ip(iface_name: str) -> Optional[str]:
    """
    Retrieves the primary IPv4 address assigned to a network interface.
    """
    SIOCGIFADDR = 0x8915
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Pack interface name into 24-byte struct for ioctl
        iface_pack = struct.pack('256s', iface_name[:15].encode('utf-8'))
        res = fcntl.ioctl(s.fileno(), SIOCGIFADDR, iface_pack)
        ip = socket.inet_ntoa(res[20:24])
        return ip
    except Exception:
        return None


def _iface_counters(iface: str) -> Tuple[Optional[int], Optional[int]]:
    """Reads interface statistics directly from sysfs (/sys/class/net/<iface>/statistics)."""
    base_path = Path(f"/sys/class/net/{iface}/statistics")
    try:
        if base_path.exists():
            rx = int((base_path / "rx_bytes").read_text().strip())
            tx = int((base_path / "tx_bytes").read_text().strip())
            return rx, tx
    except Exception as e:
        Logger.logger.debug(f"Sysfs counter read failed for {iface}: {e}")
    return None, None


def _get_service_uptime(unit: str) -> Optional[int]:
    """Calculates active service uptime in seconds via systemctl."""
    try:
        r = subprocess.run(
            ["sudo", "-n", "systemctl", "show", unit, "--property=ActiveEnterTimestampMonotonic"],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0 and "=" in r.stdout:
            val = int(r.stdout.strip().split("=")[1])
            if val > 0:
                with open("/proc/uptime", "r") as f:
                    uptime_sec = float(f.readline().split()[0])
                return max(0, int(uptime_sec - (val / 1_000_000)))
    except Exception:
        pass
    return None


def _get_openvpn_endpoint_from_journal(vpn_name: str) -> Optional[str]:
    """Extracts active remote server endpoint from openvpn journal output using sudo."""
    try:
        unit = f"openvpn-client@{vpn_name}.service"
        r = subprocess.run(
            ["sudo", "-n", "journalctl", "-u", unit, "-n", "30", "--no-pager"],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0:
            m = re.search(r"(?:Initiated with|Link Remote:)\s*(?:\[AF_INET\])?([0-9\.]+:[0-9]+)", r.stdout)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def _get_openvpn_stats(vpn_name: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Parses OpenVPN status file at /run/openvpn-client/status-<name>.log
    Returns: (rx_bytes, tx_bytes, endpoint_address)
    """
    status_file = Path(f"/run/openvpn-client/status-{vpn_name}.log")
    rx, tx = None, None

    if status_file.exists():
        content = ""
        try:
            content = status_file.read_text()
        except PermissionError:
            # Fallback to non-interactive sudo cat if edgestream user is denied read access
            try:
                r = subprocess.run(
                    ["sudo", "-n", "cat", str(status_file)],
                    capture_output=True, text=True, timeout=2
                )
                if r.returncode == 0:
                    content = r.stdout
            except Exception as se:
                Logger.logger.warning(f"Sudo read failed for {status_file}: {se}")

        if content:
            try:
                for line in content.splitlines():
                    line = line.strip()
                    if "," not in line:
                        continue

                    parts = [p.strip() for p in line.split(",", 1)]
                    if len(parts) < 2:
                        continue

                    key, val = parts[0], parts[1]

                    if key == "TUN/TAP write bytes":
                        rx = int(val)
                    elif key == "TUN/TAP read bytes":
                        tx = int(val)
                    elif key == "TCP/UDP read bytes" and rx is None:
                        rx = int(val)
                    elif key == "TCP/UDP write bytes" and tx is None:
                        tx = int(val)
            except Exception as e:
                Logger.logger.warning(f"Error parsing OpenVPN status content for {vpn_name}: {e}")

    endpoint = _get_openvpn_endpoint_from_journal(vpn_name)

    return rx, tx, endpoint


def _get_wg_stats(iface_name: str) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[str]]:
    """
    Reads interface stats from /run/edgestream/wg-status.json.
    Returns: (rx_bytes, tx_bytes, uptime_seconds)
    """
    if not WG_STATUS_FILE.exists():
        return None, None, None

    try:
        data = json.loads(WG_STATUS_FILE.read_text())
        ifaces = data.get("interfaces", {})

        iface_data = ifaces.get(iface_name)
        if not iface_data:
            return None, None, None

        peers = iface_data.get("peers", [])
        if not peers:
            return 0, 0, None

        rx_sum = sum(p.get("rx_bytes") or 0 for p in peers)
        tx_sum = sum(p.get("tx_bytes") or 0 for p in peers)

        uptimes = [p.get("uptime_seconds") for p in peers if p.get("uptime_seconds") is not None]
        min_uptime = min(uptimes) if uptimes else None

        endpoints = [p.get("endpoint") for p in peers if p.get("endpoint")]
        endpoint_address = ", ".join(endpoints) if endpoints else None

        return rx_sum, tx_sum, min_uptime, endpoint_address
    except Exception as e:
        Logger.logger.error(f"Error parsing WireGuard status cache: {e}")
        return None, None, None


def _status_for_vpn(vpn) -> VPNStatusOut:
    """Aggregates system state into a unified status schema."""
    vtype_str = vpn.vpn_type.value if hasattr(vpn.vpn_type, "value") else str(vpn.vpn_type)
    unit = _unit_name(vpn.name, vtype_str)
    iface_name = _iface_name_for_vpn(vpn.name, vtype_str)

    try:
        _, desc = service_state(vpn.name, vpn.vpn_type)
    except Exception as se:
        Logger.logger.warning(f"Failed querying systemd service state for {vpn.name}: {se}")
        return VPNStatusOut(state="connecting", last_error=None)

    desc_s = (str(desc or "")).strip().lower()

    state_map = {
        "active": "active",
        "running": "active",
        "activating": "connecting",
        "starting": "connecting",
        "reloading": "connecting",
        "auto-restart": "connecting",
        "deactivating": "connecting",
        "failed": "failed",
        "error": "failed"
    }

    norm = "inactive"
    for key, val in state_map.items():
        if key in desc_s:
            norm = val
            break

    rx, tx, uptime, endpoint = None, None, None, None
    local_vpn_ip = None

    if norm == "active":
        try:
            uptime = _get_service_uptime(unit)
        except Exception as e:
            Logger.logger.debug(f"Uptime lookup skipped for {vpn.name}: {e}")

        if vtype_str.lower() == "wireguard":
            try:
                rx, tx, wg_uptime, endpoint = _get_wg_stats(vpn.name)
                uptime = wg_uptime or uptime
            except Exception as e:
                Logger.logger.warning(f"WG stats lookup failed for {vpn.name}: {e}")
        elif vtype_str.lower() == "openvpn":
            try:
                ovpn_rx, ovpn_tx, endpoint = _get_openvpn_stats(vpn.name)
                rx, tx = ovpn_rx, ovpn_tx
            except Exception as e:
                Logger.logger.warning(f"OpenVPN stats lookup failed for {vpn.name}: {e}")

        if rx is None or tx is None:
            try:
                sys_rx, sys_tx = _iface_counters(iface_name)
                rx = rx if rx is not None else sys_rx
                tx = tx if tx is not None else sys_tx
            except Exception:
                pass

        try:
            local_vpn_ip = _get_iface_ip(iface_name)
        except Exception:
            pass

    return VPNStatusOut(
        state=norm,
        enabled=_sysctl_is_enabled(unit),
        uptime_seconds=uptime,
        rx_bytes=rx,
        tx_bytes=tx,
        tunnel_address=local_vpn_ip or ("pending..." if norm in ("active", "connecting") else None),
        endpoint_address=endpoint,
        last_error=desc_s if norm == "failed" else None
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("", response_model=List[VPNProfileOut])
def list_vpn_profiles(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Retrieve all configured VPN profiles and their metadata."""
    rows = crud.vpnclient.get_multi(db, limit=100)
    return [
        VPNProfileOut(
            id=r.id,
            name=r.name,
            vpn_type=r.vpn_type,
            autoconnect=r.autoconnect,
            filename=r.filename,
            created=r.created_at,
            modified=r.updated_at,
            filesize=r.filesize,
            kill_switch=getattr(r, "kill_switch", False),
            routes=getattr(r, "routes", []) or [],
            auth_username=r.auth_username,
            advanced={
                "mtu_mode": r.mtu_mode,
                "mtu_value": r.mtu_value,
                "mss_mode": r.mss_mode,
                "mss_value": r.mss_value,
            },
        ) for r in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TaskScheduledResponse)
def create_vpn_profile(
        request: Request,
        background_tasks: BackgroundTasks,
        payload: VPNCreateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """Register a new VPN profile with standard JSON body."""
    validate_vpn_name(payload.name)

    if crud.vpnclient.get_by_name(db, name=payload.name):
        raise HTTPException(status_code=409, detail="VPN profile name already exists")

    raw_bytes = payload.file_content.encode("utf-8") if payload.file_content else b""

    vpn_upload = VPNUpload(
        name=payload.name,
        vpn_type=payload.vpn_type,
        filename=payload.filename or "config.conf",
        filesize=len(raw_bytes),
        autoconnect=payload.autoconnect,
        kill_switch=payload.kill_switch,
        routes=[r.model_dump() for r in (payload.routes or [])],
        advanced=payload.advanced,
    )

    vpn_upload_dict = vpn_upload.model_dump()
    vpn_upload_dict["auth_username"] = payload.auth_username
    vpn_upload_dict["auth_password"] = payload.auth_password

    try:
        vpn = crud.vpnclient.upload(db=db, obj_in=vpn_upload, contents=raw_bytes)
        if payload.auth_username or payload.auth_password:
            vpn.auth_username = payload.auth_username
            vpn.auth_password = payload.auth_password
            db.add(vpn)
            db.commit()
            db.refresh(vpn)

        _audit(background_tasks, request, event_type="vpn.create", result="success",
               current_user=current_user, details={"name": vpn.name})

        return schedule_task(db, background_tasks, f"Provision VPN {vpn.name}",
                             run_playbook=True, playbook="01_vpn_settings.yml")
    except Exception as e:
        Logger.logger.error(f"VPN creation crash: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Internal server error provisioning VPN.")


@router.put("", response_model=TaskScheduledResponse)
def update_vpn_profile(
        request: Request,
        background_tasks: BackgroundTasks,
        payload: VPNUpdateSettings,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """Update settings for an existing VPN profile (name cannot be changed)."""
    vpn = None
    if payload.id is not None:
        vpn = crud.vpnclient.get(db, id=payload.id)
    elif payload.name:
        validate_vpn_name(payload.name)
        vpn = crud.vpnclient.get_by_name(db, name=payload.name)

    if not vpn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="VPN profile not found."
        )

    try:
        updated_vpn = crud.vpnclient.update_profile(db=db, db_obj=vpn, obj_in=payload)

        _audit(
            background_tasks,
            request,
            event_type="vpn.update",
            result="success",
            current_user=current_user,
            details={"name": updated_vpn.name}
        )

        return schedule_task(
            db,
            background_tasks,
            f"Update VPN settings for {updated_vpn.name}",
            run_playbook=True,
            playbook="01_vpn_settings.yml"
        )
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"VPN update crash: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error updating VPN profile."
        )


@router.post("/run", response_model=SuccessfulVPNCommandRun)
def execute_vpn_command(
        payload: VPNRunRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Start, stop, or restart a VPN service."""
    from edgestream.services.vpn_helpers import run_vpn_command
    validate_vpn_name(payload.name)

    vpn = crud.vpnclient.get_by_name(db, name=payload.name)
    if not vpn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VPN profile not found")

    vtype = vpn.vpn_type.value if hasattr(vpn.vpn_type, "value") else str(vpn.vpn_type)

    try:
        run_vpn_command(payload.action, name=vpn.name, vpn_type=vtype)
        return SuccessfulVPNCommandRun(detail=f"Issued {payload.action} to {vpn.name}")
    except Exception as e:
        Logger.logger.error(f"VPN control failure: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to communicate with systemd.")


@router.delete("", status_code=status.HTTP_200_OK, response_model=TaskScheduledResponse)
def delete_vpn_profile(
        request: Request,
        background_tasks: BackgroundTasks,
        payload: VPNDeleteRequest = Body(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Delete a VPN profile and clean up associated system services."""
    vpn = None
    if payload.id is not None:
        vpn = crud.vpnclient.get(db, id=payload.id)
    elif payload.name:
        validate_vpn_name(payload.name)
        vpn = crud.vpnclient.get_by_name(db, name=payload.name)

    if not vpn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VPN profile not found")

    crud.vpnclient.remove(db=db, id=vpn.id)
    _audit(background_tasks, request, event_type="vpn.delete", result="success",
           current_user=current_user, details={"name": vpn.name})

    return schedule_task(db, background_tasks, f"Deprovision VPN {vpn.name}",
                         run_playbook=True, playbook="01_vpn_settings.yml")


@router.get("/status")
def get_vpn_status_map(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """Returns a real-time status mapping for all configured VPNs."""
    vpns = crud.vpnclient.get_all(db)
    return {str(v.id): _status_for_vpn(v).model_dump() for v in vpns}
