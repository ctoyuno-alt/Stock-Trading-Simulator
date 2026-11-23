"""
FastAPI Administrative Management API Router.

Provides privileged administrative control plane for:
- User directory listing with search, filtering, and pagination.
- Detailed user and portfolio inspection.
- Role-based access control (RBAC) role updates with self-lockout prevention.
- User status activation/deactivation with self-lockout prevention.
- Virtual capital injection and paper account balance reset.
- Account lifecycle management (archiving).
- API key rotation and revocation.
- Administrative audit log inspection and summary analytics.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    def Depends(f=None): return f
    def Query(default=None, **kwargs): return default
    class APIRouter:
        def __init__(self, *args, **kwargs):
            self.routes = []
        def get(self, *args, **kwargs): return lambda f: f
        def post(self, *args, **kwargs): return lambda f: f
        def put(self, *args, **kwargs): return lambda f: f
        def patch(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str = "", headers=None):
            self.status_code = status_code
            self.detail = detail
            self.headers = headers
            super().__init__(detail)
    class status:
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
        HTTP_404_NOT_FOUND = 404
        HTTP_500_INTERNAL_SERVER_ERROR = 500
    class Request:
        client = type("Client", (), {"host": "127.0.0.1"})()

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self):
            return self.__dict__
    def Field(*args, **kwargs): return kwargs.get("default", None)

try:
    from sqlalchemy import func, select, or_
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:
    class _MockStatement:
        def where(self, *a, **kw): return self
        def order_by(self, *a, **kw): return self
        def offset(self, *a, **kw): return self
        def limit(self, *a, **kw): return self
        def subquery(self, *a, **kw): return self
        def select_from(self, *a, **kw): return self
        def in_(self, *a, **kw): return self
        def like(self, *a, **kw): return self
        def desc(self): return self
        def asc(self): return self

    class _MockFunc:
        def count(self, *a, **kw): return _MockStatement()
        def sum(self, *a, **kw): return _MockStatement()
        def lower(self, *a, **kw): return _MockStatement()

    func = _MockFunc()
    def select(*a, **kw): return _MockStatement()
    def or_(*a, **kw): return _MockStatement()
    AsyncSession = Any  # type: ignore

from backend.app.api.deps import require_admin
from backend.app.core.security import (
    generate_api_key,
    generate_secure_random_password,
    hash_password,
)
from database.models import (
    AccountModel,
    AdminAuditLogModel,
    OrderModel,
    OrderStatus,
    PositionModel,
    PositionStatus,
    UserModel,
    UserRole,
)
try:
    from database.session import get_db
except ImportError:
    async def get_db():
        yield None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Management"])


# --- Request & Response Schemas ---

class RoleUpdateRequest(BaseModel):
    role: str = Field(description="Target role: admin, trader, or viewer")


class StatusUpdateRequest(BaseModel):
    is_active: bool = Field(description="Target active state")
    reason: Optional[str] = Field(default=None, description="Reason for status change")


class FundAccountRequest(BaseModel):
    amount: float = Field(gt=0, description="Virtual capital amount to inject")
    reason: Optional[str] = Field(default=None, description="Reason for funding")


class ResetAccountRequest(BaseModel):
    initial_capital: Optional[float] = Field(default=None, gt=0, description="New baseline capital")
    reason: Optional[str] = Field(default=None, description="Reason for reset")


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128, description="New password for user (minimum 8 chars)")
    reason: Optional[str] = Field(default="Administrative password reset", description="Reason for reset")



# --- Helper Functions ---

def _mask_api_key(key: Optional[str]) -> Optional[str]:
    """Returns masked representation of an API key."""
    if not key:
        return None
    if len(key) >= 16:
        return f"{key[:8]}...{key[-4:]}"
    return f"{key[:4]}..."


def _extract_ip(request: Optional[Request]) -> str:
    """Safely extracts client IP address from incoming request."""
    if request and hasattr(request, "client") and request.client:
        return getattr(request.client, "host", "127.0.0.1")
    return "127.0.0.1"


async def record_audit_log(
    db: AsyncSession,
    admin: UserModel,
    action: str,
    target_user_id: Optional[int] = None,
    target_account_id: Optional[int] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AdminAuditLogModel:
    """Persists an immutable record of an administrative action."""
    log_entry = AdminAuditLogModel(
        admin_id=admin.id,
        admin_username=admin.username,
        target_user_id=target_user_id,
        target_account_id=target_account_id,
        action=action,
        details=details,
        ip_address=ip_address,
    )
    if hasattr(db, "add"):
        res = db.add(log_entry)
        if asyncio.iscoroutine(res):
            await res
    try:
        await db.flush()
    except Exception as exc:
        logger.warning(f"Audit log flush failed: {exc}")
    return log_entry


# --- Administrative Endpoints ---

@router.get("/users")
async def list_users(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    role: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    List all users with pagination, role/status filtering, and search.
    Protected strictly by require_admin.
    """
    offset = (page - 1) * limit
    stmt = select(UserModel)

    if role:
        try:
            target_role = UserRole(role.lower())
            stmt = stmt.where(UserModel.role == target_role)
        except ValueError:
            pass

    if is_active is not None:
        stmt = stmt.where(UserModel.is_active == is_active)

    if search:
        search_pattern = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(UserModel.username).like(search_pattern),
                func.lower(UserModel.email).like(search_pattern),
            )
        )

    # Count query
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar_one_or_none() or 0

    # Paginated data query
    stmt = stmt.order_by(UserModel.id.asc()).offset(offset).limit(limit)
    res = await db.execute(stmt)
    users = res.scalars().all()

    users_data = []
    for u in users:
        # Fetch associated accounts summary
        acc_stmt = select(AccountModel).where(AccountModel.user_id == u.id)
        acc_res = await db.execute(acc_stmt)
        accounts = acc_res.scalars().all()

        total_equity_inr = sum(
            float(a.equity_inr) for a in accounts if a.currency == "INR" and a.is_active
        )
        total_equity_usd = sum(
            float(a.equity_inr) for a in accounts if a.currency == "USD" and a.is_active
        )

        role_val = u.role.value if hasattr(u.role, "value") else str(u.role)
        users_data.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": role_val,
            "is_active": u.is_active,
            "has_api_key": bool(u.api_key),
            "api_key_masked": _mask_api_key(u.api_key),
            "created_at": u.created_at.isoformat() if hasattr(u.created_at, "isoformat") else str(u.created_at),
            "accounts_count": len(accounts),
            "total_equity_inr": total_equity_inr,
            "total_equity_usd": total_equity_usd,
        })

    pages = max(1, (total + limit - 1) // limit)
    return {
        "users": users_data,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Inspect user details, linked accounts, open positions, and balances.
    """
    res = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    acc_res = await db.execute(select(AccountModel).where(AccountModel.user_id == user_id))
    accounts = acc_res.scalars().all()

    account_ids = [a.id for a in accounts]
    open_positions = []
    if account_ids:
        pos_res = await db.execute(
            select(PositionModel).where(
                PositionModel.account_id.in_(account_ids),
                PositionModel.status == PositionStatus.OPEN,
            )
        )
        positions = pos_res.scalars().all()
        for p in positions:
            open_positions.append({
                "id": p.id,
                "account_id": p.account_id,
                "symbol": p.symbol,
                "exchange": p.exchange,
                "quantity": p.quantity,
                "average_entry_price": float(p.average_entry_price),
                "current_price": float(p.current_price),
                "unrealized_pnl_inr": float(p.unrealized_pnl_inr),
                "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            })

    accounts_data = [
        {
            "id": a.id,
            "account_name": a.account_name,
            "currency": a.currency,
            "cash_balance": float(a.cash_balance_inr),
            "equity": float(a.equity_inr),
            "is_active": a.is_active,
            "circuit_breaker_tripped": a.circuit_breaker_tripped,
        }
        for a in accounts
    ]

    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": role_val,
            "is_active": user.is_active,
            "api_key_masked": _mask_api_key(user.api_key),
            "created_at": user.created_at.isoformat() if hasattr(user.created_at, "isoformat") else str(user.created_at),
        },
        "accounts": accounts_data,
        "positions_count": len(open_positions),
        "open_positions": open_positions,
    }


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    payload: RoleUpdateRequest,
    request: Request = None,
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Update a user's RBAC role. Enforces self-demotion prevention (HTTP 400).
    """
    try:
        new_role = UserRole(payload.role.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Must be one of: {[r.value for r in UserRole]}",
        )

    # Self-lockout check
    if user_id == current_admin.id and new_role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote your own administrator account. Assign another admin first.",
        )

    res = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    old_role = user.role.value if hasattr(user.role, "value") else str(user.role)
    user.role = new_role

    client_ip = _extract_ip(request)
    await record_audit_log(
        db=db,
        admin=current_admin,
        action="ROLE_UPDATE",
        target_user_id=user_id,
        details=f"Updated role from {old_role} to {new_role.value}",
        ip_address=client_ip,
    )
    await db.commit()

    return {
        "message": f"User role updated to {new_role.value}",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": new_role.value,
        },
    }


@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    payload: StatusUpdateRequest,
    request: Request = None,
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Activate or deactivate a user account. Enforces self-deactivation prevention (HTTP 400).
    """
    # Self-lockout check
    if user_id == current_admin.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own administrator account.",
        )

    res = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    user.is_active = payload.is_active

    client_ip = _extract_ip(request)
    action_text = "activated" if payload.is_active else "deactivated"
    reason_text = f" Reason: {payload.reason}" if payload.reason else ""
    await record_audit_log(
        db=db,
        admin=current_admin,
        action="STATUS_TOGGLE",
        target_user_id=user_id,
        details=f"User account {action_text}.{reason_text}",
        ip_address=client_ip,
    )
    await db.commit()

    return {
        "message": f"User account {action_text} successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "is_active": user.is_active,
        },
    }


@router.post("/accounts/{account_id}/fund")
async def fund_account(
    account_id: int,
    payload: FundAccountRequest,
    request: Request = None,
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Fund or adjust virtual paper trading capital for an account.
    """
    res = await db.execute(select(AccountModel).where(AccountModel.id == account_id))
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with ID {account_id} not found",
        )

    fund_delta = Decimal(str(payload.amount))
    account.cash_balance_inr = account.cash_balance_inr + fund_delta
    account.equity_inr = account.equity_inr + fund_delta

    client_ip = _extract_ip(request)
    reason_text = f" Reason: {payload.reason}" if payload.reason else ""
    await record_audit_log(
        db=db,
        admin=current_admin,
        action="CAPITAL_FUND",
        target_user_id=account.user_id,
        target_account_id=account.id,
        details=f"Injected {account.currency} {payload.amount:,.2f}.{reason_text}",
        ip_address=client_ip,
    )
    await db.commit()

    return {
        "message": f"Account funded with {account.currency} {payload.amount:,.2f}",
        "account": {
            "id": account.id,
            "cash_balance": float(account.cash_balance_inr),
            "equity": float(account.equity_inr),
            "currency": account.currency,
        },
    }


@router.post("/accounts/{account_id}/reset")
async def reset_account(
    account_id: int,
    payload: Optional[ResetAccountRequest] = None,
    request: Request = None,
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Reset account balance to initial baseline and close all open positions.
    """
    res = await db.execute(select(AccountModel).where(AccountModel.id == account_id))
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with ID {account_id} not found",
        )

    # 1. Close open positions
    pos_res = await db.execute(
        select(PositionModel).where(
            PositionModel.account_id == account_id,
            PositionModel.status == PositionStatus.OPEN,
        )
    )
    positions = pos_res.scalars().all()
    now_utc = datetime.now(timezone.utc)
    for p in positions:
        p.status = PositionStatus.CLOSED
        p.closed_at = now_utc

    # 2. Cancel pending orders
    ord_res = await db.execute(
        select(OrderModel).where(
            OrderModel.account_id == account_id,
            OrderModel.status == OrderStatus.PENDING,
        )
    )
    orders = ord_res.scalars().all()
    for o in orders:
        o.status = OrderStatus.CANCELLED

    # 3. Reset balances
    new_balance = (
        Decimal(str(payload.initial_capital))
        if payload and payload.initial_capital
        else account.initial_capital_inr
    )
    account.cash_balance_inr = new_balance
    account.equity_inr = new_balance
    account.daily_starting_equity = new_balance
    account.circuit_breaker_tripped = False
    account.circuit_breaker_reason = None

    client_ip = _extract_ip(request)
    reason_text = f" Reason: {payload.reason}" if payload and payload.reason else ""
    await record_audit_log(
        db=db,
        admin=current_admin,
        action="CAPITAL_RESET",
        target_user_id=account.user_id,
        target_account_id=account.id,
        details=f"Account balance reset to {account.currency} {float(new_balance):,.2f}. Closed {len(positions)} positions.{reason_text}",
        ip_address=client_ip,
    )
    await db.commit()

    return {
        "message": f"Account reset to {account.currency} {float(new_balance):,.2f}",
        "account": {
            "id": account.id,
            "cash_balance": float(account.cash_balance_inr),
            "equity": float(account.equity_inr),
            "currency": account.currency,
        },
    }


@router.delete("/accounts/{account_id}")
async def archive_account(
    account_id: int,
    request: Request = None,
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Archive a paper trading account (soft deletion, is_active=False).
    """
    res = await db.execute(select(AccountModel).where(AccountModel.id == account_id))
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with ID {account_id} not found",
        )

    account.is_active = False

    client_ip = _extract_ip(request)
    await record_audit_log(
        db=db,
        admin=current_admin,
        action="ACCOUNT_ARCHIVE",
        target_user_id=account.user_id,
        target_account_id=account.id,
        details=f"Account '{account.account_name}' (ID: {account_id}) archived.",
        ip_address=client_ip,
    )
    await db.commit()

    return {
        "message": f"Account {account_id} archived successfully",
        "account_id": account_id,
    }


@router.post("/users/{user_id}/api-key/rotate")
async def rotate_user_api_key(
    user_id: int,
    request: Request = None,
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Generate and assign a fresh programmatic API key for a user.
    """
    res = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    new_api_key = generate_api_key()
    user.api_key = new_api_key

    client_ip = _extract_ip(request)
    await record_audit_log(
        db=db,
        admin=current_admin,
        action="API_KEY_ROTATE",
        target_user_id=user_id,
        details="Generated fresh programmatic API key",
        ip_address=client_ip,
    )
    await db.commit()

    return {
        "message": "API key rotated successfully",
        "api_key": new_api_key,
    }


@router.post("/users/{user_id}/api-key/revoke")
async def revoke_user_api_key(
    user_id: int,
    request: Request = None,
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Revoke a user's programmatic API key (sets to None).
    """
    res = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    user.api_key = None

    client_ip = _extract_ip(request)
    await record_audit_log(
        db=db,
        admin=current_admin,
        action="API_KEY_REVOKE",
        target_user_id=user_id,
        details="API key revoked",
        ip_address=client_ip,
    )
    await db.commit()

    return {
        "message": "API key revoked successfully",
        "revoked": True,
    }


@router.put("/users/{user_id}/password")
async def admin_reset_user_password(
    user_id: int,
    payload: AdminResetPasswordRequest,
    request: Request = None,
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Administratively resets a user's password.
    Requires require_admin.
    Re-hashes password with fresh PBKDF2-HMAC-SHA256 salt.
    Persists immutable audit log entry.
    """
    res = await db.execute(select(UserModel).where(UserModel.id == user_id))
    target_user = res.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    new_hash, new_salt = hash_password(payload.new_password)
    target_user.hashed_password = new_hash
    target_user.salt = new_salt

    client_ip = _extract_ip(request)
    audit_detail = f"Admin '{current_admin.username}' reset password for user '{target_user.username}' (ID: {user_id}). Reason: {payload.reason or 'None'}"
    await record_audit_log(
        db=db,
        admin=current_admin,
        action="USER_PASSWORD_RESET",
        target_user_id=user_id,
        details=audit_detail,
        ip_address=client_ip,
    )
    await db.commit()
    logger.info(audit_detail)

    return {
        "status": "success",
        "message": f"Password for user '{target_user.username}' has been successfully reset.",
        "user_id": user_id,
        "username": target_user.username,
    }



@router.get("/audit-logs")
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    action: Optional[str] = Query(default=None),
    target_user_id: Optional[int] = Query(default=None),
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Retrieve historical administrative audit trail entries.
    """
    offset = (page - 1) * limit
    stmt = select(AdminAuditLogModel)

    if action:
        stmt = stmt.where(AdminAuditLogModel.action == action.upper())

    if target_user_id is not None:
        stmt = stmt.where(AdminAuditLogModel.target_user_id == target_user_id)

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar_one_or_none() or 0

    # Paginated data ordered latest first
    stmt = stmt.order_by(AdminAuditLogModel.timestamp.desc()).offset(offset).limit(limit)
    res = await db.execute(stmt)
    logs = res.scalars().all()

    logs_data = []
    for l in logs:
        ts_str = l.timestamp.isoformat() if hasattr(l.timestamp, "isoformat") else str(l.timestamp)
        logs_data.append({
            "id": l.id,
            "timestamp": ts_str,
            "admin_id": l.admin_id,
            "admin_username": l.admin_username,
            "target_user_id": l.target_user_id,
            "target_account_id": l.target_account_id,
            "action": l.action,
            "details": l.details,
            "ip_address": l.ip_address,
        })

    return {
        "logs": logs_data,
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/summary")
async def get_admin_summary(
    current_admin: UserModel = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Summary metrics for Admin Dashboard KPI cards:
    - total_users, active_users, active_accounts, total_capital_inr, total_capital_usd, audit_events_count.
    """
    # Total users
    u_tot_res = await db.execute(select(func.count(UserModel.id)))
    total_users = u_tot_res.scalar_one_or_none() or 0

    # Active users
    u_act_res = await db.execute(select(func.count(UserModel.id)).where(UserModel.is_active == True))
    active_users = u_act_res.scalar_one_or_none() or 0

    # Active accounts
    a_act_res = await db.execute(select(func.count(AccountModel.id)).where(AccountModel.is_active == True))
    active_accounts = a_act_res.scalar_one_or_none() or 0

    # INR Capital
    inr_res = await db.execute(
        select(func.sum(AccountModel.equity_inr)).where(
            AccountModel.currency == "INR",
            AccountModel.is_active == True,
        )
    )
    total_capital_inr = float(inr_res.scalar_one_or_none() or 0.0)

    # USD Capital
    usd_res = await db.execute(
        select(func.sum(AccountModel.equity_inr)).where(
            AccountModel.currency == "USD",
            AccountModel.is_active == True,
        )
    )
    total_capital_usd = float(usd_res.scalar_one_or_none() or 0.0)

    # Audit count
    aud_res = await db.execute(select(func.count(AdminAuditLogModel.id)))
    audit_events_count = aud_res.scalar_one_or_none() or 0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "active_accounts": active_accounts,
        "total_capital_inr": total_capital_inr,
        "total_capital_usd": total_capital_usd,
        "audit_events_count": audit_events_count,
    }
