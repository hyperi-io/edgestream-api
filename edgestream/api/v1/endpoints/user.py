"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/user.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import Any, Dict, List
import socket
import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.core.config import Logger
from edgestream.db.db import get_db
from edgestream.models.system.user import User
from edgestream.schemas.system.user import (
    GetUser,
    UserCreate,
    UserGenOtpRequest,
    UserGenOtpResponse,
    UserValidateOtpRequest,
    UserPasswordUpdate,
    UserUpdateRequest,
    UserDeleteRequest,
    UserCreateFromUI,
)
from edgestream.services.auth.auth import verify_otp, get_current_user, change_user_password

router = APIRouter()


# -------------------------------------------------------------------
# Security Helpers
# -------------------------------------------------------------------

def ensure_admin(current_user: User):
    """Gaurdrail to restrict endpoints to superusers."""
    if not current_user.is_superuser:
        Logger.logger.warning(f"Unauthorized admin access attempt by {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required."
        )


def _is_last_superuser(db: Session, user_id: int) -> bool:
    """Safety check to prevent locking everyone out of the system."""
    user = crud.user.get(db, id=user_id)

    # If the user doesn't exist or is already disabled, they aren't the last active account
    if not user or not user.is_approved:
        return False

    # Count how many total accounts are currently enabled
    total_enabled = db.execute(
        select(func.count(User.id)).where(User.is_approved.is_(True))
    ).scalar() or 0

    # If 1 or fewer enabled accounts exist, and this user is enabled, they are the last one
    return total_enabled <= 1


# -------------------------------------------------------------------
# Multi-Factor Authentication (MFA/OTP)
# -------------------------------------------------------------------

@router.post("/otp/generate", response_model=UserGenOtpResponse)
def generate_otp(
        *,
        user_in: UserGenOtpRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Generate a new TOTP secret and provisioning URI for a user (Admin Only).
    """
    ensure_admin(current_user)

    user = crud.user.get_by_email(db=db, email=user_in.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    otp_secret = pyotp.random_base32()
    otp_url = pyotp.totp.TOTP(otp_secret).provisioning_uri(
        name=user_in.email,
        issuer_name=f"{socket.getfqdn()}@edgestream"
    )

    return {"email": user_in.email, "otp_secret": otp_secret, "otp_url": otp_url}


@router.post("/otp/validate", response_model=Dict[str, Any])
def validate_otp(
        *,
        otp_in: UserValidateOtpRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Validate a generated OTP secret against a user-provided value (Admin Only).
    Useful for testing MFA setup before saving.
    """
    ensure_admin(current_user)

    if not otp_in.otp_secret or not otp_in.otp_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OTP secret or token value")

    try:
        otp_valid = verify_otp(otp_in.otp_secret, otp_in.otp_value)
        return {
            "email": otp_in.email,
            "otp_secret": otp_in.otp_secret,
            "otp_valid": otp_valid,
        }
    except Exception as e:
        Logger.logger.error(f"OTP validation crash: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error during OTP validation.")


# -------------------------------------------------------------------
# User Management
# -------------------------------------------------------------------

@router.get("", response_model=Dict[str, List[GetUser]])
def get_all_users(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """Fetch all users in the system (Admin Only)."""
    ensure_admin(current_user)
    users = crud.user.get_all(db)
    return {"users": [crud.user._to_get_user(u) for u in users]}


@router.get("/pending", response_model=Dict[str, List[GetUser]])
def get_pending_users(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """Fetch users awaiting approval (Admin Only)."""
    ensure_admin(current_user)
    users = crud.user.get_all_pending_users(db)
    return {"users": [crud.user._to_get_user(u) for u in users]}


@router.post("", response_model=GetUser, status_code=status.HTTP_201_CREATED)
def create_user(
        *,
        user_in: UserCreateFromUI,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> GetUser:
    """
    Manually create a new user account (Admin Only).
    """
    ensure_admin(current_user)

    # Check for duplicate email before proceeding
    if crud.user.get_by_email(db, email=user_in.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A user with this email already exists.")

    to_create = UserCreate(
        email=user_in.email,
        full_name=user_in.full_name,
        display_name=user_in.display_name,
        password=user_in.password,
        is_superuser=user_in.is_superuser,
        is_approved=user_in.enabled,
        otp_secret=None,
    )

    created = crud.user.create(db=db, obj_in=to_create)
    return crud.user._to_get_user(created)


@router.put("", response_model=GetUser)
def update_user(
        *,
        req: UserUpdateRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> GetUser:
    """
    Update user metadata, permissions, or MFA state (Admin Only).
    """
    ensure_admin(current_user)

    target = crud.user.get_by_email(db=db, email=req.email)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if req.is_superuser is False and target.is_superuser:
        if _is_last_superuser(db, target.id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot demote the last remaining superuser.")

    update_data = req.model_dump(exclude_unset=True)
    update_data.pop("email", None)  # Email is our unique identifier; cannot be changed here

    if update_data.get("otp_secret") == "":
        update_data["otp_secret"] = None

    updated = crud.user.update(db=db, db_obj=target, obj_in=update_data)
    return crud.user._to_get_user(updated)


@router.delete("", response_model=Dict[str, str])
def delete_user(
        *,
        req: UserDeleteRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> dict:
    """
    Permanently delete a user account (Admin Only).
    """
    ensure_admin(current_user)

    user_to_delete = crud.user.get_by_email(db=db, email=req.email)
    if not user_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user_to_delete.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account.")

    if _is_last_superuser(db, user_to_delete.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the last remaining superuser.")

    crud.user.remove(db=db, id=user_to_delete.id)
    return {"result": f"User '{req.email}' successfully deleted"}


# -------------------------------------------------------------------
# Self-Service Password
# -------------------------------------------------------------------

@router.put("/password", response_model=Dict[str, str])
def update_password(
        request: UserPasswordUpdate,
        db: Session = Depends(get_db),
        logged_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Updates a user's password.
    Users can change their own (requires old password).
    Admins can reset any account (old password bypassed).
    """
    target_user = crud.user.get_by_email(db, email=request.email)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    is_admin = logged_user.is_superuser
    is_self = logged_user.email.lower() == request.email.lower()

    if not (is_admin or is_self):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    try:
        change_user_password(
            db=db,
            user=target_user,
            new_password=request.new_password,
            current_password=request.current_password,
            is_admin_reset=is_admin
        )
        return {"result": "Password successfully updated"}
    except HTTPException:
        raise
    except Exception as e:
        Logger.logger.error(f"Password update failure: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error updating password.")
