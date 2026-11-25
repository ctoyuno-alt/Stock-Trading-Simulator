"""
Authentication and User Session Gate for Quantum Trader.
Provides Login, Account Registration, and Password Reset workflows.
"""

from typing import Any, Dict

try:
    import streamlit as st
except ImportError:
    st = None


def render_auth_screen(api_client: Any) -> Dict[str, Any]:
    """
    Checks session authentication. If authenticated, returns user_profile dict.
    If unauthenticated, renders login/registration/recovery forms and halts
    execution via st.stop().
    """
    auth_token = st.session_state.get("auth_token")
    user_profile = st.session_state.get("user_profile")

    if auth_token:
        api_client.set_auth_token(auth_token)

    if auth_token and isinstance(user_profile, dict):
        return user_profile

    # Render minimal modern Obsidian login / registration interface
    st.markdown(
        """
        <div style="text-align: center; margin-top: 3rem; margin-bottom: 2rem;">
            <div style="font-size: 38px; margin-bottom: 8px;">⚡</div>
            <div style="font-size: 26px; font-weight: 700; color: #F8FAFC; letter-spacing: 0.04em;">QUANTUM TRADER</div>
            <div style="font-size: 13px; color: #8F9CAE; margin-top: 4px;">Institutional AI Paper Trading & Quantitative Analytics Workstation</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, auth_col2, _ = st.columns([1, 1.8, 1])
    with auth_col2:
        tab_login, tab_register, tab_forgot = st.tabs(["🔐 Sign In", "✨ Create Account", "🔑 Forgot Password?"])
        with tab_login:
            with st.form("login_form"):
                st.markdown("#### **Access Your Terminal**")
                login_user = st.text_input("Username", placeholder="e.g. admin or trader_one")
                login_pass = st.text_input("Password", type="password", placeholder="Enter your password")
                submitted = st.form_submit_button("Sign In to Terminal", use_container_width=True, type="primary")
                if submitted:
                    if not login_user or not login_pass:
                        st.error("Please enter both username and password.")
                    else:
                        resp = api_client.login(login_user, login_pass)
                        if resp.get("error"):
                            st.error(f"Authentication failed: {resp.get('message', 'Invalid credentials')}")
                        else:
                            st.session_state["auth_token"] = resp.get("access_token")
                            st.session_state["user_profile"] = resp.get("user")
                            st.rerun()

            st.caption("💡 **Default Administrator Access:** `admin` / `admin_secure_password`")

        with tab_register:
            with st.form("register_form"):
                st.markdown("#### **Create New Trader Account**")
                reg_user = st.text_input("Username", placeholder="Choose username (3+ chars)")
                reg_email = st.text_input("Email", placeholder="trader@quantum.ai")
                reg_pass = st.text_input("Password", type="password", placeholder="Minimum 8 characters")
                reg_submitted = st.form_submit_button("Register & Launch Terminal", use_container_width=True, type="primary")
                if reg_submitted:
                    if not reg_user or not reg_email or not reg_pass:
                        st.error("Please fill in all registration fields.")
                    elif len(reg_pass) < 8:
                        st.error("Password must be at least 8 characters long.")
                    else:
                        resp = api_client.register(reg_user, reg_email, reg_pass)
                        if resp.get("error"):
                            st.error(f"Registration failed: {resp.get('message', 'Could not create account')}")
                        else:
                            st.session_state["auth_token"] = resp.get("access_token")
                            st.session_state["user_profile"] = resp.get("user")
                            st.rerun()

        with tab_forgot:
            st.markdown("#### **Account Recovery & Password Reset**")
            st.caption("Recover access to your paper trading terminal using self-service token verification.")

            # Step 1: Request Token
            with st.form("forgot_password_request_form"):
                st.markdown("##### **Step 1: Request 15-Min Recovery Token**")
                reset_id = st.text_input("Username or Registered Email", placeholder="e.g. trader_one or trader@quantum.ai")
                req_btn = st.form_submit_button("Generate Recovery Token", use_container_width=True)
                if req_btn:
                    if not reset_id.strip():
                        st.error("Please enter your username or registered email address.")
                    else:
                        resp = api_client.forgot_password(reset_id.strip())
                        if resp.get("error"):
                            st.error(f"Error: {resp.get('message', 'Failed to generate recovery token')}")
                        else:
                            token = resp.get("reset_token")
                            if token:
                                st.session_state["cached_reset_token"] = token
                                st.success(f"✅ Recovery token issued! Valid for {resp.get('expires_in_minutes', 15)} minutes.")
                            else:
                                st.info(resp.get("message"))

            cached_token = st.session_state.get("cached_reset_token", "")
            if cached_token:
                st.markdown(
                    f"""
                    <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 8px; padding: 12px; margin-top: 10px; margin-bottom: 12px;">
                        <div style="font-size: 11px; font-weight: 600; color: #10B981; letter-spacing: 0.05em; text-transform: uppercase;">Active 15-Minute Recovery Token</div>
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; word-break: break-all; color: #F8FAFC; margin-top: 4px;">{cached_token}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Step 2: Apply Token and Set New Password
            with st.form("reset_password_submit_form"):
                st.markdown("##### **Step 2: Set New Secure Password**")
                token_input = st.text_input(
                    "Recovery Token",
                    value=cached_token,
                    placeholder="Paste 15-minute recovery token here",
                )
                new_pw = st.text_input("New Password", type="password", placeholder="Minimum 8 characters")
                confirm_pw = st.text_input("Confirm New Password", type="password", placeholder="Re-type new password")
                submit_reset = st.form_submit_button("Reset Password & Proceed to Login", use_container_width=True, type="primary")
                if submit_reset:
                    if not token_input.strip():
                        st.error("Please provide the recovery token.")
                    elif not new_pw or not confirm_pw:
                        st.error("Please enter and confirm your new password.")
                    elif len(new_pw) < 8:
                        st.error("New password must be at least 8 characters long.")
                    elif new_pw != confirm_pw:
                        st.error("Passwords do not match. Please verify and retry.")
                    else:
                        resp = api_client.reset_password(token_input.strip(), new_pw)
                        if resp.get("error"):
                            st.error(f"Reset failed: {resp.get('message', 'Invalid or expired token')}")
                        else:
                            st.session_state.pop("cached_reset_token", None)
                            st.success("🎉 Password successfully reset! Please click '🔐 Sign In' tab to log in.")

    st.stop()


def handle_logout(api_client: Any) -> None:
    """
    Clears session state auth tokens, resets api_client auth, and triggers rerun.
    """
    st.session_state.pop("auth_token", None)
    st.session_state.pop("user_profile", None)
    st.session_state.pop("cached_reset_token", None)
    api_client.set_auth_token(None)
    st.rerun()
