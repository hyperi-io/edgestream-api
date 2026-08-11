from pydantic import BaseModel


class DuplicateVPNResponse(BaseModel):
    detail: str = "File already exists in the system"


class SuccessfulVPNDelete(BaseModel):
    detail: str = "Successfully deleted VPN File"


class VPNFileNotFound(BaseModel):
    detail: str = "There's no VPN file uploaded. Please upload VPN file first"


class VPNExisting(BaseModel):
    detail: str = "Only one VPN file can be uploaded. Please delete existing file first before uploading."


class SuccessfulVPNCommandRun(BaseModel):
    detail: str = "{action} command has been successful ran on vpn file"


class VPNRunCommandMissingFile(BaseModel):
    detail: str = "Missing sh file for running the command. Please set it up first."


class GetVPNStatusResponse(BaseModel):
    result: str = "active"
