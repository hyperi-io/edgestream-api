from pydantic import Field
from edgestream.schemas.base import ESBaseModel

class NTPServer(ESBaseModel):
    """
    Representation of an NTP Server entry.
    """
    ip_address: str = Field(
        ..., 
        description="The IPv4 or IPv6 address of the NTP server.",
        examples=["pool.ntp.org", "129.6.15.28"]
    )
    port: int = Field(
        default=123, 
        ge=1, 
        le=65535, 
        description="Network port for NTP synchronization (standard is 123)."
    )

class NTPCreate(NTPServer):
    """
    Schema for adding a new NTP server to the system.
    """
    pass

class NTPUpsert(ESBaseModel):
    """
    Used to update an existing NTP entry by matching the old 
    address/port and replacing them with new values.
    """
    current_ip: str = Field(..., description="The IP address currently in the database.")
    current_port: int = Field(..., ge=1, le=65535)
    new_ip: str = Field(..., description="The new IP address to set.")
    new_port: int = Field(..., ge=1, le=65535)

class NTPDelete(ESBaseModel):
    """
    Schema for removing an NTP server entry.
    """
    ip_address: str = Field(..., description="IP address of the server to remove.")
    port: int = Field(..., ge=1, le=65535)
