from typing import Any, Dict, Optional, Union, List

from fastapi import HTTPException, status
from sqlalchemy import func, select, asc
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from edgestream.crud.base import CRUDBase
from edgestream.models.system.user import User
from edgestream.schemas.system.user import UserCreate, UserUpdate, GetUser
from edgestream.services.auth.security import hash_password


def _norm_email(value: Optional[str]) -> str:
    """Normalize email for consistent lookup."""
    return (value or "").strip().lower()


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """
    CRUD operations for User accounts.
    Now simplified: All users in the table are standard managed accounts.
    """

    def export(self, db: Session) -> List[Dict[str, Any]]:
        """
        Unified export method for configuration synchronization.
        SENSITIVE DATA FILTER: Excludes hashed_password and otp_secret.
        """
        rows = db.execute(
            select(User).order_by(asc(User.created_at))
        ).scalars().all()

        return [
            {
                "email": r.email,
                "full_name": r.full_name,
                "display_name": r.display_name,
                "is_superuser": bool(r.is_superuser),
                "is_approved": bool(r.is_approved),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        """Retrieve a user by email using case-insensitive comparison."""
        email = _norm_email(email)
        return db.execute(
            select(User).where(func.lower(User.email) == email)
        ).scalar_one_or_none()

    def get_all(self, db: Session) -> List[GetUser]:
        """Retrieve all registered users."""
        rows = db.execute(
            select(User).order_by(asc(User.created_at))
        ).scalars().all()

        return [self._to_get_user(row) for row in rows]

    def get_all_approved_users(self, db: Session) -> List[GetUser]:
        """Retrieve only users with approved status."""
        rows = db.execute(
            select(User)
            .where(User.is_approved.is_(True))
            .order_by(asc(User.created_at))
        ).scalars().all()
        return [self._to_get_user(row) for row in rows]

    def get_all_pending_users(self, db: Session) -> List[GetUser]:
        """Retrieve users awaiting approval."""
        rows = db.execute(
            select(User)
            .where(User.is_approved.is_(False))
            .order_by(asc(User.created_at))
        ).scalars().all()
        return [self._to_get_user(row) for row in rows]


    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        """Create a new user with hashed password."""
        email = _norm_email(obj_in.email)

        if self.get_by_email(db, email=email):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        is_approved = getattr(obj_in, "is_approved", getattr(obj_in, "enabled", False))

        db_obj = User(
            email=email,
            hashed_password=hash_password(obj_in.password),
            full_name=obj_in.full_name,
            display_name=obj_in.display_name,
            is_superuser=bool(obj_in.is_superuser),
            is_approved=bool(is_approved),
            otp_secret=obj_in.otp_secret
        )

        try:
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists or data integrity error.")

    def update(
            self,
            db: Session,
            *,
            db_obj: User,
            obj_in: Union[UserUpdate, Dict[str, Any]],
    ) -> User:
        """Update user data including optional password hashing."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        if "email" in update_data:
            update_data["email"] = _norm_email(update_data["email"])
            if update_data["email"] != db_obj.email:
                if self.get_by_email(db, email=update_data["email"]):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        if "password" in update_data and update_data["password"]:
            db_obj.hashed_password = hash_password(update_data.pop("password"))

        if "enabled" in update_data:
            update_data["is_approved"] = bool(update_data.pop("enabled"))

        return super().update(db, db_obj=db_obj, obj_in=update_data)

    @staticmethod
    def _to_get_user(u: User) -> GetUser:
        """Transform model to schema."""
        return GetUser(
            id=u.id,
            full_name=u.full_name,
            display_name=u.display_name,
            email=u.email,
            is_superuser=u.is_superuser,
            is_approved=u.is_approved,
            otp_secret=u.otp_secret,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )


user = CRUDUser(User)
