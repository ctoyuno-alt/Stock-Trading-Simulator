"""
FastAPI Security & Authentication Dependencies.

Provides:
- User authentication via JWT Bearer Token (Authorization: Bearer <token>) or API Key (X-API-Key).
- Multi-role authorization checks (Admin, Trader, Viewer).
- Database session injection.
"""

from typing import List, Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import decode_access_token
from database.models import UserModel, UserRole
from database.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> UserModel:
    """
    Authenticates incoming request using either JWT Bearer token or API Key.
    Raises HTTP 401 if credentials are missing, invalid, or expired.
    """
    user: Optional[UserModel] = None

    # 1. Primary: Verify JWT Bearer Token
    if token:
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            try:
                user_id = int(payload["sub"])
                res = await db.execute(select(UserModel).where(UserModel.id == user_id, UserModel.is_active == True))
                user = res.scalar_one_or_none()
            except (ValueError, TypeError):
                user = None

    # 2. Secondary: Verify Programmatic API Key
    if user is None and x_api_key:
        res = await db.execute(select(UserModel).where(UserModel.api_key == x_api_key, UserModel.is_active == True))
        user = res.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token or X-API-Key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Optional[UserModel]:
    """Returns authenticated UserModel if valid credentials provided, else None."""
    try:
        return await get_current_user(token=token, x_api_key=x_api_key, db=db)
    except HTTPException:
        return None


def require_role(allowed_roles: List[UserRole]):
    """Enforces role-based authorization check."""
    async def role_checker(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {[r.value for r in allowed_roles]}.",
            )
        return current_user
    return role_checker
