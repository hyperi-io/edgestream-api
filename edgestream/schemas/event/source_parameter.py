"""
Project:   edgestream-api
File:      edgestream/schemas/event/source_parameter.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import Optional, Any
from pydantic import Field
from edgestream.schemas.base import ESBaseModel

class SourceParameterBase(ESBaseModel):
    """
    Base representation of a Source Parameter.
    Used for key-value configuration pairs.
    """
    key: str = Field(
        ...,
        description="The configuration key identifier.",
        examples=["port"]
    )
    value: Optional[Any] = Field(
        None,
        description="The value associated with the key, can be of any type.",
        examples=[514]
    )

class SourceParameterCreate(SourceParameterBase):
    """
    Schema used for creating source parameters.
    Inherits requirements from SourceParamsBase.
    """
    pass

class SourceParameterUpdate(ESBaseModel):
    """
    Schema for updating source parameters.
    Fields are optional to allow for partial updates.
    """
    key: Optional[str] = Field(
        None,
        description="Optional update for the configuration key."
    )
    value: Optional[Any] = Field(
        None,
        description="Optional update for the configuration value."
    )
