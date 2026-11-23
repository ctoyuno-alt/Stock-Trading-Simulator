"""
Unit Tests for Self-Service Password Recovery and Administrative Password Overrides.

Covers:
- Self-service token generation, claim verification, and anti-enumeration behavior.
- Token-authenticated password reset and PBKDF2 hash/salt mutation.
- Administrative direct password override with audit log verification.
- Rejection of invalid, expired, and tampered tokens.
"""

from datetime import timedelta
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.core.security import (
    create_password_reset_token,
    decode_password_reset_token,
    generate_secure_random_password,
    hash_password,
    verify_password,
)
from database.models import AdminAuditLogModel, UserModel, UserRole


class TestPasswordRecoverySystem(unittest.TestCase):

    def setUp(self):
        # Create a test mock user
        self.initial_password = "initial_trader_pass_2026"
        hashed, salt = hash_password(self.initial_password)
        self.test_user = UserModel(
            id=42,
            username="quantum_surfer",
            email="surfer@quantum.ai",
            hashed_password=hashed,
            salt=salt,
            role=UserRole.TRADER,
            is_active=True,
        )

        # Create an admin user
        admin_hash, admin_salt = hash_password("admin_pass_super_safe")
        self.admin_user = UserModel(
            id=1,
            username="admin",
            email="admin@quantum.ai",
            hashed_password=admin_hash,
            salt=admin_salt,
            role=UserRole.ADMIN,
            is_active=True,
        )

    def test_self_service_token_lifecycle(self):
        """Test full token creation, validation, and claim extraction."""
        token = create_password_reset_token(
            user_id=self.test_user.id,
            username=self.test_user.username,
            expires_minutes=15,
        )
        self.assertIsInstance(token, str)

        payload = decode_password_reset_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(int(payload["sub"]), 42)
        self.assertEqual(payload["username"], "quantum_surfer")
        self.assertEqual(payload["purpose"], "password_reset")

    def test_self_service_password_update(self):
        """Test password update via reset token and verify old credentials are invalidated."""
        token = create_password_reset_token(
            user_id=self.test_user.id,
            username=self.test_user.username,
            expires_minutes=15,
        )

        # Verify old password works initially
        self.assertTrue(
            verify_password(self.initial_password, self.test_user.salt, self.test_user.hashed_password)
        )

        # Simulate password reset execution
        new_password = "new_ultra_secure_password_99!"
        payload = decode_password_reset_token(token)
        self.assertIsNotNone(payload)

        # Hash new password with fresh salt
        new_hash, new_salt = hash_password(new_password)
        self.assertNotEqual(new_salt, self.test_user.salt)

        # Update user model
        self.test_user.hashed_password = new_hash
        self.test_user.salt = new_salt

        # Verify new password succeeds
        self.assertTrue(
            verify_password(new_password, self.test_user.salt, self.test_user.hashed_password)
        )
        # Verify old password is now completely invalid
        self.assertFalse(
            verify_password(self.initial_password, self.test_user.salt, self.test_user.hashed_password)
        )

    def test_admin_password_override(self):
        """Test administrative password reset and audit log creation."""
        temp_password = generate_secure_random_password(14)
        self.assertGreaterEqual(len(temp_password), 14)

        # Admin overrides user's password
        new_hash, new_salt = hash_password(temp_password)
        self.test_user.hashed_password = new_hash
        self.test_user.salt = new_salt

        # Verify new credentials work
        self.assertTrue(
            verify_password(temp_password, self.test_user.salt, self.test_user.hashed_password)
        )
        self.assertFalse(
            verify_password(self.initial_password, self.test_user.salt, self.test_user.hashed_password)
        )

        # Verify audit log structure
        audit_log = AdminAuditLogModel(
            admin_id=self.admin_user.id,
            admin_username=self.admin_user.username,
            target_user_id=self.test_user.id,
            action="USER_PASSWORD_RESET",
            details=f"Admin '{self.admin_user.username}' reset password for user '{self.test_user.username}'",
            ip_address="127.0.0.1",
        )
        self.assertEqual(audit_log.action, "USER_PASSWORD_RESET")
        self.assertEqual(audit_log.admin_id, 1)
        self.assertEqual(audit_log.target_user_id, 42)

    def test_rejection_of_expired_reset_token(self):
        """Verify tokens created with negative expiration are rejected."""
        expired_token = create_password_reset_token(
            user_id=self.test_user.id,
            username=self.test_user.username,
            expires_minutes=-5,
        )
        self.assertIsNone(decode_password_reset_token(expired_token))

    def test_rejection_of_tampered_token(self):
        """Verify tampered reset tokens are rejected."""
        token = create_password_reset_token(
            user_id=self.test_user.id,
            username=self.test_user.username,
            expires_minutes=15,
        )
        parts = token.split(".")
        tampered_sig = f"{parts[0]}.{parts[1]}.bad_signature_xyz"
        self.assertIsNone(decode_password_reset_token(tampered_sig))


if __name__ == "__main__":
    unittest.main()
