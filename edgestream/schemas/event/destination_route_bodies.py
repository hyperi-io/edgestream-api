"""
Project:   edgestream-api
File:      edgestream/schemas/event/destination_route_bodies.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List
from pydantic import Field
from edgestream.schemas.base import ESBaseModel

class DestinationRouteListBody(ESBaseModel):
    """Used to list all routes associated with a specific destination."""
    name: str = Field(..., description="The unique name of the destination.")


class DestinationRouteAddBody(ESBaseModel):
    """Used to append new labels to a destination's routing list."""
    name: str = Field(..., description="The unique name of the destination.")
    labels: List[str] = Field(
        ...,
        min_length=1,
        description="A list of one or more labels to add."
    )


class DestinationRouteReplaceBody(ESBaseModel):
    """Used to rename/replace a specific label for a single destination."""
    name: str = Field(..., description="The unique name of the destination.")
    old_label: str = Field(..., description="The existing label to be replaced.")
    new_label: str = Field(..., description="The new label value.")


class DestinationRouteDeleteBody(ESBaseModel):
    """Used to remove a specific label from a destination's routing list."""
    name: str = Field(..., description="The unique name of the destination.")
    label: str = Field(..., description="The specific label to remove.")


class DestinationRouteReplaceGlobalBody(ESBaseModel):
    """
    Used for global refactoring: replaces an old label with a new one
    across ALL destinations in the system.
    """
    old_label: str = Field(..., description="The label to find system-wide.")
    new_label: str = Field(..., description="The replacement label.")
