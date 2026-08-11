from typing import Optional, List
from pydantic import Field
from edgestream.schemas.base import ESBaseModel

class Package(ESBaseModel):
    """
    Represents a single system package with versioning and origin metadata.
    """
    package: Optional[str] = Field(None, description="The name of the package.")
    current_version: Optional[str] = Field(None, description="The version currently installed on the system.")
    available_version: Optional[str] = Field(None, description="The latest version available in the repository.")
    origin: Optional[str] = Field(None, description="The source repository or origin.")
    archive: Optional[str] = Field(None, description="The archive/component (e.g., main, universe).")
    site: Optional[str] = Field(None, description="The mirror or site URL.")
    description: Optional[str] = Field(None, description="A brief summary of the package.")

class UpdatesAvailable(ESBaseModel):
    """
    Wrapper for a collection of available package updates.
    """
    packages: List[Package] = Field(
        default_factory=list,
        description="A list of packages that have updates available."
    )
