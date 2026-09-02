"""
Project:   edgestream-api
File:      edgestream/services/vpn_helpers.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

import subprocess
from typing import Literal, Any

from fastapi import HTTPException, status
from edgestream.core.config import settings

def _norm_type(vpn_type: Any) -> str:
    """Standardizes Enum or String types to a lower-case string."""
    val = vpn_type.value if hasattr(vpn_type, "value") else str(vpn_type)
    return val.lower()

def run_vpn_command(
    action: Literal["start", "stop", "restart"],
    *,
    name: str,
    vpn_type: Any
) -> None:
    """
    Executes a lifecycle command for a specific VPN tunnel.
    Dispatches to the privileged 'edgestream-vpnctl' helper.
    """
    if action not in ("start", "stop", "restart"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid action '{action}'. Use start, stop, or restart."
        )

    vtype = _norm_type(vpn_type)
    if vtype not in ("openvpn", "wireguard"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported VPN type: {vtype}"
        )

    try:
        vpnctl_bin = getattr(
            settings,
            "EDGESTREAM_VPNCTL",
            "/opt/edgestream-api/bin/edgestream-vpnctl"
        )

        subprocess.run(
            [vpnctl_bin, action, vtype, name],
            check=True,
            capture_output=True,
            text=True,
            timeout=15  # Prevent API hang if systemd blocks
        )
    except subprocess.CalledProcessError as e:
        # Capture specific stderr from vpnctl for better frontend debugging
        error_msg = (e.stderr or e.stdout or str(e)).strip()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"VPN Control Error: {error_msg}"
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The VPN control command timed out."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected failure in VPN helper: {str(e)}"
        )
