# edgestream/core/schemas/base.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class ESBaseModel(BaseModel):
    """
    Common base model for all EdgeStream schemas.
    Enables ORM mode (from_attributes) and flexible field population.
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class TaskScheduledResponse(ESBaseModel):
    """
    Standard tracking response for any endpoint that enqueues
    a background Ansible or System task.
    """
    identifier: str = Field(
        ...,
        description="The unique UUID for the background job (matches DB identifier)."
    )
    detail: str = Field(
        ...,
        description="A human-readable message about the task status."
    )
    status: str = Field(
        default="queued",
        description="Initial execution state of the task."
    )
    playbook: Optional[str] = Field(
        None,
        description="The specific Ansible playbook name being executed, if applicable."
    )
