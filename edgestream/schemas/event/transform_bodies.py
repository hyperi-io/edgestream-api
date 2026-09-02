"""
Project:   edgestream-api
File:      edgestream/schemas/event/transform_bodies.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from pydantic import Field
from edgestream.schemas.base import ESBaseModel

class FetchTransformBody(ESBaseModel):
    """Used to request a single transformation node by its unique name."""
    name: str = Field(
        ..., 
        description="The unique name of the transform to fetch.",
        examples=["filter_error_logs"]
    )

class DeleteTransformBody(ESBaseModel):
    """Used for the body of a DELETE request to remove a transformation."""
    name: str = Field(
        ..., 
        description="The unique name of the transform to delete.",
        examples=["drop_debug_events"]
    )
