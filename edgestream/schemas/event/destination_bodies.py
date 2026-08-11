from typing import List
from pydantic import Field
from edgestream.schemas.base import ESBaseModel
from edgestream.schemas.event.destination_parameter import DestinationParameterUpdate

class FetchDestinationBody(ESBaseModel):
    """Used to request a single destination by its unique name."""
    name: str = Field(..., description="The unique name of the destination to fetch.")


class DeleteDestinationBody(ESBaseModel):
    """Used for the body of a DELETE request."""
    name: str = Field(..., description="The unique name of the destination to delete.")


class TemplateTypeBody(ESBaseModel):
    """Used to fetch parameter templates based on a specific destination type."""
    type: str = Field(..., description="The destination type (e.g., s3, syslog, elasticsearch).")


class ModifySettingBody(ESBaseModel):
    """Used to update specific parameter settings for a destination."""
    name: str = Field(..., description="The name of the destination to modify.")
    settings: List[DestinationParameterUpdate] = Field(
        ...,
        description="A list of key-value parameter pairs to update."
    )
