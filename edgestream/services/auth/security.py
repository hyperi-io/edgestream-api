"""
Project:   edgestream-api
File:      edgestream/services/auth/security.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import jwt
import bcrypt

from edgestream.core.config import settings


def _strip_bytes_repr(maybe_repr: str) -> str:
    """Fixes legacy DB entries stored incorrectly as 'b'string''."""
    if (
            isinstance(maybe_repr, str)
            and maybe_repr.startswith("b'")
            and maybe_repr.endswith("'")
    ):
        return maybe_repr[2:-1]
    return maybe_repr


def hash_password(plain: str) -> str:
    """Hashes password with salt. Returns utf-8 string."""
    if not plain:
        raise ValueError("Password cannot be empty")

    salt = bcrypt.gensalt()
    hashed: bytes = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain against hash with legacy repr tolerance."""
    try:
        normalized_hash = _strip_bytes_repr(hashed_password)
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            normalized_hash.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(*, subject: Union[str, int], minutes: Optional[int] = None) -> str:
    """Generates signed JWT for authenticated sessions."""
    iat = datetime.now(timezone.utc)
    expire_minutes = minutes or settings.ACCESS_TOKEN_MINUTES
    exp = iat + timedelta(minutes=expire_minutes)

    payload = {
        "sub": str(subject),
        "iat": int(iat.timestamp()),
        "nbf": int(iat.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": str(uuid.uuid4()),
        "scope": "access",
    }

    if settings.JWT_ISSUER:
        payload["iss"] = settings.JWT_ISSUER
    if settings.JWT_AUDIENCE:
        payload["aud"] = settings.JWT_AUDIENCE

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
