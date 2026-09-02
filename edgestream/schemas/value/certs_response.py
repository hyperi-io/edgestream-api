"""
Project:   edgestream-api
File:      edgestream/schemas/value/certs_response.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from pydantic import BaseModel


class DuplicateCertResponse(BaseModel):
    detail: str = "Filename already exists in the system"


class IncorrectCertResponse(BaseModel):
    detail: str = "Certificate with ID: {id} not found."


class CorrectCertResponse(BaseModel):
    details: str = "Download File link should be available on successful request"
