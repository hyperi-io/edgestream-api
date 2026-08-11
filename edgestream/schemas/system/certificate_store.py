from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import Field, ConfigDict
from edgestream.schemas.base import ESBaseModel

class CertificateTypes(str, Enum):
    """Enumeration of supported certificate components."""
    CERTIFICATE_AUTHORITY = "certificate_authority"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"

    @classmethod
    def list(cls):
        return [e.value for e in cls]

class CertificateBase(ESBaseModel):
    """
    Base attributes for a Certificate record.
    """
    filename: str = Field(default="keyfile.cert", description="Name of the certificate file.")
    type: str = Field(default="certificate_authority", description="Role of the file (CA, Cert, or Key).")
    filesize: int = Field(default=0, description="Size of the file in bytes.")
    thumbprint: Optional[str] = Field(default=None, description="SHA thumbprint/fingerprint.")
    data: Optional[bytes] = Field(default=None, description="Raw binary certificate data.")
    file_extension: Optional[str] = Field(default=None, description="File extension (e.g., .pem, .crt).")
    not_after: Optional[datetime] = Field(default=None, description="Certificate expiry")
    common_name: Optional[str] = Field(default=None, description="Certificate common name")
    issuer: Optional[str] = Field(default=None, description="Certificate issuer")

class CertificateCreate(CertificateBase):
    """Schema for adding a new certificate to the store."""
    type: str = Field(default="certificate_authority")

class CertificateUpdate(ESBaseModel):
    """Attributes allowed for certificate metadata updates."""
    filename: Optional[str] = None
    type: Optional[str] = None

class CertificateRemove(ESBaseModel):
    """Used to identify a certificate for deletion."""
    id: int = Field(..., description="ID of the certificate to remove.")
    filename: str = Field(..., description="Filename for verification.")

class CertificateInDBBase(CertificateBase):
    """Full representation including database primary key."""
    id: int = Field(..., description="Database primary key.")

class Certificate(CertificateInDBBase):
    """Standard certificate representation for API responses."""
    pass

class CertificateAll(ESBaseModel):
    """Wrapper for listing multiple certificates."""
    results: List[Certificate] = Field(default_factory=list)

class CertificateUpload(CertificateBase):
    """Schema for successful upload feedback."""
    pass

class AllCertificateUpload(ESBaseModel):
    """Wrapper for bulk upload results."""
    results: List[CertificateUpload] = Field(default_factory=list)

class CertificateService(ESBaseModel):
    """
    Specialized view for internal service consumption.
    Note: 'data' is typed as str here, assuming base64 encoding for certain services.
    """
    id: Optional[int] = None
    filename: Optional[str] = None
    type: Optional[str] = None
    filesize: int = 0
    thumbprint: Optional[str] = None
    data: Optional[str] = None  # Base64 string representation
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

class GetCertificate(ESBaseModel):
    """
    Categorized view of the certificate store.
    """
    certificate_authority: List[Certificate] = Field(default_factory=list)
    certificate: List[Certificate] = Field(default_factory=list)
    private_key: List[Certificate] = Field(default_factory=list)
