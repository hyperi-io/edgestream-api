from pydantic import BaseModel


class DuplicateCertResponse(BaseModel):
    detail: str = "Filename already exists in the system"


class IncorrectCertResponse(BaseModel):
    detail: str = "Certificate with ID: {id} not found."


class CorrectCertResponse(BaseModel):
    details: str = "Download File link should be available on successful request"
