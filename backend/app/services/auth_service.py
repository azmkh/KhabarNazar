from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate
from app.utils.security import get_password_hash, verify_password


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Finds a user by normalized email address."""
    normalized_email = email.strip().lower()
    return db.query(User).filter(User.email == normalized_email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Finds a user by primary key ID."""
    return db.query(User).filter(User.id == user_id).first()


def register_user(db: Session, user_in: UserCreate) -> User:
    """Registers a new user after verifying uniqueness and hashing password."""
    normalized_email = str(user_in.email).strip().lower()

    existing_user = get_user_by_email(db, normalized_email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        name=user_in.name.strip(),
        email=normalized_email,
        password_hash=hashed_pw,
        role="user",
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        # Two simultaneous registrations with the same email: the unique index wins.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )
    db.refresh(new_user)
    return new_user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticates credentials against stored password hash."""
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
