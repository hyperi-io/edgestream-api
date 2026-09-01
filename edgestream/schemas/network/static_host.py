"""
Project:   edgestream-api
File:      edgestream/schemas/network/static_host.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from pydantic import Field
from edgestream.schemas.base import ESBaseModel

class StaticHost(ESBaseModel):
    """
    Representation of a static host entry (local DNS/hosts file).
    """
    host: str = Field(
        ...,
        description="The hostname or FQDN of the static entry.",
        examples=["myserver.local"]
    )
    ip_address: str = Field(
        ...,
        description="The IPv4 or IPv6 address associated with the host.",
        examples=["192.168.1.10"]
    )

class StaticHostCreate(StaticHost):
    """
    Schema for adding a new static host mapping.
    """
    pass

class StaticHostUpsert(ESBaseModel):
    """
    Used to update an existing static host entry by matching the old
    hostname and replacing it with new values.
    """
    current_host: str = Field(..., description="The hostname currently in the database.")
    new_host: str = Field(..., description="The new hostname to set.")
    new_ip_address: str = Field(..., description="The new IP address to set.")

class StaticHostDelete(ESBaseModel):
    """
    Schema for removing a static host entry by its hostname.
    """
    host: str = Field(..., description="The hostname of the entry to remove.")
