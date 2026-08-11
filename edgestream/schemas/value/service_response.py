from pydantic import BaseModel


class DuplicateServiceResponse(BaseModel):
    detail: str = "Service name already exists in the system"


class IncorrectServiceNameResponse(BaseModel):
    detail: str = "Service with Name {name} not found"


class DeleteServiceResponse(BaseModel):
    detail: str = "Service with Name: {name} deleted."


get_generic_error_responses = {
    400: {
        "content": {
            "application/json": {
                "examples": {
                    "IncorrectServiceNameResponse": {
                        "value": {"detail": "Service with Name {name} not found"}
                    },
                    "IncorrectCertificateResponse": {
                        "value": {
                            "detail": "Certificate {filename} is not found. Please add the certificate first"
                        }
                    },
                },
            }
        }
    }
}
