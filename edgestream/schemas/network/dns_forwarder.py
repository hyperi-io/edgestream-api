"""
Project:   edgestream-api
File:      edgestream/schemas/network/dns_forwarder.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import Optional, List
from pydantic import Field
from edgestream.schemas.base import ESBaseModel

class DNSForwarderCreate(ESBaseModel):
    """
    Schema for creating a conditional DNS forwarder (split-horizon DNS).
    """
    domain: str = Field(
        ...,
        description="The domain name to forward queries for (e.g., internal.corp).",
        examples=["internal.local"]
    )
    ip_address: str = Field(
        ...,
        description="The IP address of the upstream DNS server for this domain.",
        examples=["10.0.0.50"]
    )
    port: int = Field(
        default=53,
        ge=1,
        le=65535,
        description="The port of the upstream DNS server."
    )

class ListDNSForwarderCreate(ESBaseModel):
    """
    Wrapper for bulk-creating DNS forwarders.
    """
    dns_forwarders: List[DNSForwarderCreate] = Field(..., min_length=1)

class DNSForwarderBase(ESBaseModel):
    """
    Full representation of a DNS Forwarder as stored in the database.
    """
    id: int = Field(..., description="Database primary key.")
    domain: str = Field(..., description="The domain being forwarded.")
    ip_address: str = Field(..., description="Target upstream IP address.")
    port: int = Field(default=53, ge=1, le=65535)

class ListDNSForwarderBase(ESBaseModel):
    """
    Wrapper for responding with a list of forwarders.
    """
    result: List[DNSForwarderBase]

class DNSForwarderUpdate(ESBaseModel):
    """
    Used to update an existing forwarder by ID.
    Note: ID is required to identify the row in a body-only PUT request.
    """
    id: int = Field(..., description="The ID of the forwarder to update.")
    domain: Optional[str] = Field(None, description="Updated domain name.")
    ip_address: Optional[str] = Field(None, description="Updated upstream IP.")
    port: Optional[int] = Field(None, ge=1, le=65535)

class DNSForwarderDelete(ESBaseModel):
    """
    Used to delete a forwarder, typically by its unique domain name.
    """
    domain: str = Field(..., description="The unique domain name of the forwarder to remove.")
