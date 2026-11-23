# Quantum Trader: Admin Account Management System
## Architecture, Design & Implementation Specification Plan (Milestone M1)

---

### Executive Summary

The **Admin Account Management System** for Quantum Trader establishes an enterprise-grade administrative control plane for the AI Quantitative Paper Trading Simulator. The system enables authorized administrators (`UserRole.ADMIN`) to govern user lifecycles, manage paper trading capital allocations across multi-currency accounts (INR ₹ and USD $), rotate or revoke API credentials, enforce role-based access control (RBAC), and maintain an immutable administrative audit log of all state-mutating actions.

This plan details the full architectural design encompassing database schemas, FastAPI administrative endpoints, role-gated security guardrails with self-lockout prevention, Streamlit dashboard integration adhering to the Obsidian cyber-dark visual language, and an automated verification test plan.

---

### 1. Database Operations & Schema Architecture

#### 1.1 Existing Relational Models
The current database schema (`database/models.py`) contains:
- `UserModel` (`users` table): User authentication, credentials (PBKDF2 hash + salt), assigned role (`UserRole.ADMIN`, `UserRole.TRADER`, `UserRole.VIEWER`), active status (`is_active: bool`), and optional programmatic API key (`api_key: str`).
- `AccountModel` (`accounts` table): Paper trading account linked to a user via `user_id`, maintaining `initial_capital_inr`, `cash_balance_inr`, `equity_inr`, `daily_starting_equity`, `circuit_breaker_tripped`, `currency` (`INR` or `USD`), and `is_active: bool`.
- `PositionModel` (`positions` table): Live and closed virtual positions with average entry price, current price, stop-loss, take-profit, and PnL metrics.
- `OrderModel` (`orders` table): Virtual order audit records with Indian tax breakdowns (STT, turnover, SEBI, GST, stamp duty).
- `PortfolioSnapshotModel` (`portfolio_snapshots` table): Historical portfolio valuation snapshots for drawdown tracking.

#### 1.2 New Administrative Audit Log Model (`AdminAuditLogModel`)
To satisfy regulatory and security compliance, every state-mutating administrative action must be immutably recorded in a dedicated audit log table.

**Schema Definition (`admin_audit_logs` table)**:
```python
class AdminAuditLogModel(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
    )
    admin_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    admin_username: Mapped[str] = mapped_column(String(64), nullable=False)
    target_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    target_account_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("accounts.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Relationships
    admin: Mapped["UserModel"] = relationship("UserModel", foreign_keys=[admin_id])
    target_user: Mapped[Optional["UserModel"]] = relationship("UserModel", foreign_keys=[target_user_id])
    target_account: Mapped[Optional["AccountModel"]] = relationship("AccountModel", foreign_keys=[target_account_id])
```

**Tracked Administrative Actions**:
- `ROLE_UPDATE`: Modification of user RBAC role (e.g. TRADER -> ADMIN or VIEWER).
- `STATUS_TOGGLE`: Activation or deactivation of user accounts.
- `CAPITAL_FUND`: Virtual paper capital injection or balance adjustment.
- `CAPITAL_RESET`: Resetting an account's cash and equity to a clean initial baseline, archiving existing open positions.
- `ACCOUNT_ARCHIVE`: Soft-deleting/archiving a paper account (`is_active = False`).
- `API_KEY_ROTATE`: Re-generating a fresh `qt_live_...` API token.
- `API_KEY_REVOKE`: Revoking and clearing an active API token (`api_key = None`).

#### 1.3 Schema Auto-Provisioning & Migration
`database/init_db.py` executes `await conn.run_sync(Base.metadata.create_all)` during backend startup. Subclassing `Base` ensures `admin_audit_logs` is automatically provisioned in both PostgreSQL and SQLite (test) environments without requiring manual DDL commands.

---

### 2. Administrative FastAPI Endpoint Specifications

All administrative endpoints are registered under the `/api/v1/admin` prefix and strictly protected by the dependency `current_admin: UserModel = Depends(require_admin)`.

```
========================================================================================
METHOD  PATH                                        DESCRIPTION
========================================================================================
GET     /api/v1/admin/users                         List users (paginated, filter, search)
GET     /api/v1/admin/users/{user_id}               Inspect user profile, accounts, positions
PATCH   /api/v1/admin/users/{user_id}/role          Update user role (ADMIN, TRADER, VIEWER)
PATCH   /api/v1/admin/users/{user_id}/status        Activate / deactivate user account
POST    /api/v1/admin/accounts/{account_id}/fund    Fund virtual paper capital
POST    /api/v1/admin/accounts/{account_id}/reset   Reset account balance & wipe positions
DELETE  /api/v1/admin/accounts/{account_id}         Archive account (soft delete)
POST    /api/v1/admin/users/{user_id}/api-key/rotate Rotate API key (fresh qt_live_...)
POST    /api/v1/admin/users/{user_id}/api-key/revoke Revoke API key (sets to null)
GET     /api/v1/admin/audit-logs                    Retrieve administrative audit trail
GET     /api/v1/admin/summary                       Summary stats for admin dashboard KPIs
========================================================================================
```

#### 2.1 Detailed Endpoint Specifications

##### 1. User Listing (`GET /api/v1/admin/users`)
- **Query Parameters**:
  - `page: int = 1` (min 1)
  - `limit: int = 20` (min 1, max 100)
  - `role: Optional[UserRole] = None`
  - `is_active: Optional[bool] = None`
  - `search: Optional[str] = None` (substring match against `username` or `email`, case-insensitive)
- **Response Schema**:
  ```json
  {
    "users": [
      {
        "id": 1,
        "username": "admin",
        "email": "admin@quantumtrader.local",
        "role": "admin",
        "is_active": true,
        "has_api_key": true,
        "api_key_masked": "ak_live_..._key",
        "created_at": "2026-11-23T10:00:00Z",
        "accounts_count": 2,
        "total_equity_inr": 100000.0,
        "total_equity_usd": 25000.0
      }
    ],
    "total": 1,
    "page": 1,
    "limit": 20,
    "pages": 1
  }
  ```

##### 2. User Details Inspection (`GET /api/v1/admin/users/{user_id}`)
- **Path Parameters**: `user_id: int`
- **Response Schema**:
  ```json
  {
    "user": {
      "id": 2,
      "username": "trader_one",
      "email": "trader1@quantumtrader.local",
      "role": "trader",
      "is_active": true,
      "api_key_masked": "qt_live_...9f",
      "created_at": "2026-11-23T10:05:00Z"
    },
    "accounts": [
      {
        "id": 2,
        "account_name": "trader_one's Paper Account",
        "currency": "INR",
        "cash_balance": 100000.0,
        "equity": 100000.0,
        "is_active": true,
        "circuit_breaker_tripped": false
      }
    ],
    "positions_count": 1,
    "open_positions": [
      {
        "id": 10,
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "quantity": 25,
        "average_entry_price": 2450.0,
        "current_price": 2480.0,
        "unrealized_pnl_inr": 750.0,
        "status": "OPEN"
      }
    ]
  }
  ```

##### 3. Role Management (`PATCH /api/v1/admin/users/{user_id}/role`)
- **Request Body**:
  ```json
  {
    "role": "admin"
  }
  ```
- **Self-Lockout Check**: If `user_id == current_admin.id` and `role != UserRole.ADMIN`, raise `HTTPException(status_code=400, detail="Cannot demote your own administrator account.")`.
- **Audit Log**: Action `ROLE_UPDATE` with details describing previous and new roles.

##### 4. User Status Management (`PATCH /api/v1/admin/users/{user_id}/status`)
- **Request Body**:
  ```json
  {
    "is_active": false,
    "reason": "Policy violation investigation"
  }
  ```
- **Self-Lockout Check**: If `user_id == current_admin.id` and `is_active is False`, raise `HTTPException(status_code=400, detail="Cannot deactivate your own administrator account.")`.
- **Audit Log**: Action `STATUS_TOGGLE` recording status transition and reason.

##### 5. Virtual Capital Funding (`POST /api/v1/admin/accounts/{account_id}/fund`)
- **Request Body**:
  ```json
  {
    "amount": 50000.0,
    "reason": "Q4 Trading Competition Grant"
  }
  ```
- **Logic**: Adds `amount` to both `cash_balance_inr` and `equity_inr` of the specified `AccountModel`. Also updates `daily_starting_equity` if set.
- **Audit Log**: Action `CAPITAL_FUND` with account ID, amount, and reason.

##### 6. Account Balance Reset (`POST /api/v1/admin/accounts/{account_id}/reset`)
- **Request Body**:
  ```json
  {
    "initial_capital": 100000.0,
    "reason": "Periodic paper simulation reset"
  }
  ```
- **Logic**: Clears open positions (marking status CLOSED with current timestamp), cancels pending orders, resets `cash_balance_inr` and `equity_inr` to `initial_capital` (or account's default `initial_capital_inr`), resets circuit breaker flags.
- **Audit Log**: Action `CAPITAL_RESET` recording reset parameters.

##### 7. Account Archival (`DELETE /api/v1/admin/accounts/{account_id}`)
- **Logic**: Soft archives account by setting `is_active = False`. Prevents foreign key constraint violations with historical orders/snapshots while preventing future trading.
- **Audit Log**: Action `ACCOUNT_ARCHIVE`.

##### 8. API Key Rotation (`POST /api/v1/admin/users/{user_id}/api-key/rotate`)
- **Logic**: Generates a new cryptographically secure token via `generate_api_key()`, saves to `user.api_key`.
- **Audit Log**: Action `API_KEY_ROTATE`.

##### 9. API Key Revocation (`POST /api/v1/admin/users/{user_id}/api-key/revoke`)
- **Logic**: Sets `user.api_key = None`.
- **Audit Log**: Action `API_KEY_REVOKE`.

##### 10. Audit Log Retrieval (`GET /api/v1/admin/audit-logs`)
- **Query Parameters**: `page: int = 1`, `limit: int = 50`, `action: Optional[str] = None`, `target_user_id: Optional[int] = None`.
- **Response**: List of chronologically ordered audit logs (latest first) with total count.

##### 11. Admin Summary Metrics (`GET /api/v1/admin/summary`)
- **Response Schema**:
  ```json
  {
    "total_users": 12,
    "active_users": 11,
    "active_accounts": 14,
    "total_capital_inr": 1400000.0,
    "total_capital_usd": 150000.0,
    "audit_events_count": 87
  }
  ```

---

### 3. Role-Based Security Rules & Self-Lockout Prevention

#### 3.1 Security Dependency Hierarchy
```
Request Header: [Authorization: Bearer <jwt>] OR [X-API-Key: <key>]
                      │
                      ▼
             get_current_user (deps.py)
                      │
     ┌────────────────┴────────────────┐
     ▼                                 ▼
Unauthenticated / Invalid         Valid UserModel & is_active==True
  HTTP 401 Unauthorized                │
                                       ▼
                             require_role([UserRole.ADMIN])
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
              role != ADMIN                       role == ADMIN
           HTTP 403 Forbidden               HTTP 200 / Execute Handler
```

#### 3.2 Self-Lockout Prevention Guardrails
A critical vulnerability in administrative systems is self-lockout: an admin accidentally demoting themselves or deactivating their own account, stranding the platform without administrative governance.

1. **Self-Demotion Guard**:
   ```python
   if target_user.id == current_admin.id and new_role != UserRole.ADMIN:
       raise HTTPException(
           status_code=status.HTTP_400_BAD_REQUEST,
           detail="Cannot demote your own administrator account. Assign another admin first."
       )
   ```
2. **Self-Deactivation Guard**:
   ```python
   if target_user.id == current_admin.id and not is_active:
       raise HTTPException(
           status_code=status.HTTP_400_BAD_REQUEST,
           detail="Cannot deactivate your own administrator account."
       )
   ```
3. **UI Affirmation**: The frontend dashboard actively disables self-deactivation buttons and displays an informative banner when the logged-in administrator inspects their own user card.

---

### 4. Streamlit UI Layouts & Obsidian Cyber-Dark Styling

#### 4.1 UI Design Philosophy
The admin interface matches the established **Obsidian Cyber-Dark Theme**:
- Deep Obsidian background: `#080B11`
- Frosted Obsidian card background: `#0E131F`
- Subtle borders: `1px solid rgba(255, 255, 255, 0.08)`
- Electric Indigo primary accents: `#6366F1` / `#818CF8`
- Emerald Green success accents: `#00E676`
- Crimson Red alert/warning accents: `#FF3B30`
- JetBrains Mono typography for numbers, IDs, and financial amounts.

#### 4.2 Dynamic Tab Navigation Integration
The 8th tab `"👤 Admin User & Account Management"` is conditionally appended **only** when `is_admin` is True:
```python
is_admin = str(user_role).lower() == "admin"
tab_titles = [
    "📊 Market & Technicals",
    "🧠 AI Confluence Analysis",
    "🤖 Autonomous AI Auto-Trader",
    "💼 Positions & Execution",
    "📜 Trade Ledger & Performance",
    "🧪 Historical Backtest",
    "🛡️ System Health & Freshness",
]
if is_admin:
    tab_titles.append("👤 Admin User & Account Management")

all_tabs = st.tabs(tab_titles)
```
Non-admin users never see the tab header or its contents.

#### 4.3 Component Mockups & Layout Blueprint

```
+---------------------------------------------------------------------------------------------------------+
| 👤 ADMIN USER & ACCOUNT MANAGEMENT                                                    [ 🔄 Refresh ]   |
| Institutional Governance • RBAC Role Assignment • Virtual Capital Controls • Audit Trail               |
+---------------------------------------------------------------------------------------------------------+
| [ Total Users: 12 ]       [ Active Accounts: 14 ]   [ Managed Capital: ₹1.4M / $150K ] [ Audit Logs: 87 ] | (KPI Cards)
+---------------------------------------------------------------------------------------------------------+
| 🔍 Search: [_______________]  Role: [All Roles ▼]   Status: [All Status ▼]                             | (Filter Bar)
+---------------------------------------------------------------------------------------------------------+
| USER DIRECTORY TABLE (st.dataframe with custom column formatting)                                       |
| ID | Username     | Email                   | Role    | Active | Accounts | Total Equity  | API Key     |
| 1  | admin        | admin@quantumtrader.local| ADMIN   | [x]    | 2        | ₹100,000.00   | ak_live_... |
| 2  | trader_alpha | alpha@fund.local        | TRADER  | [x]    | 1        | ₹250,000.00   | qt_live_... |
+---------------------------------------------------------------------------------------------------------+
| ⚙️ ADMINISTRATIVE ACTION WORKBENCH                                                                      |
| ---------------------------------------------------- | ------------------------------------------------ |
| [PANEL A: USER RBAC & CREDENTIALS]                   | [PANEL B: CAPITAL & ACCOUNT LIFECYCLE]           |
| Selected User: [trader_alpha (ID: 2) ▼]              | Selected Account: [trader_alpha's INR Account ▼] |
| Current Role: TRADER | Status: ACTIVE                | Balance: ₹250,000.00 | Currency: INR             |
|                                                      |                                                  |
| Change Role: ( ) ADMIN  (*) TRADER  ( ) VIEWER       | Capital Action: (*) Fund Capital  ( ) Reset      |
| [ 🔄 Update Role ]                                   | Amount to Inject: [ 50,000.00 ]                  |
|                                                      | Reason: [Trader performance bonus]               |
| Account Status:                                      | [ 💰 Inject Virtual Capital ]                    |
| [ 🔴 Deactivate User ]                               |                                                  |
|                                                      | Account Lifecycle:                               |
| Credential Management:                               | [ 🔄 Reset Account Balance to Baseline ]         |
| [ 🔑 Rotate API Key ]   [ 🚫 Revoke API Key ]        | [ 📦 Archive Account ]                           |
+---------------------------------------------------------------------------------------------------------+
| 🛡️ ADMINISTRATIVE AUDIT TRAIL                                                                           |
| Filter Action: [All Actions ▼]                                                                          |
| Timestamp (UTC)      | Admin | Action         | Target User | Target Account | Details        | IP      |
| 2026-11-23 10:15:22 | admin | CAPITAL_FUND   | 2           | 2              | +₹50,000.00    | 127.0.0.1|
| 2026-11-23 10:10:05 | admin | ROLE_UPDATE    | 3           | None           | VIEWER->TRADER | 127.0.0.1|
+---------------------------------------------------------------------------------------------------------+
```

#### 4.4 Capital Adjustment Modal (`@st.dialog`)
For quick adjustments without navigating the full workbench, an `@st.dialog("Adjust Virtual Capital")` dialog provides quick deposit or reset workflows with immediate toast feedback and re-render.

---

### 5. Automated Verification & Test Execution Plan

#### 5.1 Test Suite Scope (`tests/unit/test_admin_account_management.py`)
Compatible with both `python3 -m unittest` and `pytest`:

1. **Authentication & Authorization Guardrails**:
   - `test_admin_endpoints_require_auth`: Requests with no token/key receive `401 Unauthorized`.
   - `test_admin_endpoints_reject_non_admin`: Requests with `TRADER` or `VIEWER` roles receive `403 Forbidden`.
   - `test_admin_endpoints_permit_admin`: Requests with `ADMIN` role receive `200 OK` or `201 Created`.
2. **User Listing, Pagination & Search**:
   - `test_user_listing_pagination`: Correct total counts, page sizing, and slicing.
   - `test_user_listing_search_and_filter`: Substring search by username/email; exact filtering by role and `is_active`.
3. **User Details Inspection**:
   - `test_get_user_details`: Retrieves user profile, linked accounts, cash balances, and open positions.
4. **RBAC & Self-Lockout Prevention**:
   - `test_update_user_role`: Admin updates trader role to `VIEWER` or `ADMIN`.
   - `test_self_demotion_prevention`: Admin attempting to demote themselves receives `400 Bad Request`.
5. **Status Toggling & Self-Deactivation Prevention**:
   - `test_toggle_user_status`: Admin activates and deactivates trader accounts.
   - `test_self_deactivation_prevention`: Admin attempting to deactivate themselves receives `400 Bad Request`.
6. **Virtual Capital Adjustments & Account Lifecycle**:
   - `test_fund_account_capital`: Cash balance and equity increase by funded amount.
   - `test_reset_account_capital`: Open positions closed, balances reset to initial baseline.
   - `test_archive_account`: Account soft-deleted (`is_active = False`).
7. **Credential Management**:
   - `test_rotate_api_key`: Generates fresh `qt_live_...` key.
   - `test_revoke_api_key`: Sets `api_key = None`.
8. **Audit Logging Integrity**:
   - `test_mutating_actions_record_audit_log`: Verifies that role changes, status toggles, capital injections, resets, and API key rotations generate entries in `admin_audit_logs`.
   - `test_audit_log_inspection_endpoint`: Fetches paginated logs filtered by action type.
9. **Admin Summary Statistics**:
   - `test_admin_summary_kpi_counts`: Accurate counts for users, accounts, capital by currency, and audit events.

#### 5.2 Verification Commands
- Unit test suite: `python3 -m unittest discover -s tests`
- Dedicated admin test: `python3 -m unittest tests/unit/test_admin_account_management.py`
- Streamlit syntax check: `python3 -c "import dashboard.app; import dashboard.api_client; print('OK')"`

---

### Conclusion
This plan provides complete coverage for Milestone M1, fulfilling all requirements (R1, R2, R3, R4) with zero shortcuts, real persistence, and defense-in-depth security.
