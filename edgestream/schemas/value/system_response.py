from pydantic import BaseModel

from edgestream.schemas.system.system import InterfaceTypes


class DatabaseMalformedResponse(BaseModel):
    detail: str = "Database is malformed, please contact an administrator."


class InterfaceNotFoundResponse(BaseModel):
    detail: str = "Interface with Name {name} not found"


class DuplicateInterfaceResponse(BaseModel):
    detail: str = "Interface with that type already exists in the system"


class DuplicateSystemResponse(BaseModel):
    detail: str = "Service name already exists in the system"


class IncorrectSystemResponse(BaseModel):
    detail: str = "Service with Name {name} not found"


class IncorrectInterfaceResponse(BaseModel):
    detail: str = (
        f"Incorrect Interface type. Must be the following {InterfaceTypes.list()}"
    )


get_generic_error_responses = {
    400: {
        "content": {
            "application/json": {
                "examples": {
                    "FileNotFoundErrorResponse": {
                        "value": {
                            "detail": "Process failed because the executable could not be found.\n{exc}"
                        }
                    },
                    "CalledProcessErrorResponse": {
                        "value": {
                            "detail": "last command not implemented on this platform"
                        }
                    },
                    "TimeoutExpiredErrorResponse": {
                        "value": {"detail": "last command process timed out"}
                    },
                },
            }
        }
    }
}


interface_bad_request_responses = {
    400: {
        "content": {
            "application/json": {
                "examples": {
                    "BadRequestResponse": {
                        "value": {
                            "detail": f"Incorrect Interface type. Must be any of the following {InterfaceTypes.list()}"
                        }
                    },
                    "IntegrityErrorResponse": {
                        "value": {
                            "detail": f"Interface with that type and name already exists in the system"
                        }
                    },
                }
            }
        }
    }
}
