from enum import Enum
from typing import Optional, List
from pydantic import Field, ConfigDict
from edgestream.schemas.base import ESBaseModel

# -------- Base System Models --------

class SystemBase(ESBaseModel):
    hostname: Optional[str] = Field(None, examples=["edgestream-node-01"])
    org_id: Optional[str] = Field(None, examples=["org-1234"])
    site_id: Optional[str] = Field(None, examples=["site-alpha"])
    timezone: Optional[str] = Field(None, examples=["UTC"])

class SystemCreate(SystemBase):
    pass

class SystemUpdate(SystemBase):
    pass

class SystemUpdateRestricted(ESBaseModel):
    id: int = Field(..., description="ID of the restricted setting.")
    label: str = Field(..., description="The configuration key/label.")

# -------- IP and Interface Models --------

class SystemIPAddress(ESBaseModel):
    ip_address: str

class SystemIPAddresses(ESBaseModel):
    ip_addresses: List[str] = Field(default_factory=list)

class SystemMgmtIface(ESBaseModel):
    management_iface: str = Field(..., examples=["eth0"])

class SystemMgmtIfaceUpdate(ESBaseModel):
    management_iface: str

# -------- Disk Partition Models --------

class SystemPartition(ESBaseModel):
    mount_point: str
    disk_total_bytes: int
    disk_total_human_readable: str
    disk_used_bytes: int
    disk_used_human_readable: str
    disk_free_bytes: int
    disk_free_human_readable: str
    disk_usage_percent: float

class SystemPartitions(ESBaseModel):
    partitions: List[SystemPartition] = Field(default_factory=list)

# -------- User Models --------

class LastUser(ESBaseModel):
    username: str
    terminal: Optional[str] = None
    host: Optional[str] = None
    logged_in: Optional[str] = None
    duration: Optional[str] = None
    active: bool = False

class LastUsers(ESBaseModel):
    users: List[LastUser] = Field(default_factory=list)

class SystemUser(ESBaseModel):
    name: str
    terminal: Optional[str] = None
    host: Optional[str] = None
    started: Optional[str] = None
    pid: Optional[int] = None

class SystemUsers(ESBaseModel):
    users: List[SystemUser] = Field(default_factory=list)

# -------- Uptime Models --------

class SystemUptime(ESBaseModel):
    secs: int
    human_readable: str

class SystemUptimes(ESBaseModel):
    uptime: SystemUptime

# -------- Individual Property Models --------

class SystemHostname(ESBaseModel):
    hostname: str

class SystemHostnameUpdate(ESBaseModel):
    hostname: str

class SystemOrgID(ESBaseModel):
    org_id: str

class SystemOrgIDUpdate(ESBaseModel):
    org_id: str

class SystemSiteID(ESBaseModel):
    site_id: str

class SystemSiteIDUpdate(ESBaseModel):
    site_id: str

class SystemTimezone(ESBaseModel):
    timezone: str

class SystemTimezoneUpdate(ESBaseModel):
    timezone: str

# -------- Database Models --------

class SystemInDBBase(SystemBase):
    id: int = Field(..., description="Primary key.")
    submitter_id: int = Field(..., description="ID of user who last modified.")

class System(SystemInDBBase):
    pass

class SystemInDB(SystemInDBBase):
    pass

class SystemSearchResults(ESBaseModel):
    results: List[System] = Field(default_factory=list)

# -------- Composite and Component Models --------

class SystemAggregate(
    SystemHostname,
    SystemUptimes,
    SystemIPAddresses,
    SystemPartitions,
    LastUsers,
):
    """
    Unified view of current system status.
    Inherits all fields from individual status schemas.
    """
    pass

class InterfaceTypes(str, Enum):
    MANAGEMENT = "management"
    EVENT = "event"

    @classmethod
    def list(cls):
        return [c.value for c in cls]

class SystemComponents(ESBaseModel):
    sources_enabled: int = Field(default=0)
    sinks_enabled: int = Field(default=0)
