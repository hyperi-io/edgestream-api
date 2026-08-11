from typing import Optional, List
from pydantic import Field, field_validator, ConfigDict

from edgestream.schemas.base import ESBaseModel

# Domain Constants
_ALLOWED_TYPES = {"filter"}                  
_ALLOWED_QUERY_SYNTAX = {"query_builder", "vrl"}

class TransformBase(ESBaseModel):
    """
    Base attributes for Data Transformations.
    """
    name: Optional[str] = Field(None, description="The unique name of the transform.")
    description: str = Field(default="", description="Human-readable description.")
    type: Optional[str] = Field(None, description="Transform kind (e.g., 'filter').")
    parent: List[str] = Field(
        default_factory=list, 
        description="List of parent source/transform names feeding this node."
    )
    query_syntax: Optional[str] = Field(
        None, 
        description="The engine used (vrl or query_builder)."
    )
    query_builder: Optional[str] = Field(None, description="JSON string for the UI Query Builder.")
    query_raw: Optional[str] = Field(None, description="The raw VRL or filter string.")
    enabled: bool = Field(default=False)

    @field_validator("parent", mode="before")
    @classmethod
    def split_parent_string(cls, v):
        """Coerce a CSV string into a list of strings if provided."""
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v or []

    @field_validator("type", mode="before")
    @classmethod
    def normalize_and_validate_type(cls, v):
        if not v:
            return v
        v_clean = str(v).lower()
        if v_clean not in _ALLOWED_TYPES:
            raise ValueError(f"Invalid transform type '{v_clean}'. Allowed: {sorted(_ALLOWED_TYPES)}")
        return v_clean

    @field_validator("query_syntax", mode="before")
    @classmethod
    def normalize_and_validate_syntax(cls, v):
        if not v:
            return v
        v_clean = str(v).lower()
        if v_clean not in _ALLOWED_QUERY_SYNTAX:
            raise ValueError(f"Invalid query_syntax '{v_clean}'. Allowed: {sorted(_ALLOWED_QUERY_SYNTAX)}")
        return v_clean

class Transform(TransformBase):
    """Standard representation for API responses."""
    pass

class TransformCreate(TransformBase):
    """
    Attributes required to create a new Transform.
    """
    name: str = Field(..., min_length=1)
    type: str = Field(...)
    query_syntax: str = Field(...)
    parent: List[str] = Field(default_factory=list)
    enabled: bool = Field(default=False)

class TransformUpdate(TransformBase):
    """
    Schema for updating a Transform. 
    Endpoints require name/type/syntax to re-validate logic.
    """
    name: str = Field(...)
    type: str = Field(...)
    query_syntax: str = Field(...)

class TransformDelete(ESBaseModel):
    """
    Body schema for delete requests.
    """
    name: str = Field(..., description="Unique name of the transform to remove.")

class TransformInDBBase(TransformBase):
    """
    Full representation including DB primary key.
    """
    id: int = Field(..., description="Database primary key.")
