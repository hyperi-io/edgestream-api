"""
Project:   edgestream-api
File:      edgestream/crud/network/vpn_client.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

import os
import re
import base64
import hashlib
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.network.vpn_client import VPNConfig
from edgestream.schemas.network.vpn_client import (
    VPNType,
    VPNUpload,
    VPNUpdate,
    VPNUpdateSettings
)

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]$")

def _validate_name(name: str) -> str:
    if not name or not _NAME_RE.fullmatch(name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid name. Use letters, numbers, and hyphens (3-63 chars).",
        )
    return name

def _safe_filename(name: str) -> str:
    return os.path.basename(name or "")

def _normalize_openvpn_bytes(profile_name: str, contents: bytes, has_auth: bool = False) -> bytes:
    try:
        txt = contents.decode("utf-8")
    except Exception:
        return contents

    dev_line = f"dev tun-es-{profile_name}"
    dev_re = re.compile(r"(?m)^\s*dev\s+\S+\s*$")
    devtype_re = re.compile(r"(?m)^\s*dev-type\s+tun\s*$")
    auth_re = re.compile(r"(?m)^\s*auth-user-pass.*$")

    if dev_re.search(txt):
        txt = dev_re.sub(dev_line, txt)
    else:
        txt = dev_line + "\n" + txt

    if not devtype_re.search(txt):
        txt = txt.rstrip() + "\ndev-type tun\n"

    # Enforce standard creds file path if auth is present
    cred_file = f"/etc/openvpn/client/{profile_name}.credentials"
    if has_auth:
        if auth_re.search(txt):
            txt = auth_re.sub(f"auth-user-pass {cred_file}", txt)
        else:
            txt = txt.rstrip() + f"\nauth-user-pass {cred_file}\n"

    return txt.encode("utf-8")

def _normalize_wireguard_bytes(contents: bytes) -> bytes:
    if not contents:
        return contents

    m = re.search(rb"(?m)^\[Interface\]\s*$", contents)
    data = contents[m.start():] if m else contents

    data = re.sub(rb"(?m)^\s*dev\s+.*\r?\n?", b"", data)
    data = re.sub(rb"(?m)^\s*dev-type\s+.*\r?\n?", b"", data)

    return data.rstrip() + b"\n"

def _next_vpn_table_id(db: Session, start: int = 100) -> int:
    used = set(db.execute(
        select(VPNConfig.table_id).where(VPNConfig.table_id.is_not(None))
    ).scalars().all())

    n = start
    while n in used:
        n += 1
    return n


class CRUDVPNClient(CRUDBase[VPNConfig, VPNUpload, VPNUpdate]):

    def export(self, db: Session) -> List[Dict[str, Any]]:
        rows = db.execute(select(VPNConfig).order_by(VPNConfig.name.asc())).scalars().all()
        out = []
        for r in rows:
            try:
                payload = r.data.decode("utf-8")
                encoding = "text"
            except Exception:
                payload = base64.b64encode(r.data).decode("ascii")
                encoding = "base64"

            out.append({
                "name": r.name,
                "vpn_type": r.vpn_type.value if hasattr(r.vpn_type, "value") else str(r.vpn_type),
                "filename": r.filename,
                "autoconnect": r.autoconnect,
                "mtu_mode": r.mtu_mode.value if hasattr(r.mtu_mode, "value") else str(r.mtu_mode),
                "mtu_value": r.mtu_value,
                "mss_mode": r.mss_mode.value if hasattr(r.mss_mode, "value") else str(r.mss_mode),
                "mss_value": r.mss_value,
                "kill_switch": r.kill_switch,
                "table_id": r.table_id,
                "routes": r.routes or [],
                "auth_username": r.auth_username,
                "auth_password": r.auth_password,
                "data": payload,
                "data_encoding": encoding,
                "filesize": r.filesize,
                "data_sha256": r.data_sha256,
            })
        return out

    def upload(self, db: Session, obj_in: VPNUpload, contents: bytes) -> VPNConfig:
        try:
            data = obj_in.model_dump()

            data.pop("created", None)
            data.pop("modified", None)

            data["name"] = _validate_name(data.get("name", ""))
            data["filename"] = _safe_filename(data.get("filename", "")) or "config"

            adv = data.pop("advanced", None) or {}
            for key in ["mtu_mode", "mtu_value", "mss_mode", "mss_value"]:
                if key in adv:
                    data[key] = adv[key]

            if data.get("table_id") in (None, "", 0):
                data["table_id"] = _next_vpn_table_id(db)

            vtype = data.get("vpn_type")
            vtype_enum = vtype if isinstance(vtype, VPNType) else VPNType(str(vtype))

            has_auth = bool(data.get("auth_username") and data.get("auth_password"))

            final_contents = contents or b""
            if vtype_enum == VPNType.openvpn and final_contents:
                final_contents = _normalize_openvpn_bytes(data["name"], final_contents, has_auth=has_auth)
            elif vtype_enum == VPNType.wireguard and final_contents:
                final_contents = _normalize_wireguard_bytes(final_contents)

            data["data"] = final_contents
            data["filesize"] = len(final_contents)
            data["data_sha256"] = hashlib.sha256(final_contents).hexdigest() if final_contents else None

            db_obj = VPNConfig(**data)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VPN profile name or Table ID already exists.")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"VPN Upload Error: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error during VPN upload.")

    def get_by_name(self, db: Session, *, name: str) -> Optional[VPNConfig]:
        name = _validate_name(name)
        return db.execute(
            select(VPNConfig).where(VPNConfig.name == name)
        ).scalar_one_or_none()

    def update_profile(
            self,
            db: Session,
            *,
            db_obj: VPNConfig,
            obj_in: VPNUpdateSettings
    ) -> VPNConfig:
        update_data = obj_in.model_dump(exclude_unset=True)

        update_data.pop("name", None)
        update_data.pop("id", None)

        file_content = update_data.pop("file_content", None)
        filename = update_data.pop("filename", None)

        if file_content is not None:
            raw_bytes = file_content.encode("utf-8")
            if db_obj.vpn_type == VPNType.openvpn:
                raw_bytes = _normalize_openvpn_bytes(db_obj.name, raw_bytes)
            elif db_obj.vpn_type == VPNType.wireguard:
                raw_bytes = _normalize_wireguard_bytes(raw_bytes)

            db_obj.data = raw_bytes
            db_obj.filesize = len(raw_bytes)
            db_obj.data_sha256 = hashlib.sha256(raw_bytes).hexdigest()
            if filename:
                db_obj.filename = _safe_filename(filename)

        if "advanced" in update_data and update_data["advanced"]:
            adv = update_data.pop("advanced")
            for key in ["mtu_mode", "mtu_value", "mss_mode", "mss_value"]:
                if key in adv:
                    update_data[key] = adv[key]

        if "routes" in update_data and update_data["routes"] is not None:
            update_data["routes"] = [
                r if isinstance(r, dict) else r.model_dump()
                for r in update_data["routes"]
            ]

        try:
            return super().update(db, db_obj=db_obj, obj_in=update_data)
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Constraint violation during VPN profile update."
            )
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"VPN Update Error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error during VPN profile update."
            )

    def replace_config_bytes(self, db: Session, *, db_obj: VPNConfig, filename: str, contents: bytes) -> VPNConfig:
        try:
            db_obj.filename = _safe_filename(filename) or db_obj.filename

            final_contents = contents or b""
            if db_obj.vpn_type == VPNType.openvpn:
                final_contents = _normalize_openvpn_bytes(db_obj.name, final_contents)
            elif db_obj.vpn_type == VPNType.wireguard:
                final_contents = _normalize_wireguard_bytes(final_contents)

            db_obj.data = final_contents
            db_obj.filesize = len(final_contents)
            db_obj.data_sha256 = hashlib.sha256(final_contents).hexdigest()

            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to replace config bytes.")

vpnclient = CRUDVPNClient(VPNConfig)
