from pydantic import Field
from edgestream.schemas.base import ESBaseModel

class FetchSourceBody(ESBaseModel):
    """Used to request a single event source by its unique name."""
    name: str = Field(
        ..., 
        description="The unique name of the source to fetch.",
        examples=["syslog-udp-514"]
    )

class DeleteSourceBody(ESBaseModel):
    """Used for the body of a DELETE request to remove a source."""
    name: str = Field(
        ..., 
        description="The unique name of the source to delete.",
        examples=["snmp-trap-collector"]
    )

class TemplateTypeBody(ESBaseModel):
    """Used to fetch parameter templates based on a specific source type."""
    type: str = Field(
        ..., 
        description="The source type (e.g., syslog, snmp, netflow).",
        examples=["syslog"]
    )
