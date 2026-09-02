"""
Project:   edgestream-api
File:      edgestream/schemas/value/syslog_response.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from pydantic import BaseModel


class DuplicatePortResponse(BaseModel):
    detail: str = "Syslog with Port {port} already exists in the system"


class IncorrectSyslogResponse(BaseModel):
    detail: str = "Syslog Port with Port: {port} not found."


class DeleteSyslogResponse(BaseModel):
    detail: str = "Syslog Port with Port: {port} deleted."


get_syslog_error_responses = {
    400: {
        "content": {
            "application/json": {
                "examples": {
                    "DuplicatePortResponse": {
                        "value": {
                            "detail": "Syslog with Port {port} already exists in the system"
                        }
                    },
                    "InvalidProtocolResponse": {
                        "value": {
                            "detail": "Protocol {protocol} is invalid. Must be any of the following: ['udp', "
                            "'tcp']"
                        }
                    },
                },
            }
        }
    }
}
