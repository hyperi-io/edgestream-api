from pydantic import Field
from edgestream.schemas.base import ESBaseModel

class DNSServer(ESBaseModel):
    """
    Representation of a DNS Server entry.
    """
    ip_address: str = Field(
        ...,
        description="The IPv4 or IPv6 address of the DNS server.",
        examples=["8.8.8.8"]
    )
    port: int = Field(
        default=53,
        ge=1,
        le=65535,
        description="Network port for DNS queries (usually 53)."
    )

class DNSCreate(DNSServer):
    """
    Schema for adding a new DNS server to the system.
    """
    pass

class DNSUpsert(ESBaseModel):
    """
    Used to update an existing DNS entry by matching the old
    address/port and replacing them with new values.
    """
    current_ip: str = Field(..., description="The IP address currently in the database.")
    current_port: int = Field(..., ge=1, le=65535)
    new_ip: str = Field(..., description="The new IP address to set.")
    new_port: int = Field(..., ge=1, le=65535)

class DNSDelete(ESBaseModel):
    """
    Schema for removing a DNS server entry.
    """
    ip_address: str = Field(..., description="IP address of the server to remove.")
    port: int = Field(..., ge=1, le=65535)
