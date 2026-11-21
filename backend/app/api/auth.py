"""
Authentication and User Management API Routes.

Exposes:
- POST /api/v1/auth/register: User registration with auto-provisioned virtual trading account.
- POST /api/v1/auth/login: Credential verification and JWT access token issuance.
- GET  /api/v1/auth/me: Current authenticated user profile and account balances.
- POST /api/v1/auth/api-key: Programmatic API key generation / rotation.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.core.config import get_settings
from backend.app.core.security import (
    create_access_token,
    generate_api_key,
    hash_password,
    verify_password,
)
from database.models import AccountModel, UserModel, UserRole
from database.session import get_db

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, description="Unique username")
    email: str = Field(min_length=5, max_length=255, description="User email address")
    password: str = Field(min_length=6, max_length=128, description="User password")
    role: Optional[UserRole] = Field(default=UserRole.TRADER, description="User role")


class LoginRequest(BaseModel):
    username: str = Field(description="Username or email")
    password: str = Field(description="Password")


class UserProfileResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    api_key: Optional[str] = None
    accounts: List[Dict[str, Any]] = []


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Registers a new user and auto-provisions their dedicated INR virtual paper trading account."""
    clean_username = req.username.strip()
    clean_email = req.email.strip().lower()

    # Check if username or email already exists
    existing = await db.execute(
        select(UserModel).where(
            (UserModel.username == clean_username) | (UserModel.email == clean_email)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username or email already exists.",
        )

    # Hash password with PBKDF2
    hashed_pw, salt = hash_password(req.password)
    new_api_key = generate_api_key()

    new_user = UserModel(
        username=clean_username,
        email=clean_email,
        hashed_password=hashed_pw,
        salt=salt,
        role=req.role or UserRole.TRADER,
        is_active=True,
        api_key=new_api_key,
    )
    db.add(new_user)
    await db.flush()

    # Auto-provision dedicated INR virtual paper account (₹100,000)
    init_cap = settings.INITIAL_VIRTUAL_CAPITAL_INR
    user_account = AccountModel(
        user_id=new_user.id,
        account_name=f"{clean_username}'s Paper Account",
        initial_capital_inr=init_cap,
        cash_balance_inr=init_cap,
        equity_inr=init_cap,
        daily_starting_equity=init_cap,
        currency="INR",
        is_active=True,
    )
    db.add(user_account)
    await db.commit()
    await db.refresh(new_user)

    # Issue JWT Token
    token = create_access_token({"sub": str(new_user.id), "username": new_user.username, "role": new_user.role.value})
    logger.info(f"New user registered: {new_user.username} (ID: {new_user.id}, Role: {new_user.role})")

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "role": new_user.role.value,
            "is_active": new_user.is_active,
            "api_key": new_user.api_key,
            "accounts": [
                {
                    "id": user_account.id,
                    "account_name": user_account.account_name,
                    "equity": float(user_account.equity_inr),
                    "currency": user_account.currency,
                }
            ],
        },
    }


@router.post("/login", response_model=AuthTokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Authenticates credentials and issues a signed JWT access token."""
    login_id = req.username.strip()

    # Search by username or email
    res = await db.execute(
        select(UserModel).where(
            (UserModel.username == login_id) | (UserModel.email == login_id.lower())
        )
    )
    user = res.scalar_one_or_none()

    if user is None or not verify_password(req.password, user.salt, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated.")

    # Fetch user's linked accounts
    accts_res = await db.execute(select(AccountModel).where(AccountModel.user_id == user.id))
    user_accounts = accts_res.scalars().all()

    token = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role.value})
    logger.info(f"User logged in: {user.username} (ID: {user.id})")

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "api_key": user.api_key,
            "accounts": [
                {"id": a.id, "account_name": a.account_name, "equity": float(a.equity_inr), "currency": a.currency}
                for a in user_accounts
            ],
        },
    }


@router.get("/me", response_model=UserProfileResponse)
async def get_me(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Returns the authenticated user's profile and active trading accounts."""
    accts_res = await db.execute(select(AccountModel).where(AccountModel.user_id == current_user.id))
    user_accounts = accts_res.scalars().all()

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "api_key": current_user.api_key,
        "accounts": [
            {"id": a.id, "account_name": a.account_name, "equity": float(a.equity_inr), "currency": a.currency}
            for a in user_accounts
        ],
    }


@router.post("/api-key", response_model=Dict[str, str])
async def rotate_api_key(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    """Generates a new programmatic API key for the authenticated user."""
    new_key = generate_api_key()
    current_user.api_key = new_key
    await db.commit()
    logger.info(f"API key rotated for user {current_user.username}")
    return {"api_key": new_key, "message": "API key successfully rotated."}
