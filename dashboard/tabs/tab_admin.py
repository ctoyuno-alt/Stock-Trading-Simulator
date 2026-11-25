"""
Tab 8: Admin User & Account Management (RBAC) for Quantum Trader.
Provides administrative governance: summary KPIs, user directory with filters,
defensive schema parsing, action workbench (role update, status toggle, key rotate/revoke,
password override, capital funding/reset/archive), quick capital adjustment modal,
and audit trail ledger.
"""

import secrets
from typing import Any, Dict

try:
    import streamlit as st
except ImportError:
    st = None


def render_tab(
    api_client: Any,
    state: Dict[str, Any],
    market: str,
    symbol: str,
    timeframe: str,
) -> None:
    """
    Renders Tab 8: Admin User & Account Management.
    """
    # 1. Institutional RBAC Guard
    is_admin = (
        state.get("is_admin", False)
        or state.get("user_role") == "admin"
        or (
            isinstance(state.get("current_user"), dict)
            and str(state.get("current_user", {}).get("role") or "").lower() == "admin"
        )
    )

    if not is_admin:
        st.markdown(
            """
            <div style="background-color: rgba(255, 51, 102, 0.08); border: 1px solid #FF3366; border-radius: 8px; padding: 24px; text-align: center; margin: 20px 0;">
                <div style="font-size: 32px; margin-bottom: 8px;">🛡️</div>
                <h3 style="color: #FF3366; margin: 0 0 8px 0; font-weight: 700;">Institutional Access Restriction</h3>
                <p style="color: #8F9CAE; font-size: 14px; margin: 0;">
                    This panel is restricted strictly to users with verified <b>ADMIN</b> privileges.<br>
                    Your current session role does not have administrative rights to modify user directories, capital balances, or audit ledgers.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.warning("⚠️ Access Denied: Administrator role required to view this panel.")
        return

    current_user = state.get("current_user", {})
    if not isinstance(current_user, dict):
        current_user = {}

    # Define dialog if supported
    if hasattr(st, "dialog"):
        @st.dialog("⚡ Quick Paper Capital Adjustment")
        def capital_adjustment_dialog(account_id: int, account_name: str, current_balance: float, currency: str):
            curr_symbol = "$" if currency == "USD" else "₹"
            st.markdown(f"**Target Account:** `{account_name}` (ID: {account_id})")
            st.markdown(f"**Current Balance:** `{curr_symbol}{current_balance:,.2f}`")
            adj_mode = st.radio(
                "Adjustment Action",
                ["Inject Capital", "Reset Balance to Baseline"],
                horizontal=True,
                key=f"dlg_mode_{account_id}",
            )
            if adj_mode == "Inject Capital":
                fund_amt = st.number_input(
                    f"Amount to Add ({currency})",
                    min_value=1.0,
                    value=50000.0,
                    step=5000.0,
                    key=f"dlg_amt_{account_id}",
                )
                fund_rsn = st.text_input("Funding Reason", value="Admin Capital Grant", key=f"dlg_rsn_{account_id}")
                if st.button("💰 Confirm Capital Injection", type="primary", use_container_width=True, key=f"dlg_btn_fund_{account_id}"):
                    res = api_client.fund_account(account_id, fund_amt, fund_rsn)
                    if res and res.get("error"):
                        st.error(res.get("message"))
                    else:
                        st.success(f"Funded {curr_symbol}{fund_amt:,.2f} successfully!")
                        st.rerun()
            else:
                default_base = 25000.0 if currency == "USD" else 100000.0
                reset_bal = st.number_input(
                    f"New Baseline Balance ({currency})",
                    min_value=1000.0,
                    value=default_base,
                    step=5000.0,
                    key=f"dlg_new_{account_id}",
                )
                reset_rsn = st.text_input("Reset Reason", value="Admin Periodic Reset", key=f"dlg_rst_rsn_{account_id}")
                st.caption("⚠️ Resetting closes all open positions and cancels pending orders.")
                if st.button("🔄 Execute Account Reset", type="primary", use_container_width=True, key=f"dlg_btn_rst_{account_id}"):
                    res = api_client.reset_account_admin(account_id, reset_bal, reset_rsn)
                    if res and res.get("error"):
                        st.error(res.get("message"))
                    else:
                        st.success(f"Account reset to {curr_symbol}{reset_bal:,.2f} successfully!")
                        st.rerun()
    else:
        capital_adjustment_dialog = None

    st.markdown(
        """
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <div>
                <h2 style="margin: 0; font-size: 24px; font-weight: 700; color: #F8FAFC;">
                    👤 Admin User & Account Management
                </h2>
                <div style="font-size: 13px; color: #8F9CAE; margin-top: 4px;">
                    Platform Governance • RBAC Role Assignment • Virtual Capital Controls • Audit Trail
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Summary KPI Metric Cards
    summary = api_client.get_admin_summary()
    if not isinstance(summary, dict) or summary.get("error"):
        summary = {}

    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    col_kpi1.metric(
        "Total Users",
        f"{summary.get('total_users', 0)}",
        delta=f"{summary.get('active_users', 0)} Active",
    )
    col_kpi2.metric(
        "Active Accounts",
        f"{summary.get('active_accounts', 0)}",
        delta="Operational",
    )
    col_kpi3.metric(
        "Managed Capital",
        f"₹{summary.get('total_capital_inr', 0):,.0f}",
        delta=f"${summary.get('total_capital_usd', 0):,.0f} USD",
    )
    col_kpi4.metric(
        "Audit Events",
        f"{summary.get('audit_events_count', 0)}",
        delta="Immutable Log",
    )

    st.divider()

    # 2. User Directory & Filter Toolbar
    st.markdown("#### **📋 User Directory & Account Overview**")
    col_srch, col_role_fltr, col_stat_fltr = st.columns([2.5, 1.2, 1.2])
    with col_srch:
        admin_search = st.text_input(
            "🔍 Search Users",
            placeholder="Search username or email...",
            key="admin_search_input",
        )
    with col_role_fltr:
        admin_role_fltr = st.selectbox(
            "Role Filter",
            ["All Roles", "ADMIN", "TRADER", "VIEWER"],
            key="admin_role_filter_sel",
        )
    with col_stat_fltr:
        admin_stat_fltr = st.selectbox(
            "Status Filter",
            ["All Status", "Active", "Inactive"],
            key="admin_status_filter_sel",
        )

    filter_is_active = None
    if admin_stat_fltr == "Active":
        filter_is_active = True
    elif admin_stat_fltr == "Inactive":
        filter_is_active = False

    filter_role = None if admin_role_fltr == "All Roles" else admin_role_fltr.lower()

    users_resp = api_client.get_admin_users(
        page=1,
        limit=50,
        role=filter_role,
        is_active=filter_is_active,
        search=admin_search if admin_search.strip() else None,
    )
    users_list = users_resp.get("users", []) if isinstance(users_resp, dict) and not users_resp.get("error") else []

    if not users_list:
        st.info("No users match the search and filter criteria.")
    else:
        st.dataframe(
            users_list,
            use_container_width=True,
            column_config={
                "id": st.column_config.NumberColumn("User ID", format="%d"),
                "username": "Username",
                "email": "Email",
                "role": "Role",
                "is_active": st.column_config.CheckboxColumn("Active"),
                "accounts_count": st.column_config.NumberColumn("Accounts", format="%d"),
                "total_equity_inr": st.column_config.NumberColumn("Equity (INR)", format="₹%,.2f"),
                "total_equity_usd": st.column_config.NumberColumn("Equity (USD)", format="$%,.2f"),
                "api_key_masked": "API Key",
                "created_at": "Joined",
            },
        )

    st.divider()

    # 3. Action Workbench with Defensive Schema Parsing
    st.markdown("#### **⚙️ Administrative Action Workbench**")
    if not users_list:
        st.warning("No users available to manage.")
    else:
        col_wb_left, col_wb_right = st.columns(2)

        # Defensive schema parsing on users_list
        user_options = {}
        for u in users_list:
            if not isinstance(u, dict):
                continue
            uid = u.get("id") or u.get("user_id") or 0
            uname = u.get("username", "Unknown")
            urole = (u.get("role") or "trader").upper()
            user_options[f"{uname} (ID: {uid} - {urole})"] = u

        if not user_options:
            st.warning("No user records could be parsed.")
            return

        selected_label = st.selectbox("Select Target User", list(user_options.keys()), key="admin_target_user_sel")
        target_user = user_options[selected_label]
        target_user_id = target_user.get("id") or target_user.get("user_id") or 0
        target_username = target_user.get("username", "Unknown")
        current_user_id = current_user.get("id") or current_user.get("user_id")
        is_self = target_user_id == current_user_id

        with col_wb_left:
            st.markdown("##### **User RBAC & Credentials**")
            if is_self:
                st.info("🛡️ *You are viewing your own administrator account. Self-demotion and self-deactivation are guarded against lockout.*")

            # Role Update
            curr_role = (target_user.get("role") or "trader").upper()
            role_choices = ["ADMIN", "TRADER", "VIEWER"]
            curr_role_idx = role_choices.index(curr_role) if curr_role in role_choices else 1
            new_role = st.selectbox("Assign RBAC Role", role_choices, index=curr_role_idx, key=f"wb_role_{target_user_id}")
            if st.button("🔄 Update User Role", use_container_width=True, key=f"btn_upd_role_{target_user_id}"):
                if is_self and new_role != "ADMIN":
                    st.error("Cannot demote your own administrator account.")
                else:
                    resp = api_client.update_user_role(target_user_id, new_role.lower())
                    if resp and resp.get("error"):
                        st.error(resp.get("message"))
                    else:
                        st.success(f"Role updated to {new_role} successfully!")
                        st.rerun()

            # Status Toggle
            st.markdown("---")
            status_reason = st.text_input("Status Change Reason (Optional)", key=f"wb_stat_rsn_{target_user_id}")
            user_is_active = target_user.get("is_active", True)
            if user_is_active:
                deact_disabled = is_self
                if st.button("🔴 Deactivate User", disabled=deact_disabled, use_container_width=True, key=f"btn_deact_{target_user_id}"):
                    resp = api_client.toggle_user_status(target_user_id, False, status_reason)
                    if resp and resp.get("error"):
                        st.error(resp.get("message"))
                    else:
                        st.success("User deactivated successfully!")
                        st.rerun()
            else:
                if st.button("🟢 Reactivate User", use_container_width=True, key=f"btn_react_{target_user_id}"):
                    resp = api_client.toggle_user_status(target_user_id, True, status_reason)
                    if resp and resp.get("error"):
                        st.error(resp.get("message"))
                    else:
                        st.success("User reactivated successfully!")
                        st.rerun()

            # API Key Management
            st.markdown("---")
            st.write(f"- **Current API Key:** `{target_user.get('api_key_masked') or 'None configured'}`")
            k_btn1, k_btn2 = st.columns(2)
            with k_btn1:
                if st.button("🔑 Rotate Key", use_container_width=True, key=f"btn_rot_k_{target_user_id}"):
                    resp = api_client.rotate_user_api_key(target_user_id)
                    if resp and resp.get("error"):
                        st.error(resp.get("message"))
                    else:
                        st.success("API key rotated successfully!")
                        st.rerun()
            with k_btn2:
                if st.button("🚫 Revoke Key", use_container_width=True, key=f"btn_rev_k_{target_user_id}"):
                    resp = api_client.revoke_user_api_key(target_user_id)
                    if resp and resp.get("error"):
                        st.error(resp.get("message"))
                    else:
                        st.success("API key revoked successfully!")
                        st.rerun()

            # Administrative Password Reset
            st.markdown("---")
            st.markdown("##### **🔑 Administrative Password Override**")
            st.caption(f"Directly reset credentials for `{target_username}` with mandatory audit logging.")

            col_pw_in, col_pw_gen = st.columns([2, 1])
            with col_pw_gen:
                st.write("")
                st.write("")
                if st.button("🎲 Generate", key=f"btn_gen_pw_{target_user_id}", help="Generate temporary high-entropy password"):
                    generated_pw = f"QT-{secrets.token_hex(4).upper()}#{secrets.token_urlsafe(4)}"
                    if hasattr(st, "session_state"):
                        st.session_state[f"gen_pw_{target_user_id}"] = generated_pw

            cached_gen_pw = st.session_state.get(f"gen_pw_{target_user_id}", "") if hasattr(st, "session_state") else ""
            with col_pw_in:
                admin_new_pw = st.text_input(
                    "New Password",
                    value=cached_gen_pw,
                    type="password" if not cached_gen_pw else "default",
                    placeholder="Min 8 characters",
                    key=f"adm_new_pw_{target_user_id}",
                )

            admin_pw_reason = st.text_input(
                "Override Reason (Optional)",
                placeholder="e.g. User requested unlock via support ticket",
                key=f"adm_pw_rsn_{target_user_id}",
            )

            if st.button("🔐 Override User Password", use_container_width=True, key=f"btn_ovr_pw_{target_user_id}"):
                effective_pw = admin_new_pw.strip() if admin_new_pw else ""
                if not effective_pw or len(effective_pw) < 8:
                    st.error("Password must be at least 8 characters long.")
                else:
                    resp = api_client.admin_reset_user_password(target_user_id, effective_pw, admin_pw_reason)
                    if resp and resp.get("error"):
                        st.error(resp.get("message"))
                    else:
                        st.success(f"Password for '{target_username}' successfully reset and logged to audit trail!")
                        if hasattr(st, "session_state"):
                            st.session_state.pop(f"gen_pw_{target_user_id}", None)
                        st.rerun()

        with col_wb_right:
            st.markdown("##### **Virtual Capital & Account Lifecycle**")
            details_resp = api_client.get_admin_user_details(target_user_id)
            accounts_list = details_resp.get("accounts", []) if isinstance(details_resp, dict) and not details_resp.get("error") else []

            if not accounts_list:
                st.info(f"User '{target_username}' has no associated trading accounts.")
            else:
                account_options = {}
                for a in accounts_list:
                    if not isinstance(a, dict):
                        continue
                    a_id = a.get("id") or a.get("account_id") or 0
                    a_name = a.get("account_name", "Paper Account")
                    a_curr = a.get("currency", "INR")
                    account_options[f"{a_name} (ID: {a_id} - {a_curr})"] = a

                if not account_options:
                    st.info(f"No account options could be resolved for '{target_username}'.")
                else:
                    selected_acc_label = st.selectbox(
                        "Select Paper Account",
                        list(account_options.keys()),
                        key=f"wb_acc_sel_{target_user_id}",
                    )
                    target_account = account_options[selected_acc_label]
                    target_acc_id = target_account.get("id") or target_account.get("account_id") or 0
                    acc_curr = target_account.get("currency", "INR")
                    curr_sym_acc = "$" if acc_curr == "USD" else "₹"
                    acc_equity = float(target_account.get("equity", 0.0) or 0.0)
                    acc_cash = float(target_account.get("cash_balance", 0.0) or 0.0)

                    st.metric(
                        f"Account Equity ({acc_curr})",
                        f"{curr_sym_acc}{acc_equity:,.2f}",
                        delta=f"Cash: {curr_sym_acc}{acc_cash:,.2f}",
                    )

                    if capital_adjustment_dialog is not None:
                        if st.button("⚡ Open Quick Adjustment Modal", use_container_width=True, key=f"btn_open_dlg_{target_acc_id}"):
                            capital_adjustment_dialog(
                                target_acc_id,
                                target_account.get("account_name", "Paper Account"),
                                acc_cash,
                                acc_curr,
                            )

                    action_mode = st.radio(
                        "Action Mode",
                        ["💰 Fund Capital", "🔄 Reset Balance", "📦 Archive Account"],
                        horizontal=True,
                        key=f"wb_act_mode_{target_acc_id}",
                    )

                    if action_mode == "💰 Fund Capital":
                        fund_amount = st.number_input(
                            f"Capital to Inject ({acc_curr})",
                            min_value=1.0,
                            value=50000.0,
                            step=5000.0,
                            key=f"wb_fund_amt_{target_acc_id}",
                        )
                        fund_reason = st.text_input(
                            "Funding Reason",
                            value="Admin Capital Injection",
                            key=f"wb_fund_rsn_{target_acc_id}",
                        )
                        if st.button("Inject Virtual Capital", type="primary", use_container_width=True, key=f"btn_do_fund_{target_acc_id}"):
                            res = api_client.fund_account(target_acc_id, fund_amount, fund_reason)
                            if res and res.get("error"):
                                st.error(res.get("message"))
                            else:
                                st.success(f"Successfully injected {curr_sym_acc}{fund_amount:,.2f}!")
                                st.rerun()

                    elif action_mode == "🔄 Reset Balance":
                        default_reset = 25000.0 if acc_curr == "USD" else 100000.0
                        reset_amount = st.number_input(
                            f"Reset Baseline Capital ({acc_curr})",
                            min_value=1000.0,
                            value=default_reset,
                            step=5000.0,
                            key=f"wb_rst_amt_{target_acc_id}",
                        )
                        reset_reason = st.text_input(
                            "Reset Reason",
                            value="Admin Baseline Reset",
                            key=f"wb_rst_rsn_{target_acc_id}",
                        )
                        st.caption("⚠️ Closes all open positions and cancels pending orders.")
                        if st.button("Execute Reset Baseline", type="primary", use_container_width=True, key=f"btn_do_reset_{target_acc_id}"):
                            res = api_client.reset_account_admin(target_acc_id, reset_amount, reset_reason)
                            if res and res.get("error"):
                                st.error(res.get("message"))
                            else:
                                st.success(f"Account reset to {curr_sym_acc}{reset_amount:,.2f}!")
                                st.rerun()

                    else:
                        st.caption("📦 Archiving marks the account inactive (`is_active = False`) and prevents future trading.")
                        if st.button("Confirm Account Archival", type="secondary", use_container_width=True, key=f"btn_do_archive_{target_acc_id}"):
                            res = api_client.delete_account_admin(target_acc_id)
                            if res and res.get("error"):
                                st.error(res.get("message"))
                            else:
                                st.success("Account archived successfully!")
                                st.rerun()

    st.divider()

    # 4. Administrative Audit Trail Ledger
    st.markdown("#### **🛡️ Administrative Audit Trail Ledger**")
    col_aud_fltr, _ = st.columns([2, 3])
    with col_aud_fltr:
        aud_action_fltr = st.selectbox(
            "Filter Audit Actions",
            [
                "All Actions",
                "ROLE_UPDATE",
                "STATUS_TOGGLE",
                "CAPITAL_FUND",
                "CAPITAL_RESET",
                "ACCOUNT_ARCHIVE",
                "API_KEY_ROTATE",
                "API_KEY_REVOKE",
            ],
            key="admin_audit_action_filter",
        )

    aud_resp = api_client.get_admin_audit_logs(
        page=1,
        limit=50,
        action=aud_action_fltr,
    )
    audit_logs = aud_resp.get("logs", []) if isinstance(aud_resp, dict) and not aud_resp.get("error") else []
    if not audit_logs:
        st.info("No administrative audit entries recorded yet.")
    else:
        st.dataframe(
            audit_logs,
            use_container_width=True,
            column_config={
                "id": st.column_config.NumberColumn("Log ID", format="%d"),
                "timestamp": "Timestamp (UTC)",
                "admin_username": "Admin",
                "action": "Action",
                "target_user_id": st.column_config.NumberColumn("Target User ID", format="%d"),
                "target_account_id": st.column_config.NumberColumn("Target Account ID", format="%d"),
                "details": "Details",
                "ip_address": "IP Address",
            },
        )
