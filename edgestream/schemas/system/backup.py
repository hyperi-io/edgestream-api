from typing import Optional, List
from pydantic import Field
from edgestream.schemas.base import ESBaseModel

class BackupBase(ESBaseModel):
    """
    Base attributes for system backups.
    Supports local file storage, AWS S3, and Google Cloud Storage (GCS).
    """
    enabled: Optional[bool] = Field(None, description="Whether this backup target is active.")
    provider: Optional[str] = Field(None, description="Storage provider: 'file', 's3', or 'gcs'.")
    path: Optional[str] = Field(None, description="Local filesystem path for 'file' provider.")
    bucket_name: Optional[str] = Field(None, description="Cloud storage bucket name.")
    region: Optional[str] = Field(None, description="Cloud storage region (S3).")
    access_key_id: Optional[str] = Field(None, description="AWS Access Key ID.")
    secret_access_key: Optional[str] = Field(None, description="AWS Secret Access Key.")
    endpoint_url: Optional[str] = Field(None, description="Optional S3-compatible endpoint URL.")
    gcs_project_id: Optional[str] = Field(None, description="Google Cloud Project ID.")
    gcs_credentials_json: Optional[str] = Field(None, description="GCS Service Account JSON string.")
    retention: Optional[str] = Field(None, description="Retention period (e.g., '30d').")
    schedule: Optional[str] = Field(None, description="Backup frequency (e.g., '12h').")

class BackupCreate(BackupBase):
    """
    Attributes required to create a new backup target.
    Includes default values for standard configurations.
    """
    enabled: bool = Field(default=False)
    provider: str = Field(default="file")
    path: str = Field(default="")
    bucket_name: str = Field(default="")
    region: str = Field(default="")
    access_key_id: str = Field(default="")
    secret_access_key: str = Field(default="")
    endpoint_url: str = Field(default="")
    gcs_project_id: str = Field(default="")
    gcs_credentials_json: str = Field(default="")
    retention: str = Field(default="30d")
    schedule: str = Field(default="12h")

class BackupUpdate(BackupBase):
    """
    Attributes for updating an existing backup target.
    All fields are optional to allow partial updates.
    """
    pass

class BackupResponse(BackupBase):
    """
    Standard response model for a single backup target.
    Guarantees key fields are present in the JSON response.
    """
    enabled: bool
    provider: str
    retention: str
    schedule: str

class BackupTargetResponse(BackupResponse):
    """
    Alias for BackupResponse used in multi-target contexts.
    """
    pass

class BackupTargetsResponse(ESBaseModel):
    """
    Wrapper for returning all configured backup targets.
    """
    targets: List[BackupTargetResponse] = Field(
        default_factory=list,
        description="A list of all configured backup providers and their settings."
    )
