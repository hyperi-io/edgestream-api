import json
from typing import Optional, Any
from pydantic import Field, field_validator, ConfigDict

from edgestream.schemas.base import ESBaseModel


class DestinationParameterBase(ESBaseModel):
    """
    Base schema for Destination Parameters.
    Handles automatic JSON string deserialization for complex types (lists/dicts).
    """
    key: Optional[str] = Field(
        None,
        description="The key for the parameter identifier.",
        examples=["url"],
    )
    value: Optional[Any] = Field(
        None,
        description="The value for the parameter, can be a string, number, or JSON-serialized object.",
        examples=["http://example.com"],
    )

    @field_validator("value", mode="before")
    @classmethod
    def deserialize_value(cls, v: Any) -> Any:
        """
        If the incoming value is a string that looks like JSON (starts with { or [),
        attempt to parse it into a Python object.
        """
        if isinstance(v, str):
            v_strip = v.strip()
            if (v_strip.startswith("{") and v_strip.endswith("}")) or \
                    (v_strip.startswith("[") and v_strip.endswith("]")):
                try:
                    return json.loads(v_strip)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON string provided for value: {e.msg}")
        return v

    @staticmethod
    def serialize_value(v: Any) -> str:
        """
        Utility method for CRUD operations to ensure complex types 
        are stored as JSON strings in the database.
        """
        if isinstance(v, str):
            v_strip = v.strip()
            if (v_strip.startswith("{") and v_strip.endswith("}")) or \
                    (v_strip.startswith("[") and v_strip.endswith("]")):
                try:
                    json.loads(v_strip)
                except json.JSONDecodeError:
                    raise ValueError("Refusing to store invalid JSON-looking string as raw string.")

        if isinstance(v, (list, dict)):
            return json.dumps(v)
        return str(v) if v is not None else ""


class DestinationParameterCreate(DestinationParameterBase):
    """
    Schema for creating a new destination parameter. Keys and values are mandatory.
    """
    key: str = Field(..., description="Required key identifier.")
    value: Any = Field(..., description="Required value.")


class DestinationParameterUpdate(ESBaseModel):
    """
    Schema for updating parameters. Inherits Config from ESBaseModel.
    """
    key: Optional[str] = Field(None, description="The parameter key to update.")
    value: Optional[Any] = Field(None, description="The new value for the parameter.")

    @field_validator("value", mode="before")
    @classmethod
    def deserialize_value(cls, v: Any) -> Any:
        return DestinationParameterBase.deserialize_value(v)
