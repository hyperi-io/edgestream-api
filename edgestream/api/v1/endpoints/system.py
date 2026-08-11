import re
import bleach
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger, settings
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.schemas.system.system import (
    SystemUptime,
    SystemPartitions,
    SystemIPAddresses,
    System,
    SystemHostname,
    SystemHostnameUpdate,
    SystemOrgID,
    SystemOrgIDUpdate,
    SystemSiteID,
    SystemSiteIDUpdate,
    SystemTimezone,
    SystemTimezoneUpdate,
    SystemComponents,
)
from edgestream.schemas.value.system_response import get_generic_error_responses
from edgestream.services.auth.auth import get_current_user
from edgestream.services.background.ansible_tasks import schedule_task
from edgestream.services.hostname import get_db_hostname
from edgestream.services.interfaces import get_ipv4_addresses, get_interfaces
from edgestream.services.network_summary import get_network_summary
from edgestream.services.partitions import get_partition_usage
from edgestream.services.uptime import get_uptime
from edgestream.services.user import get_last_users

router = APIRouter()

ZONEINFO = Path("/usr/share/zoneinfo")
ZONE1970 = ZONEINFO / "zone1970.tab"


# --- System Identity (Hostname, Org, Site) ---

@router.get("/hostname", response_model=SystemHostname)
def fetch_system_hostname(current_user: User = Depends(get_current_user)) -> SystemHostname:
    """Retrieve the current system hostname from the database."""
    return SystemHostname(hostname=get_db_hostname())


@router.put("/hostname", status_code=201)
def update_system_hostname(
        *,
        system_hostname_in: SystemHostnameUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """Update hostname and trigger system reconfiguration."""
    if not re.fullmatch(r'^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}$', system_hostname_in.hostname):
        raise HTTPException(
            status_code=400,
            detail="Invalid hostname. Use alphanumeric characters/hyphens (max 63). Cannot start with a hyphen.",
        )

    clean_hostname = bleach.clean(system_hostname_in.hostname)

    try:
        system = crud.system.system.get_or_create(db)
        crud.system.system.update(db=db, db_obj=system, obj_in={"hostname": clean_hostname})
        return schedule_task(db, background_tasks, f"Update hostname to {clean_hostname}", True)
    except Exception as e:
        Logger.logger.error(f"Hostname update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error updating hostname.")


@router.get("/org_id", response_model=SystemOrgID)
def fetch_org_id(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> SystemOrgID:
    system = crud.system.system.get_system(db)
    if not system:
        raise HTTPException(status_code=404, detail="System configuration not initialized.")
    return SystemOrgID(org_id=system.org_id)


@router.put("/org_id", status_code=201)
def update_system_org_id(
        *,
        system_org_id_in: SystemOrgIDUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    if not re.fullmatch(r'^[a-zA-Z0-9][a-zA-Z0-9-_\.]{0,64}$', system_org_id_in.org_id):
        raise HTTPException(status_code=400, detail="Invalid Org ID format.")

    system = crud.system.system.get_or_create(db)
    crud.system.system.update(db=db, db_obj=system, obj_in={"org_id": bleach.clean(system_org_id_in.org_id)})

    return schedule_task(db, background_tasks, "Update organization ID", True, playbook="01_vector_settings.yml")


@router.get("/site_id", response_model=SystemSiteID)
def fetch_site_id(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> SystemSiteID:
    system = crud.system.system.get_system(db)
    if not system:
        raise HTTPException(status_code=404, detail="System configuration not initialized.")
    return SystemSiteID(site_id=system.site_id)


@router.put("/site_id", status_code=201)
def update_system_site_id(
        *,
        system_site_id_in: SystemSiteIDUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    if not re.fullmatch(r'^[a-zA-Z0-9][a-zA-Z0-9-_\.]{0,64}$', system_site_id_in.site_id):
        raise HTTPException(status_code=400, detail="Invalid Site ID format.")

    system = crud.system.system.get_or_create(db)
    crud.system.system.update(db=db, db_obj=system, obj_in={"site_id": bleach.clean(system_site_id_in.site_id)})

    return schedule_task(db, background_tasks, "Update site ID", True, playbook="01_vector_settings.yml")


# --- System Status (Uptime, IP, Disk) ---

@router.get("/uptime", response_model=SystemUptime)
def fetch_system_uptime(current_user: User = Depends(get_current_user)) -> dict:
    return get_uptime()


@router.get("/ip_addresses", response_model=SystemIPAddresses)
def fetch_network_ip_addresses(current_user: User = Depends(get_current_user)) -> dict:
    return {"ip_addresses": get_ipv4_addresses()}


@router.get("/interfaces")
def fetch_interfaces(current_user: User = Depends(get_current_user)) -> list:
    try:
        return get_interfaces()
    except Exception as e:
        Logger.logger.error(f"Interface fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Unable to retrieve network interfaces.")


@router.get("/partitions", response_model=SystemPartitions)
def fetch_system_partitions(current_user: User = Depends(get_current_user)) -> dict:
    return {"partitions": get_partition_usage()}


# --- Dashboard / Summary ---

@router.get("/", responses={**get_generic_error_responses, 200: {"model": System}})
def fetch_system_information(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
) -> dict:
    """Aggregate endpoint for the primary dashboard view."""
    return {
        "version": f"EdgeStream Hub {settings.VERSION}",
        "hostname": get_db_hostname(),
        "uptime": get_uptime(),
        "interfaces": get_interfaces(),
        "ip_addresses": get_ipv4_addresses(),
        "partitions": get_partition_usage(),
        "users": get_last_users(),
        "components": {
            "sources_enabled": crud.source.count_enabled(db),
            "sinks_enabled": crud.destination.count_enabled(db),
        },
    }


@router.get("/components", response_model=SystemComponents)
def fetch_components(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> SystemComponents:
    """Count enabled pipeline components (Sources/Sinks)."""
    try:
        return SystemComponents(
            sources_enabled=crud.source.count_enabled(db),
            sinks_enabled=crud.destination.count_enabled(db)
        )
    except Exception as e:
        Logger.logger.warning(f"Component count failed: {e}")
        return SystemComponents(sources_enabled=0, sinks_enabled=0)


# --- Timezone Management ---

@router.get("/timezone", response_model=SystemTimezone)
def fetch_timezone(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> SystemTimezone:
    system = crud.system.system.get_system(db)
    return SystemTimezone(timezone=system.timezone if system else "UTC")


@router.put("/timezone", status_code=201)
def update_system_timezone(
        *,
        system_timezone_in: SystemTimezoneUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    if not re.fullmatch(r'^[a-zA-Z0-9\/\+_\- ]+$', system_timezone_in.timezone):
        raise HTTPException(status_code=400, detail="Invalid timezone format.")

    system = crud.system.system.get_or_create(db)
    crud.system.system.update(db=db, db_obj=system, obj_in={"timezone": bleach.clean(system_timezone_in.timezone)})

    return schedule_task(db, background_tasks, "Update system timezone", True)


@router.get("/timezones")
def get_available_timezones(current_user: User = Depends(get_current_user)):
    """Retrieve list of valid IANA timezones from the host filesystem."""
    zones = []
    if ZONE1970.exists():
        try:
            for line in ZONE1970.read_text().splitlines():
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    zones.append(parts[2].strip())
        except Exception as e:
            Logger.logger.error(f"Failed to parse zone1970.tab: {e}")

    unique_zones = sorted(set(zones))
    if "UTC" not in unique_zones:
        unique_zones.insert(0, "UTC")
    return {"timezones": unique_zones}


@router.get("/network_summary")
def fetch_network_summary(current_user: User = Depends(get_current_user)) -> dict:
    """Provides a summarized view of network stats and throughput."""
    try:
        return get_network_summary()
    except Exception as e:
        Logger.logger.error(f"Network summary fetch failed: {e}")
        raise HTTPException(status_code=500, detail="Unable to retrieve network summary.")


@router.get("/version")
def fetch_version(current_user: User = Depends(get_current_user)) -> str:
    return f"EdgeStream Hub {settings.VERSION}"
