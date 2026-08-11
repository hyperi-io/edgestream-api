from typing import List, Optional, Any
from pydantic import BaseModel, ConfigDict

class DestinationParameterBase(BaseModel):
    key: str
    value: Any

class DestinationCreate(BaseModel):
    name: str
    type: str
    enabled: bool = False
    system: bool = False
    fallback: bool = False
    settings: Optional[List[DestinationParameterBase]] = []
    routes: Optional[List[str]] = []  # List of source names used for routing

    model_config = ConfigDict(from_attributes=True)

class DestinationUpdate(BaseModel):
    name: str  # Used to locate the destination
    type: Optional[str] = None
    enabled: Optional[bool] = None
    system: Optional[bool] = None
    fallback: Optional[bool] = None
    settings: Optional[List[DestinationParameterBase]] = None
    routes: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)
