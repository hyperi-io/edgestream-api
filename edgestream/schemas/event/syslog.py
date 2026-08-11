from typing import List, Optional
from enum import Enum
from pydantic import Field, field_validator
from edgestream.schemas.base import ESBaseModel

class Protocols(str, Enum):
    """Enumeration of supported transport protocols."""
    TCP = "tcp"
    UDP = "udp"

class ProtocolItem(ESBaseModel):
    """Individual protocol configuration for a listener."""
    protocol: str = Field(..., description="Transport protocol, either 'tcp' or 'udp'.")

    @field_validator("protocol", mode="before")
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Protocol must be a string")
        v_clean = v.strip().lower()
        if v_clean not in [p.value for p in Protocols]:
            raise ValueError("Protocol must be 'tcp' or 'udp'")
        return v_clean

class SyslogPort(ESBaseModel):
    """Full representation of a Syslog Listener as stored in the system."""
    id: Optional[int] = Field(None, description="Database primary key.")
    name: str = Field(..., description="Unique identifier/name for the syslog source.")
    port: int = Field(..., ge=1, le=65535, description="Network port number.")
    label: str = Field(..., description="Internal routing label.")
    protocols: List[ProtocolItem] = Field(default_factory=list)

class SyslogPortAll(ESBaseModel):
    """Wrapper for multiple syslog port configurations."""
    results: List[SyslogPort]

class SyslogPortCreate(ESBaseModel):
    """Schema for creating a new Syslog listener port."""
    port: int = Field(..., ge=1, le=65535)
    label: str = Field(..., min_length=1)
    protocols: List[ProtocolItem] = Field(..., min_length=1)

class SyslogPortUpdate(ESBaseModel):
    """Schema for updating an existing listener, identified by name."""
    name: str = Field(..., description="The unique name of the source to update.")
    port: int = Field(..., ge=1, le=65535)
    label: str = Field(..., min_length=1)
    protocols: List[ProtocolItem] = Field(..., min_length=1)

class SyslogPortDelete(ESBaseModel):
    """Schema for deleting a listener by its unique name."""
    name: str = Field(..., description="The unique name of the source to delete.")
