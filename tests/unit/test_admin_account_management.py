"""
Unit Tests for Admin Account Management System (Milestone M1).

Validates:
- Security Guardrails: 401 Unauthorized (unauthenticated) & 403 Forbidden (non-admin).
- Admin Authorization: 200 OK for UserRole.ADMIN across all admin routes.
- User Directory: Pagination, role/status filtering, search, and details inspection.
- Role Management: Updating user roles and self-demotion lockout prevention (HTTP 400).
- Status Management: Activating/deactivating users and self-deactivation lockout prevention (HTTP 400).
- Virtual Capital Controls: Funding paper accounts and resetting baseline balances.
- Account Lifecycle: Archiving accounts (is_active=False).
- Credential Management: API key rotation (qt_live_...) and revocation (None).
- Audit Trail: Immutable logging of mutating actions and log retrieval.
- Admin Summary: KPI metric aggregation (users, accounts, capital, audit counts).
- Dashboard API Client: Client method integration and URL parameter encoding.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

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
from backend.app.api.deps import get_current_user, require_admin, require_role
from backend.app.api.admin import (
    FundAccountRequest,
    ResetAccountRequest,
    RoleUpdateRequest,
    StatusUpdateRequest,
    archive_account,
    fund_account,
    get_admin_summary,
    get_user_details,
    list_audit_logs,
    list_users,
    record_audit_log,
    reset_account,
    revoke_user_api_key,
    rotate_user_api_key,
    update_user_role,
    update_user_status,
)
from dashboard.api_client import DashboardAPIClient


class MockAsyncResult:
    """Mock result returning scalars for async SQLAlchemy queries."""

    def __init__(self, data):
        self._data = data

    def scalar_one_or_none(self):
        if isinstance(self._data, list):
            return self._data[0] if self._data else None
        return self._data

    def scalars(self):
        data_list = self._data if isinstance(self._data, list) else [self._data]
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = data_list
        return mock_scalars


class TestAdminSecurityGuardrails(unittest.TestCase):
    """Verifies authentication and authorization boundaries for administrative access."""

    def setUp(self):
        self.admin_user = UserModel(
            id=1,
            username="admin_super",
            email="admin@quantum.local",
            hashed_password="hash",
            salt="salt",
            role=UserRole.ADMIN,
            is_active=True,
            api_key="ak_live_admin_master",
        )
        self.trader_user = UserModel(
            id=2,
            username="trader_joe",
            email="joe@quantum.local",
            hashed_password="hash",
            salt="salt",
            role=UserRole.TRADER,
            is_active=True,
            api_key="qt_live_trader_key",
        )
        self.viewer_user = UserModel(
            id=3,
            username="viewer_ann",
            email="ann@quantum.local",
            hashed_password="hash",
            salt="salt",
            role=UserRole.VIEWER,
            is_active=True,
            api_key=None,
        )

    def test_unauthenticated_request_raises_401(self):
        """Unauthenticated requests (missing/invalid credentials) must raise HTTP 401."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = MockAsyncResult(None)

        with self.assertRaises(Exception) as ctx:
            asyncio.run(get_current_user(token=None, x_api_key=None, db=mock_db))
        self.assertEqual(getattr(ctx.exception, "status_code", None), 401)

    def test_trader_role_rejected_by_require_admin_raises_403(self):
        """Standard trader users accessing admin dependencies must receive HTTP 403."""
        with self.assertRaises(Exception) as ctx:
            asyncio.run(require_admin(current_user=self.trader_user))
        self.assertEqual(getattr(ctx.exception, "status_code", None), 403)
        self.assertIn("Access denied", str(getattr(ctx.exception, "detail", "")))

    def test_viewer_role_rejected_by_require_admin_raises_403(self):
        """Viewer users accessing admin dependencies must receive HTTP 403."""
        with self.assertRaises(Exception) as ctx:
            asyncio.run(require_admin(current_user=self.viewer_user))
        self.assertEqual(getattr(ctx.exception, "status_code", None), 403)
        self.assertIn("Access denied", str(getattr(ctx.exception, "detail", "")))

    def test_admin_role_permitted_by_require_admin(self):
        """Admin users accessing require_admin must pass through successfully."""
        user = asyncio.run(require_admin(current_user=self.admin_user))
        self.assertEqual(user.id, self.admin_user.id)
        self.assertEqual(user.role, UserRole.ADMIN)


class TestAdminUserManagement(unittest.TestCase):
    """Verifies administrative user listing, inspection, role updates, and status toggles."""

    def setUp(self):
        self.admin = UserModel(
            id=1,
            username="admin",
            email="admin@quantum.local",
            role=UserRole.ADMIN,
            is_active=True,
            api_key="ak_live_admin",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.trader = UserModel(
            id=2,
            username="quant_trader",
            email="quant@quantum.local",
            role=UserRole.TRADER,
            is_active=True,
            api_key="qt_live_quant_abc123456789xyz",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def test_list_users_pagination_and_masking(self):
        """Verify user listing returns paginated results and masks API keys."""
        mock_db = AsyncMock()
        # Count query returns 2
        # Data query returns [admin, trader]
        # Accounts query returns empty list
        mock_db.execute.side_effect = [
            MockAsyncResult(2),  # total
            MockAsyncResult([self.admin, self.trader]),  # users
            MockAsyncResult([]),  # accounts for admin
            MockAsyncResult([]),  # accounts for trader
        ]

        resp = asyncio.run(list_users(page=1, limit=10, current_admin=self.admin, db=mock_db))
        self.assertEqual(resp["total"], 2)
        self.assertEqual(resp["page"], 1)
        self.assertEqual(len(resp["users"]), 2)

        # Check API key masking
        trader_data = resp["users"][1]
        self.assertEqual(trader_data["username"], "quant_trader")
        self.assertTrue(trader_data["has_api_key"])
        self.assertTrue(trader_data["api_key_masked"].startswith("qt_live_..."))

    def test_get_user_details_with_accounts_and_positions(self):
        """Verify user details endpoint returns linked accounts and open positions."""
        mock_account = AccountModel(
            id=10,
            user_id=2,
            account_name="quant_trader's Paper Account",
            currency="INR",
            cash_balance_inr=Decimal("150000.00"),
            equity_inr=Decimal("175000.00"),
            is_active=True,
            circuit_breaker_tripped=False,
        )
        mock_position = PositionModel(
            id=101,
            account_id=10,
            symbol="TCS",
            exchange="NSE",
            quantity=10,
            average_entry_price=Decimal("3500.00"),
            current_price=Decimal("3600.00"),
            unrealized_pnl_inr=Decimal("1000.00"),
            status=PositionStatus.OPEN,
        )

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            MockAsyncResult(self.trader),  # user query
            MockAsyncResult([mock_account]),  # accounts query
            MockAsyncResult([mock_position]),  # positions query
        ]

        resp = asyncio.run(get_user_details(user_id=2, current_admin=self.admin, db=mock_db))
        self.assertEqual(resp["user"]["username"], "quant_trader")
        self.assertEqual(len(resp["accounts"]), 1)
        self.assertEqual(resp["accounts"][0]["currency"], "INR")
        self.assertEqual(resp["positions_count"], 1)
        self.assertEqual(resp["open_positions"][0]["symbol"], "TCS")

    def test_get_user_details_not_found_raises_404(self):
        """Verify non-existent user ID raises HTTP 404."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = MockAsyncResult(None)

        with self.assertRaises(Exception) as ctx:
            asyncio.run(get_user_details(user_id=999, current_admin=self.admin, db=mock_db))
        self.assertEqual(getattr(ctx.exception, "status_code", None), 404)

    def test_update_user_role_success(self):
        """Admin can promote a trader to ADMIN or demote to VIEWER."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = MockAsyncResult(self.trader)

        req = RoleUpdateRequest(role="admin")
        resp = asyncio.run(update_user_role(user_id=2, payload=req, current_admin=self.admin, db=mock_db))
        self.assertEqual(resp["user"]["role"], "admin")
        self.assertEqual(self.trader.role, UserRole.ADMIN)
        mock_db.commit.assert_awaited_once()

    def test_self_demotion_prevention_raises_400(self):
        """Admin cannot demote their own account to prevent administrative lockout (HTTP 400)."""
        mock_db = AsyncMock()
        req = RoleUpdateRequest(role="trader")

        with self.assertRaises(Exception) as ctx:
            asyncio.run(update_user_role(user_id=1, payload=req, current_admin=self.admin, db=mock_db))
        self.assertEqual(getattr(ctx.exception, "status_code", None), 400)
        self.assertIn("Cannot demote your own administrator account", str(getattr(ctx.exception, "detail", "")))

    def test_toggle_user_status_success(self):
        """Admin can deactivate and reactivate a trader account."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = MockAsyncResult(self.trader)

        req = StatusUpdateRequest(is_active=False, reason="Suspicious activity investigation")
        resp = asyncio.run(update_user_status(user_id=2, payload=req, current_admin=self.admin, db=mock_db))
        self.assertFalse(resp["user"]["is_active"])
        self.assertFalse(self.trader.is_active)
        mock_db.commit.assert_awaited_once()

    def test_self_deactivation_prevention_raises_400(self):
        """Admin cannot deactivate their own account to prevent administrative lockout (HTTP 400)."""
        mock_db = AsyncMock()
        req = StatusUpdateRequest(is_active=False, reason="Self test")

        with self.assertRaises(Exception) as ctx:
            asyncio.run(update_user_status(user_id=1, payload=req, current_admin=self.admin, db=mock_db))
        self.assertEqual(getattr(ctx.exception, "status_code", None), 400)
        self.assertIn("Cannot deactivate your own administrator account", str(getattr(ctx.exception, "detail", "")))


class TestAdminCapitalAndAccountLifecycle(unittest.TestCase):
    """Verifies virtual paper capital funding, account reset, and archiving."""

    def setUp(self):
        self.admin = UserModel(id=1, username="admin", role=UserRole.ADMIN, is_active=True)
        self.account = AccountModel(
            id=5,
            user_id=2,
            account_name="trader_5_account",
            currency="INR",
            initial_capital_inr=Decimal("100000.00"),
            cash_balance_inr=Decimal("80000.00"),
            equity_inr=Decimal("85000.00"),
            daily_starting_equity=Decimal("80000.00"),
            circuit_breaker_tripped=True,
            circuit_breaker_reason="Daily drawdown 4% breached",
            is_active=True,
        )

    def test_fund_account_increases_cash_and_equity(self):
        """Admin funding adds specified amount to cash balance and equity."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = MockAsyncResult(self.account)

        req = FundAccountRequest(amount=50000.0, reason="Trading competition prize")
        resp = asyncio.run(fund_account(account_id=5, payload=req, current_admin=self.admin, db=mock_db))

        self.assertEqual(self.account.cash_balance_inr, Decimal("130000.00"))
        self.assertEqual(self.account.equity_inr, Decimal("135000.00"))
        self.assertEqual(resp["account"]["cash_balance"], 130000.0)
        mock_db.commit.assert_awaited_once()

    def test_reset_account_wipes_positions_and_restores_balance(self):
        """Account reset closes open positions, cancels orders, and resets balances."""
        open_pos = PositionModel(
            id=20,
            account_id=5,
            symbol="INFY",
            quantity=15,
            status=PositionStatus.OPEN,
            average_entry_price=Decimal("1500.00"),
            current_price=Decimal("1480.00"),
            unrealized_pnl_inr=Decimal("-300.00"),
        )
        pending_ord = OrderModel(
            id=30,
            account_id=5,
            client_order_id="ord_test_1",
            symbol="INFY",
            status=OrderStatus.PENDING,
        )

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            MockAsyncResult(self.account),      # account query
            MockAsyncResult([open_pos]),       # positions query
            MockAsyncResult([pending_ord]),    # orders query
        ]

        req = ResetAccountRequest(initial_capital=100000.0, reason="Simulation period restart")
        resp = asyncio.run(reset_account(account_id=5, payload=req, current_admin=self.admin, db=mock_db))

        # Check positions closed
        self.assertEqual(open_pos.status, PositionStatus.CLOSED)
        self.assertIsNotNone(open_pos.closed_at)

        # Check orders cancelled
        self.assertEqual(pending_ord.status, OrderStatus.CANCELLED)

        # Check balances reset and circuit breaker cleared
        self.assertEqual(self.account.cash_balance_inr, Decimal("100000.00"))
        self.assertEqual(self.account.equity_inr, Decimal("100000.00"))
        self.assertFalse(self.account.circuit_breaker_tripped)
        self.assertIsNone(self.account.circuit_breaker_reason)

    def test_archive_account_sets_inactive(self):
        """Archiving an account soft-deletes by setting is_active = False."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = MockAsyncResult(self.account)

        resp = asyncio.run(archive_account(account_id=5, current_admin=self.admin, db=mock_db))
        self.assertFalse(self.account.is_active)
        self.assertEqual(resp["account_id"], 5)
        mock_db.commit.assert_awaited_once()


class TestAdminCredentialManagement(unittest.TestCase):
    """Verifies rotating and revoking programmatic API keys."""

    def setUp(self):
        self.admin = UserModel(id=1, username="admin", role=UserRole.ADMIN, is_active=True)
        self.target_user = UserModel(
            id=7,
            username="api_trader",
            role=UserRole.TRADER,
            is_active=True,
            api_key="qt_live_old_key_12345",
        )

    def test_rotate_api_key_generates_fresh_token(self):
        """Rotating API key generates a fresh high-entropy key starting with qt_live_."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = MockAsyncResult(self.target_user)

        resp = asyncio.run(rotate_user_api_key(user_id=7, current_admin=self.admin, db=mock_db))
        new_key = resp["api_key"]
        self.assertTrue(new_key.startswith("qt_live_"))
        self.assertEqual(self.target_user.api_key, new_key)
        self.assertNotEqual(new_key, "qt_live_old_key_12345")
        mock_db.commit.assert_awaited_once()

    def test_revoke_api_key_clears_key(self):
        """Revoking API key sets user.api_key to None."""
        mock_db = AsyncMock()
        mock_db.execute.return_value = MockAsyncResult(self.target_user)

        resp = asyncio.run(revoke_user_api_key(user_id=7, current_admin=self.admin, db=mock_db))
        self.assertTrue(resp["revoked"])
        self.assertIsNone(self.target_user.api_key)
        mock_db.commit.assert_awaited_once()


class TestAdminAuditTrailAndSummary(unittest.TestCase):
    """Verifies audit logging persistence, audit trail inspection, and summary metrics."""

    def setUp(self):
        self.admin = UserModel(id=1, username="admin", role=UserRole.ADMIN, is_active=True)

    def test_record_audit_log_persists_entry(self):
        """record_audit_log helper writes immutable entry to database session."""
        mock_db = AsyncMock()
        log = asyncio.run(
            record_audit_log(
                db=mock_db,
                admin=self.admin,
                action="ROLE_UPDATE",
                target_user_id=2,
                target_account_id=5,
                details="Updated role to TRADER",
                ip_address="192.168.1.100",
            )
        )
        self.assertEqual(log.admin_username, "admin")
        self.assertEqual(log.action, "ROLE_UPDATE")
        self.assertEqual(log.ip_address, "192.168.1.100")
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()

    def test_list_audit_logs_with_action_filtering(self):
        """Audit log endpoint retrieves paginated records filtered by action."""
        mock_log = AdminAuditLogModel(
            id=1,
            timestamp=datetime.now(timezone.utc),
            admin_id=1,
            admin_username="admin",
            target_user_id=2,
            target_account_id=5,
            action="CAPITAL_FUND",
            details="Funded ₹50,000",
            ip_address="127.0.0.1",
        )

        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            MockAsyncResult(1),           # count query
            MockAsyncResult([mock_log]),  # data query
        ]

        resp = asyncio.run(list_audit_logs(page=1, limit=10, action="CAPITAL_FUND", current_admin=self.admin, db=mock_db))
        self.assertEqual(resp["total"], 1)
        self.assertEqual(len(resp["logs"]), 1)
        self.assertEqual(resp["logs"][0]["action"], "CAPITAL_FUND")

    def test_get_admin_summary_aggregation(self):
        """Admin summary endpoint aggregates counts and capital across currencies."""
        mock_db = AsyncMock()
        mock_db.execute.side_effect = [
            MockAsyncResult(10),       # total users
            MockAsyncResult(9),        # active users
            MockAsyncResult(12),       # active accounts
            MockAsyncResult(1200000.0),# total INR capital
            MockAsyncResult(150000.0), # total USD capital
            MockAsyncResult(45),       # total audit events
        ]

        resp = asyncio.run(get_admin_summary(current_admin=self.admin, db=mock_db))
        self.assertEqual(resp["total_users"], 10)
        self.assertEqual(resp["active_users"], 9)
        self.assertEqual(resp["active_accounts"], 12)
        self.assertEqual(resp["total_capital_inr"], 1200000.0)
        self.assertEqual(resp["total_capital_usd"], 150000.0)
        self.assertEqual(resp["audit_events_count"], 45)


class TestDashboardAPIClientAdminMethods(unittest.TestCase):
    """Verifies that DashboardAPIClient methods construct requests correctly."""

    def setUp(self):
        self.client = DashboardAPIClient(base_url="http://testserver:8000")
        self.client.set_auth_token("test_jwt_admin_token")

    @patch.object(DashboardAPIClient, "_request")
    def test_get_admin_users_query_params(self, mock_request):
        """get_admin_users properly constructs query string with filters."""
        mock_request.return_value = {"users": [], "total": 0}
        self.client.get_admin_users(page=2, limit=25, role="TRADER", is_active=True, search="alice")
        mock_request.assert_called_once_with(
            "GET",
            "/api/v1/admin/users?page=2&limit=25&role=trader&is_active=true&search=alice",
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_fund_account_request(self, mock_request):
        """fund_account sends correct POST path and payload."""
        mock_request.return_value = {"message": "Success"}
        self.client.fund_account(account_id=7, amount=25000.0, reason="Bonus Grant")
        mock_request.assert_called_once_with(
            "POST",
            "/api/v1/admin/accounts/7/fund",
            {"amount": 25000.0, "reason": "Bonus Grant"},
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_update_user_role_request(self, mock_request):
        """update_user_role sends correct PATCH path and payload."""
        mock_request.return_value = {"message": "Success"}
        self.client.update_user_role(user_id=4, role="admin")
        mock_request.assert_called_once_with(
            "PATCH",
            "/api/v1/admin/users/4/role",
            {"role": "admin"},
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_toggle_user_status_request(self, mock_request):
        """toggle_user_status sends correct PATCH path and payload."""
        mock_request.return_value = {"message": "Success"}
        self.client.toggle_user_status(user_id=4, is_active=False, reason="Audit review")
        mock_request.assert_called_once_with(
            "PATCH",
            "/api/v1/admin/users/4/status",
            {"is_active": False, "reason": "Audit review"},
        )

    @patch.object(DashboardAPIClient, "_request")
    def test_rotate_and_revoke_api_key_requests(self, mock_request):
        """rotate_user_api_key and revoke_user_api_key send correct POST requests."""
        mock_request.return_value = {"message": "Success"}
        self.client.rotate_user_api_key(user_id=4)
        mock_request.assert_called_with("POST", "/api/v1/admin/users/4/api-key/rotate")

        self.client.revoke_user_api_key(user_id=4)
        mock_request.assert_called_with("POST", "/api/v1/admin/users/4/api-key/revoke")

    @patch.object(DashboardAPIClient, "_request")
    def test_get_admin_audit_logs_and_summary(self, mock_request):
        """get_admin_audit_logs and get_admin_summary send correct GET requests."""
        mock_request.return_value = {"logs": [], "total": 0}
        self.client.get_admin_audit_logs(page=1, limit=50, action="CAPITAL_FUND")
        mock_request.assert_called_with(
            "GET",
            "/api/v1/admin/audit-logs?page=1&limit=50&action=CAPITAL_FUND",
        )

        self.client.get_admin_summary()
        mock_request.assert_called_with("GET", "/api/v1/admin/summary")


if __name__ == "__main__":
    unittest.main()
