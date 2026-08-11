from pydantic import Field
from typing import Optional

from edgestream.schemas.base import ESBaseModel

class DestinationRouteBase(ESBaseModel):
    """
    Base schema for Destination Routes.
    Used for labeling event flows within the pipeline.
    """
    label: Optional[str] = Field(
        None,
        description="The label used to identify the route. Typically a string identifier.",
        examples=["route_label_1"],
    )

class DestinationRouteCreate(DestinationRouteBase):
    """
    Schema for creating a new Destination Route.
    """
    label: str = Field(
        ...,
        description="The label for the route. This field is required when creating a route.",
        examples=["new_route_label"],
    )

class DestinationRouteUpdate(ESBaseModel):
    """
    Schema for updating a Destination Route label.
    Inherits ConfigDict from ESBaseModel.
    """
    label: Optional[str] = Field(
        None,
        description="Optional updated label for the route.",
        examples=["updated_route_label"],
    )
