from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re

class QueryRow(BaseModel):
    path: str
    selector: str

_CIDR = re.compile(r"^(\d{1,3}\.){3}\d{1,3}/(\d{1,2}|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$")

class SubscriptionPayload(BaseModel):
    name: str
    version: str
    uri: Optional[str] = None
    query: List[QueryRow] = Field(default_factory=list)

    heartbeat_interval: int = 3600
    connection_retry_count: int = 0
    connection_retry_interval: int = 60
    max_time: int = 30
    max_envelope_size: int = 512000

    enabled: bool = True
    read_existing_events: bool = True
    content_format: str = "RenderedText"
    ignore_channel_error: bool = True
    locale: Optional[str] = None
    data_locale: Optional[str] = None

    # Default permitted is open; you can change to ["0.0.0.0/0"] if you prefer
    permitted: List[str] = Field(default_factory=list)
    prohibited: List[str] = Field(default_factory=list)

    @field_validator("heartbeat_interval", "connection_retry_interval", "max_time")
    @classmethod
    def gt_zero(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Must be > 0")
        return v

    @field_validator("connection_retry_count")
    @classmethod
    def ge_zero(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Must be >= 0")
        return v

    @field_validator("max_envelope_size")
    @classmethod
    def min_env(cls, v: int) -> int:
        if v < 4096:
            raise ValueError("Minimum 4096")
        return v

    @field_validator("query")
    @classmethod
    def query_valid(cls, rows: List[QueryRow]) -> List[QueryRow]:
        if not rows or any((not r.path or not r.selector) for r in rows):
            raise ValueError("Each query row needs a path and selector")
        return rows

    @field_validator("permitted", "prohibited")
    @classmethod
    def cidrs_ok(cls, cidrs: List[str]) -> List[str]:
        for c in cidrs:
            if not _CIDR.match(c.strip()):
                raise ValueError(f"Invalid CIDR: {c}")
        return cidrs

class SubscriptionRow(SubscriptionPayload):
    id: int
