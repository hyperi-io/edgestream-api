"""
Project:   edgestream-api
File:      edgestream/api/v1/endpoints/authentication.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Form, Request, BackgroundTasks, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from edgestream import crud
from edgestream.db.db import get_db
from edgestream.db.session import SessionLocal
from edgestream.services.auth.auth import authenticate, get_current_user
from edgestream.services.auth.security import create_access_token
from edgestream.services.background.audit_tasks import enqueue_audit
from edgestream.models.system.user import User
from edgestream.schemas.system.user import User as UserSchema, UserCreate
from edgestream.schemas.value.user_response import (
    SuccessLoginResponse,
    LoginBadRequestResponse,
    UnauthenticatedResponse,
    DuplicateUserResponse,
)

router = APIRouter()


def oauth_form_with_otp(
        form: OAuth2PasswordRequestForm = Depends(),
        otp: Optional[str] = Form(default=None),
):
    return form, otp


@router.post(
    "/login",
    responses={
        200: {"model": SuccessLoginResponse},
        401: {"model": UnauthenticatedResponse},  # Standardized from 404
        400: {"model": LoginBadRequestResponse},
    },
)
def login(
        request: Request,
        background: BackgroundTasks,
        db: Session = Depends(get_db),
        form_and_otp=Depends(oauth_form_with_otp),
) -> Any:
    form_data, otp = form_and_otp

    try:
        user = authenticate(
            email=form_data.username,
            password=form_data.password,
            otp=otp,
            db=db,
        )

        if not user:
            enqueue_audit(
                background, SessionLocal, request,
                event_type="login_failure", result="failure",
                actor_id=form_data.username, reason="bad_credentials",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email, password, or OTP."
            )

        # Success Logic
        token = create_access_token(subject=str(user.id))

        enqueue_audit(
            background, SessionLocal, request,
            event_type="login_success", result="success",
            actor_id=str(user.id), details={"email": user.email},
            status_code=status.HTTP_200_OK,
        )

        return {"access_token": token, "token_type": "bearer"}

    except HTTPException:
        raise
    except Exception as e:
        from edgestream.core.config import Logger
        Logger.logger.error(f"Login process failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during login.")


@router.get(
    "/whoami",
    responses={200: {"model": UserSchema}, 401: {"model": UnauthenticatedResponse}},
)
def whoami(
        request: Request,
        background: BackgroundTasks,
        current_user: User = Depends(get_current_user),
) -> Any:
    """Returns the current authenticated user's profile."""
    enqueue_audit(
        background, SessionLocal, request,
        event_type="auth_me_success", result="success",
        actor_id=str(current_user.id), status_code=status.HTTP_200_OK,
    )
    # Use Pydantic v2 model_validate
    return UserSchema.model_validate(current_user)


@router.post(
    "/signup",
    response_model=UserSchema,
    status_code=201,
    responses={400: {"model": DuplicateUserResponse}},
)
def create_user_signup(
        request: Request,
        background: BackgroundTasks,
        db: Session = Depends(get_db),
        user_in: UserCreate = Depends(),
) -> Any:
    """Public signup endpoint for new users."""
    try:
        # 2.0 Style Duplicate Check
        existing_user = db.execute(
            select(User).where(User.email == user_in.email)
        ).scalars().first()

        if existing_user:
            enqueue_audit(
                background, SessionLocal, request,
                event_type="signup_failure", result="failure",
                actor_id=user_in.email, reason="duplicate_email",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
            raise HTTPException(
                status_code=400,
                detail="A user with this email already exists."
            )

        # Create user via refactored CRUD
        user = crud.user.create(db=db, obj_in=user_in)

        enqueue_audit(
            background, SessionLocal, request,
            event_type="signup_success", result="success",
            actor_id=str(user.id), details={"email": user.email},
            status_code=status.HTTP_201_CREATED,
        )
        return user

    except HTTPException:
        raise
    except Exception as e:
        from edgestream.core.config import Logger
        Logger.logger.error(f"Signup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during registration.")
