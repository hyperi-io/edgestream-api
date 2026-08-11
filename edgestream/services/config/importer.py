from __future__ import annotations

import sqlite3
import secrets
import string
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.schemas.system.advanced_setting import AdvancedSettingCreate
from edgestream.schemas.system.certificate_store import CertificateTypes
from edgestream.schemas.event.destination import DestinationCreate
from edgestream.schemas.event.destination_parameter import DestinationParameterCreate
from edgestream.schemas.event.source import SourceCreate
from edgestream.schemas.event.source_parameter import SourceParameterCreate
from edgestream.schemas.event.transform import TransformCreate
from edgestream.schemas.network.dns_client import DNSCreate
from edgestream.schemas.network.dns_forwarder import DNSForwarderCreate
from edgestream.schemas.network.ntp_client import NTPCreate
from edgestream.schemas.network.static_host import StaticHostCreate
from edgestream.schemas.network.static_route import StaticRouteCreate
from edgestream.schemas.network.ip_management import IPMgmtCreate
from edgestream.schemas.system.system import SystemUpdate
from edgestream.schemas.network.vpn_client import VPNUpload
from edgestream.schemas.system.log_viewer import CreateLogViewer
from edgestream.schemas.system.user import UserCreate


def import_settings(parsed_yaml: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """
    Main entry point for importing a full system configuration.
    Wipes existing state for specific sections to ensure a clean restore.
    """
    version = parsed_yaml.get("version")
    if version != 1:
        Logger.logger.error(f"Import rejected: Version mismatch. Expected 1, got {version}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incompatible configuration version. Expected '1', found '{version}'."
        )

    response: Dict[str, Any] = {"version": version}

    # 1. Process Backup & Credentials
    if backup := parsed_yaml.get("backup"):
        response["backup"] = process_backup(db, backup)

    # 2. Process System Identity
    response["system"] = process_system(db, parsed_yaml.get("system", {}))

    # 3. Process Certificates
    if certificates := parsed_yaml.get("certificates"):
        process_certificates(db, certificates)

    # 4. Process Pipeline Components
    process_sources(db, parsed_yaml.get("sources", []))
    process_transforms(db, parsed_yaml.get("transforms", []))
    process_destinations(db, parsed_yaml.get("destinations", []))

    # 5. Process Networking
    if networks := parsed_yaml.get("networks", {}):
        response["networks"] = process_networks_strict(db, networks)

    # 6. Process VPN, Advanced, Logs, and Users
    process_vpn(db, parsed_yaml.get("vpn", []))
    process_advanced(db, parsed_yaml.get("advanced", {}))
    process_logs(db, parsed_yaml.get("logs", []))

    # NEW: Process User accounts
    process_users(db, parsed_yaml.get("users", []))

    return {"updated_configs": response}


# ----------------- Processors -----------------

def process_backup(db: Session, backup_data: Dict[str, Any]) -> Dict[str, Any]:
    """Syncs backup/cloud credentials across all providers."""
    for provider_name, data in backup_data.items():
        crud.backup.upsert_by_provider(db=db, provider=provider_name, obj_in=data)
    return {"status": "synchronized"}


def process_system(db: Session, data: Dict[str, Any]) -> str:
    """Updates system identity and localization."""
    system_update = SystemUpdate(**data)
    current = crud.system.get_system(db)
    if current:
        crud.system.update(db=db, db_obj=current, obj_in=system_update)
    else:
        crud.system.create(db=db, obj_in=system_update)
    return str(system_update.hostname)


def process_certificates(db: Session, certificates: Dict[str, Any]):
    """Wipes and restores the certificate store."""
    crud.certificate.delete_all(db)
    for cert_type in certificates.keys():
        for cert in certificates.get(cert_type, []):
            if cert.get("data_b64"):
                import base64
                raw_data = base64.b64decode(cert["data_b64"])
            else:
                raw_data = cert["data"].encode()

            crud.certificate.create(db=db, obj_in={
                **cert,
                "data": raw_data,
                "filesize": len(raw_data)
            })


def process_sources(db: Session, sources: List[Dict[str, Any]]):
    crud.source.delete_all(db=db)
    for s in sources:
        params = [SourceParameterCreate(key=k, value=v) for k, v in (s.get("settings") or {}).items()]
        crud.source.create(db=db, obj_in=SourceCreate(**{**s, "settings": params}))


def process_destinations(db: Session, destinations: List[Dict[str, Any]]):
    crud.destination.delete_all(db=db)
    for d in destinations:
        # Pass parameters as dictionaries so Pydantic can validate them correctly
        params = [{"key": k, "value": v} for k, v in (d.get("settings") or {}).items()]
        crud.destination.create(db=db, obj_in=DestinationCreate(**{**d, "settings": params}))


def process_transforms(db: Session, transforms: List[Dict[str, Any]]):
    crud.transform.delete_all(db=db)
    for t in transforms:
        crud.transform.create(db=db, obj_in=TransformCreate(**t))


def process_networks_strict(db: Session, networks: Dict[str, Any]) -> Dict[str, Any]:
    """Wipes and restores network settings."""
    crud.ntp.delete_all(db)
    crud.dns.delete_all(db)
    crud.static_host.delete_all(db)
    crud.dns_forwarder.delete_all(db)
    crud.static_route.delete_all(db)
    crud.ip_mgmt.delete_all(db)

    results = {}
    mapping = {
        "ntp": (networks.get("ntp", []), NTPCreate, crud.ntp),
        "dns": (networks.get("dns", []), DNSCreate, crud.dns),
        "static_hosts": (networks.get("static_hosts", []), StaticHostCreate, crud.static_host),
        "dns_forwarders": (networks.get("dns_forwarders", []), DNSForwarderCreate, crud.dns_forwarder),
        "static_routes": (networks.get("static_routes", []), StaticRouteCreate, crud.static_route),
    }

    for key, (items, schema, manager) in mapping.items():
        results[key] = []
        for item in items:
            results[key].append(manager.create(db=db, obj_in=schema(**item)))

    if ip_mgmt_items := networks.get("ip_management", []):
        payload = {item["type"]: item for item in ip_mgmt_items if item.get("type") in ("mgmt", "event")}
        crud.ip_mgmt.create(db=db, obj_in=IPMgmtCreate(**payload))

    return results


def process_vpn(db: Session, vpn: List[Dict[str, Any]]):
    crud.vpnclient.delete_all(db)
    for v in vpn:
        import base64
        contents = base64.b64decode(v["data"]) if v.get("data_encoding") == "base64" else v["data"].encode()

        upload_schema = VPNUpload(
            name=v["name"],
            vpn_type=v["vpn_type"],
            filename=v["filename"],
            autoconnect=v.get("autoconnect", False),
            kill_switch=v.get("kill_switch", False),
            table_id=v.get("table_id")
        )
        crud.vpnclient.upload(db=db, obj_in=upload_schema, contents=contents)


def process_advanced(db: Session, advanced: Dict[str, Any]):
    crud.advanced_setting.delete_all(db=db)
    for k, v in advanced.items():
        crud.advanced_setting.create(db=db, obj_in=AdvancedSettingCreate(label=k, value=v))


def process_logs(db: Session, logs: List[Dict[str, Any]]):
    """Restores the log viewer whitelist."""
    crud.log_viewer.delete_all(db)
    for log in logs:
        crud.log_viewer.create(db=db, obj_in=CreateLogViewer(**log))


def process_users(db: Session, users: List[Dict[str, Any]]):
    """
    Syncs user accounts. Since passwords aren't exported, existing users
    are kept as is, and new users are created with a random secure password.
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    for u in users:
        email = u.get("email")
        if not email:
            continue

        existing = crud.user.get_by_email(db, email=email)
        if existing:
            # Sync roles/approval status for existing users
            crud.user.update(db, db_obj=existing, obj_in={
                "full_name": u.get("full_name"),
                "display_name": u.get("display_name"),
                "is_superuser": u.get("is_superuser"),
                "is_approved": u.get("is_approved")
            })
        else:
            # Create new user with a random "locked" password
            random_pw = ''.join(secrets.choice(alphabet) for _ in range(32))
            new_user_data = UserCreate(
                email=email,
                password=random_pw,
                full_name=u.get("full_name"),
                display_name=u.get("display_name"),
                is_superuser=u.get("is_superuser", False),
                is_approved=u.get("is_approved", False)
            )
            crud.user.create(db, obj_in=new_user_data)