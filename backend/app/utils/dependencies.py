from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_id
from app.utils.security import decode_access_token

# Swagger shows an "Authorize" box where the access_token from /auth/login is pasted.
bearer_scheme = HTTPBearer(auto_error=False, description="Paste the access_token returned by /auth/login")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Dependency that extracts, decodes, and validates JWT token to fetch the current user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise credentials_exception

    # Tokens are issued with the user ID as subject. The role is always read
    # from the database, so a demoted admin loses access immediately.
    subject = str(payload.get("sub") or "")
    if not subject.isdigit():
        raise credentials_exception

    user = get_user_by_id(db, int(subject))
    if user is None:
        raise credentials_exception

    return user


def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency enforcing administrator role authorization."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: administrator privileges required.",
        )
    return current_user
