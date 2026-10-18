from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import authenticate_user, register_user
from app.utils.login_limiter import login_limiter
from app.utils.security import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """Creates a new user, hashes password, and returns a JWT access token with profile."""
    user = register_user(db, user_in)
    access_token = create_access_token(subject=user.id, role=user.role)
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate user and issue JWT token",
)
def login(credentials: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Verifies user credentials and issues a signed JWT access token.

    Repeated failures from the same client are refused with 429 for a while
    (see app/utils/login_limiter.py).
    """
    client = request.client.host if request.client else "unknown"
    account_key = f"account:{client}:{str(credentials.email).strip().lower()}"
    client_key = f"client:{client}"
    window = settings.LOGIN_LOCKOUT_MINUTES * 60

    wait = login_limiter.retry_after(
        {
            account_key: settings.LOGIN_MAX_FAILURES_PER_ACCOUNT,
            client_key: settings.LOGIN_MAX_FAILURES_PER_CLIENT,
        },
        window,
    )
    if wait is not None:
        minutes = max(1, -(-wait // 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed sign-in attempts. Please try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(wait)},
        )

    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        login_limiter.record_failure([account_key, client_key])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password entered.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    login_limiter.reset(account_key)
    access_token = create_access_token(subject=user.id, role=user.role)
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )
