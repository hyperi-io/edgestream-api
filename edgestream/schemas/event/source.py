from typing import Optional, List
from pydantic import Field
from edgestream.schemas.base import ESBaseModel
from edgestream.schemas.event.source_parameter import SourceParameterBase, SourceParameterCreate

class Source(ESBaseModel):
    """
    Base representation of an Event Source.
    """
    name: Optional[str] = Field(None, description="The unique name of the source.")
    type: str = Field(default="", description="The type of source (e.g., syslog, snmp).")
    enabled: bool = Field(default=False, description="Whether the source is currently active.")
    system: bool = Field(default=False, description="Flag indicating if this is a system-protected source.")
    settings: List[SourceParameterBase] = Field(
        default_factory=list,
        description="Configuration parameters associated with this source."
    )

class SourceCreate(ESBaseModel):
    """
    Schema for creating a new Event Source.
    """
    name: str = Field(..., description="The name must be provided for a new source.")
    type: str = Field(..., description="The type must be provided for a new source.")
    enabled: bool = Field(default=False)
    system: bool = Field(default=False)
    settings: List[SourceParameterCreate] = Field(default_factory=list)

class SourceUpdate(ESBaseModel):
    """
    Schema for updating an existing Event Source.
    All fields are optional to support partial updates (PATCH style).
    """
    name: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None
    system: Optional[bool] = None
    settings: Optional[List[SourceParameterBase]] = None

class SourceDelete(ESBaseModel):
    """
    Schema for deleting a source, typically requiring only the name.
    """
    name: str = Field(..., description="The name of the source to be deleted.")

class SourceInDB(Source):
    """
    Represents the source as it exists in the database, including the primary key.
    """
    id: int = Field(..., description="Database primary key.")
