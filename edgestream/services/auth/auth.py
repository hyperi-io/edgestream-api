from __future__ import annotations

import pyotp
import jwt
from typing import Optional, Union, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import ExpiredSignatureError, PyJWTError
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import settings, Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.services.auth.security import verify_password, hash_password

security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


def decode_token_or_401(token: str) -> dict:
    """Decodes a JWT or raises a standardized 401 response."""
    try:
        return jwt.decode(
            token,
            key=settings.JWT_SECRET,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
        db: Session = Depends(get_db),
        token: str = Depends(oauth2_scheme),
) -> User:
    """Dependency to retrieve the authenticated User instance."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_token_or_401(token)
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = crud.user.get(db, id=int(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_approved:
        raise HTTPException(status_code=403, detail="Account pending approval")

    return user


def get_system_or_user(
        auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
        db: Session = Depends(get_db)
) -> Union[User, dict]:
    """
    Hybrid dependency. Allows access to either:
    1. A valid User via JWT.
    2. The System Runner via the static EDGESTREAM_QUEUE_TOKEN.
    """
    if not auth:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Check for static system bypass
    if settings.EDGESTREAM_QUEUE_TOKEN and auth.credentials == settings.EDGESTREAM_QUEUE_TOKEN:
        return {"id": "system_runner", "role": "system"}

    return get_current_user(db=db, token=auth.credentials)


def authenticate(*, email: str, password: str, otp: Optional[str], db: Session) -> User:
    """Validates multi-factor credentials."""
    email_norm = (email or "").strip().lower()
    user = crud.user.get_by_email(db, email=email_norm)
    generic_error = "Invalid username, password, or authentication code."

    if not user or not verify_password(password or "", user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=generic_error)

    if user.otp_secret:
        if not otp or not verify_otp(user.otp_secret, otp):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=generic_error)

    return user


def change_user_password(
        *,
        db: Session,
        user: User,
        new_password: str,
        current_password: Optional[str] = None,
        is_admin_reset: bool = False
) -> User:
    """Updates password with salt/hash and logs the event."""
    if not is_admin_reset:
        if not current_password or not verify_password(current_password, user.hashed_password):
            Logger.logger.warning(f"Failed password change attempt for: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password verification failed."
            )

    user.hashed_password = hash_password(new_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    Logger.logger.info(f"Password updated: {user.email} (Reset: {is_admin_reset})")
    return user


def verify_otp(secret: str, otp: str) -> bool:
    """Validates TOTP token with a 30-second clock-drift window."""
    totp = pyotp.TOTP(secret)
    return totp.verify(otp, valid_window=1)
