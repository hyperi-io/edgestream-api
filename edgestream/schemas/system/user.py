from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, List
from pydantic import Field, field_validator, ConfigDict
from edgestream.schemas.base import ESBaseModel

class UserBase(ESBaseModel):
    """
    Base model for user properties shared across most schemas.
    """
    email: str = Field(..., description="User's unique email address.")
    full_name: str = Field(..., description="The user's legal or full name.")
    display_name: Optional[str] = Field(None, description="The name shown in the UI.")
    is_superuser: bool = Field(default=False)
    is_approved: bool = Field(default=False)
    otp_secret: Optional[str] = Field(None, description="Secret key for 2FA/OTP.")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        """Validates format and enforces lowercase normalization."""
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-.]+)*$"
        if not re.match(email_regex, value):
            raise ValueError("Invalid email address format")
        return value.lower()

class UserCreate(UserBase):
    """
    Model for creating a new user via standard API.
    """
    password: str = Field(..., min_length=8)

class UserCreateFromUI(ESBaseModel):
    """
    Model specifically for UI-driven user creation,
    supporting the 'enabled' alias used by the frontend.
    """
    email: str = Field(...)
    full_name: str = Field(..., description="Mandatory for UI creation")
    display_name: Optional[str] = None
    password: str = Field(..., min_length=8)
    enabled: bool = False
    is_superuser: bool = False

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return UserBase.check_email(value)

class UserUpdate(ESBaseModel):
    """
    Properties to receive via API on update. All optional for partial updates.
    """
    email: Optional[str] = None
    full_name: Optional[str] = None
    display_name: Optional[str] = None
    is_superuser: Optional[bool] = None
    is_approved: Optional[bool] = None
    otp_secret: Optional[str] = None

class UserPasswordUpdate(ESBaseModel):
    """
    Model for updating user passwords.
    """
    email: str = Field(...)
    current_password: str = Field(...)
    new_password: str = Field(..., min_length=8)

class UserInDBBase(UserBase):
    """
    Base properties stored in the database, including auto-generated metadata.
    """
    id: Optional[int] = Field(None, description="Primary key.")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class UserInDB(UserInDBBase):
    """
    Internal model including sensitive hashed password.
    Never returned directly to the client.
    """
    hashed_password: str

class User(UserInDBBase):
    """
    Default model returned for standard single-user API responses.
    """
    pass

class GetUser(UserInDBBase):
    """
    Explicit model for retrieving a user's details, ensuring
    timestamps are present for the UI and Exporter.
    """
    # Note: inheriting from UserInDBBase satisfies all requirements
    pass

class Users(ESBaseModel):
    """
    Model for listing multiple users.
    """
    users: List[GetUser] = Field(default_factory=list)

class TokenData(ESBaseModel):
    """Information encoded in the JWT token."""
    username: Optional[str] = None

class UserDeleteRequest(ESBaseModel):
    """Body for user deletion requests."""
    email: str

class UserUpdateRequest(ESBaseModel):
    """Body for admin user update requests by email lookup."""
    email: str
    full_name: Optional[str] = None
    display_name: Optional[str] = None
    is_superuser: Optional[bool] = None
    is_approved: Optional[bool] = None
    otp_secret: Optional[str] = None

# --- OTP / MFA specific schemas ---

class UserGenOtpRequest(ESBaseModel):
    email: str

class UserGenOtpResponse(ESBaseModel):
    email: Optional[str] = None
    otp_secret: Optional[str] = None
    otp_url: Optional[str] = None

class UserValidateOtpRequest(ESBaseModel):
    email: Optional[str] = None
    otp_secret: Optional[str] = None
    otp_url: Optional[str] = None
    otp_value: Optional[str] = None
