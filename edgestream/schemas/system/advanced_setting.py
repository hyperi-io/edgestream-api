from typing import Optional, List
from pydantic import Field
from edgestream.schemas.base import ESBaseModel

class AdvancedSettingBase(ESBaseModel):
    """
    Base representation of a system advanced setting.
    """
    id: Optional[int] = Field(None, description="Database primary key.")
    label: Optional[str] = Field(None, description="The unique key for the setting.")
    value: Optional[str] = Field(None, description="The currently active value.")
    description: Optional[str] = Field(None, description="Human-readable explanation of the setting.")
    default_value: Optional[str] = Field(None, description="The fallback value if not modified.")

class AdvancedSettingCreate(ESBaseModel):
    """
    Schema for creating a new advanced setting entry.
    """
    label: str = Field(..., min_length=1, description="Unique identifier for the setting.")
    value: str = Field(default="", description="The value to be stored.")
    description: str = Field(default="", description="Context for the setting.")
    default_value: str = Field(default="", description="The factory default value.")

class AdvancedSettingUpdate(ESBaseModel):
    """
    Schema for updating an existing setting.
    """
    label: Optional[str] = Field(None, description="Optionally update the label.")
    value: Optional[str] = Field(None, description="The new value to apply.")
    description: Optional[str] = Field(None, description="Updated description.")
    default_value: Optional[str] = Field(None, description="Updated default value.")

class AdvancedSettingUpdateAll(ESBaseModel):
    """
    Used for bulk updates of system settings.
    """
    advanced_settings: List[AdvancedSettingBase] = Field(
        default_factory=list,
        description="A list of settings to be updated in bulk."
    )

class AdvancedSettingAll(ESBaseModel):
    """
    Wrapper for returning all system settings.
    """
    advanced_settings: List[AdvancedSettingBase] = Field(
        default_factory=list,
        description="The full list of system advanced settings."
    )
