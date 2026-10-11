from fastapi import APIRouter, Depends
from app.models.user import User
from app.schemas.user import UserResponse
from app.utils.dependencies import get_current_admin, get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the profile of the currently logged-in user."""
    return UserResponse.model_validate(current_user)


@router.get(
    "/admin-test",
    response_model=UserResponse,
    summary="Verify administrator authorization",
)
def test_admin_access(current_admin: User = Depends(get_current_admin)):
    """Demonstrates role-based authorization check: requires admin role."""
    return UserResponse.model_validate(current_admin)
