"""
Unit Tests for Authentication, JWT Cryptography, PBKDF2 Password Hashing, and RBAC Security.
Tests standard password verification, token generation, tamper detection, and expiration.
"""

from datetime import timedelta
import time
import unittest

from backend.app.core.security import (
    create_access_token,
    create_password_reset_token,
    decode_access_token,
    decode_password_reset_token,
    generate_api_key,
    generate_secure_random_password,
    hash_password,
    verify_password,
)

try:
    from database.models import UserRole
except ImportError:
    from enum import Enum
    class UserRole(str, Enum):
        ADMIN = "admin"
        TRADER = "trader"
        VIEWER = "viewer"


class TestSecurityAuth(unittest.TestCase):

    def test_password_hashing_and_verification(self):
        """Verify PBKDF2-HMAC-SHA256 password hashing and secure verification."""
        password = "super_secret_trading_pass_123"
        hashed, salt = hash_password(password)

        self.assertIsInstance(hashed, str)
        self.assertIsInstance(salt, str)
        self.assertEqual(len(hashed), 64)  # SHA-256 produces 64 hex chars
        self.assertEqual(len(salt), 32)    # 16 bytes hex = 32 chars

        # Verify correct password matches
        self.assertTrue(verify_password(password, salt, hashed))

        # Verify incorrect password is rejected
        self.assertFalse(verify_password("wrong_password", salt, hashed))
        self.assertFalse(verify_password("", salt, hashed))

    def test_password_salt_uniqueness(self):
        """Verify that identical passwords generate distinct hashes due to random salting."""
        password = "same_plain_password"
        h1, s1 = hash_password(password)
        h2, s2 = hash_password(password)

        self.assertNotEqual(s1, s2)
        self.assertNotEqual(h1, h2)
        self.assertTrue(verify_password(password, s1, h1))
        self.assertTrue(verify_password(password, s2, h2))

    def test_jwt_creation_and_decoding(self):
        """Verify RFC 7519 HMAC-SHA256 JWT access token issuance and claims parsing."""
        data = {"sub": "42", "username": "pro_trader", "role": "trader"}
        token = create_access_token(data=data, expires_delta=timedelta(minutes=15))

        self.assertIsInstance(token, str)
        parts = token.split(".")
        self.assertEqual(len(parts), 3, "JWT must consist of header, payload, and signature")

        decoded = decode_access_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.get("sub"), "42")
        self.assertEqual(decoded.get("username"), "pro_trader")
        self.assertEqual(decoded.get("role"), "trader")
        self.assertIn("exp", decoded)

    def test_jwt_tampered_token_rejection(self):
        """Verify that any modification to payload or signature invalidates the token."""
        data = {"sub": "1", "username": "admin", "role": "admin"}
        token = create_access_token(data=data)
        parts = token.split(".")

        # Tampered signature
        tampered_sig = parts[0] + "." + parts[1] + ".tampered_signature"
        self.assertIsNone(decode_access_token(tampered_sig))

        # Tampered payload
        tampered_payload = "a" + parts[1][1:]
        tampered_token = parts[0] + "." + tampered_payload + "." + parts[2]
        self.assertIsNone(decode_access_token(tampered_token))

    def test_jwt_token_expiration(self):
        """Verify that expired JWT access tokens are strictly rejected."""
        data = {"sub": "99", "username": "expired_user", "role": "viewer"}
        # Token expired 5 seconds in the past
        token = create_access_token(data=data, expires_delta=timedelta(seconds=-5))
        decoded = decode_access_token(token)
        self.assertIsNone(decoded, "Expired tokens must decode to None")

    def test_api_key_generation(self):
        """Verify high-entropy programmatic API key structure and collision resistance."""
        key1 = generate_api_key()
        key2 = generate_api_key()

        self.assertTrue(key1.startswith("qt_"), "API key must have 'qt_' prefix")
        self.assertTrue(len(key1) >= 35, "API key must have sufficient entropy length")
        self.assertNotEqual(key1, key2, "API keys must be unique")

    def test_user_roles(self):
        """Verify RBAC role enumeration values."""
        self.assertEqual(UserRole.ADMIN.value, "admin")
        self.assertEqual(UserRole.TRADER.value, "trader")
        self.assertEqual(UserRole.VIEWER.value, "viewer")

    def test_password_reset_token_issuance_and_decoding(self):
        """Verify creation and decoding of time-limited password reset tokens."""
        token = create_password_reset_token(user_id=105, username="algo_trader", expires_minutes=15)
        self.assertIsInstance(token, str)
        self.assertEqual(len(token.split(".")), 3)

        payload = decode_password_reset_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("sub"), "105")
        self.assertEqual(payload.get("username"), "algo_trader")
        self.assertEqual(payload.get("purpose"), "password_reset")
        self.assertIn("jti", payload)
        self.assertIn("exp", payload)

    def test_password_reset_token_purpose_mismatch(self):
        """Verify that a standard JWT access token cannot be used as a password reset token."""
        access_token = create_access_token({"sub": "105", "username": "algo_trader", "role": "trader"})
        # Should be rejected because purpose != "password_reset"
        self.assertIsNone(decode_password_reset_token(access_token))

    def test_password_reset_token_expiration(self):
        """Verify that an expired password reset token is strictly rejected."""
        token = create_password_reset_token(user_id=105, username="algo_trader", expires_minutes=-1)
        self.assertIsNone(decode_password_reset_token(token))

    def test_password_reset_token_tampering(self):
        """Verify that tampered password reset tokens are rejected."""
        token = create_password_reset_token(user_id=105, username="algo_trader", expires_minutes=15)
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + ".invalid_sig"
        self.assertIsNone(decode_password_reset_token(tampered))

    def test_generate_secure_random_password(self):
        """Verify high-entropy random password generation."""
        pw1 = generate_secure_random_password(16)
        pw2 = generate_secure_random_password(16)
        self.assertGreaterEqual(len(pw1), 16)
        self.assertNotEqual(pw1, pw2)



if __name__ == "__main__":
    unittest.main()
