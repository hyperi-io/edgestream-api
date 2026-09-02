"""
Project:   edgestream-api
File:      edgestream/schemas/value/user_response.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from pydantic import BaseModel


class LoginBadRequestResponse(BaseModel):
    detail: str = "Incorrect password"


class UserNotFoundResponse(BaseModel):
    detail: str = "Username does not exists"


class UnauthenticatedResponse(BaseModel):
    detail: str = "Not authenticated"


class DuplicateUserResponse(BaseModel):
    detail: str = "The user with this email already exists in the system"


class SuccessLoginResponse(BaseModel):
    access_token: str
    token_type: str
