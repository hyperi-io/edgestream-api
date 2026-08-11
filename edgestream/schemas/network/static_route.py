from pydantic import Field
from edgestream.schemas.base import ESBaseModel


class StaticRoute(ESBaseModel):
    """
    Representation of a static network route.
    """
    to: str = Field(
        ...,
        description="The destination network or host in CIDR notation.",
        examples=["10.10.0.0/24"]
    )
    via: str = Field(
        ...,
        description="The gateway IP address (next hop).",
        examples=["192.168.1.1"]
    )
    device: str = Field(
        ...,
        description="The network interface device name.",
        examples=["eth0"]
    )


class StaticRouteCreate(StaticRoute):
    """
    Schema for adding a new static route to the routing table.
    """
    pass


class StaticRouteUpsert(ESBaseModel):
    """
    Used to update an existing route by matching the current
    triplet and replacing it with a new triplet.
    """
    current_to: str = Field(..., description="Current destination CIDR.")
    current_via: str = Field(..., description="Current gateway IP.")
    current_device: str = Field(..., description="Current interface.")

    new_to: str = Field(..., description="New destination CIDR.")
    new_via: str = Field(..., description="New gateway IP.")
    new_device: str = Field(..., description="New interface.")


class StaticRouteDelete(ESBaseModel):
    """
    Schema for removing a static route.
    Requires the exact triplet to ensure the correct route is targeted.
    """
    to: str = Field(..., description="Destination CIDR of the route to remove.")
    via: str = Field(..., description="Gateway IP of the route to remove.")
    device: str = Field(..., description="Interface device of the route to remove.")
