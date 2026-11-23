"""
Cryptographic Security, Password Hashing, and JWT Token Management.

Provides:
- NIST-compliant PBKDF2-HMAC-SHA256 password hashing (600,000 rounds) with cryptographically random salts.
- Constant-time password verification preventing timing side-channel attacks.
- RFC 7519 HMAC-SHA256 (HS256) JWT access token issuance and signature validation.
- High-entropy API key generation for programmatic bots and scripts.
"""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Any, Dict, Optional, Tuple

from backend.app.core.config import get_settings

settings = get_settings()

PBKDF2_ITERATIONS = 600000


def hash_password(password: str) -> Tuple[str, str]:
    """
    Hashes a plaintext password using PBKDF2-HMAC-SHA256 with 600,000 iterations.
    Returns (hashed_hex, salt_hex).
    """
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return hashed, salt


def verify_password(password: str, salt: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against the stored salt and hash using constant-time comparison.
    """
    computed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return hmac.compare_digest(computed, hashed_password)


def _b64_url_encode(data: bytes) -> str:
    """Encodes bytes to base64url string without trailing padding '='."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_url_decode(s: str) -> bytes:
    """Decodes base64url string restoring required '=' padding."""
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Issues an RFC 7519 HMAC-SHA256 (HS256) JWT access token signed with JWT_SECRET_KEY.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=settings.JWT_EXPIRATION_HOURS)

    to_encode.update({"exp": int(expire.timestamp()), "iat": int(now.timestamp())})

    header = {"alg": "HS256", "typ": "JWT"}
    p1 = _b64_url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p2 = _b64_url_encode(json.dumps(to_encode, separators=(",", ":")).encode("utf-8"))

    secret_bytes = settings.JWT_SECRET_KEY.encode("utf-8")
    signing_input = f"{p1}.{p2}".encode("utf-8")
    sig = _b64_url_encode(hmac.new(secret_bytes, signing_input, hashlib.sha256).digest())

    return f"{p1}.{p2}.{sig}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates JWT token signature and expiration.
    Returns payload claims dict if valid, None if invalid or expired.
    """
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None

        p1, p2, sig = parts
        secret_bytes = settings.JWT_SECRET_KEY.encode("utf-8")
        signing_input = f"{p1}.{p2}".encode("utf-8")
        expected_sig = _b64_url_encode(hmac.new(secret_bytes, signing_input, hashlib.sha256).digest())

        if not hmac.compare_digest(sig, expected_sig):
            return None

        payload_bytes = _b64_url_decode(p2)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Check expiration
        exp = payload.get("exp")
        if exp is not None:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if now_ts > exp:
                return None

        return payload
    except Exception:
        return None


def generate_api_key() -> str:
    """Generates a secure high-entropy API key for programmatic trading bots."""
    return f"qt_live_{secrets.token_urlsafe(32)}"


def create_password_reset_token(
    user_id: int,
    username: str,
    expires_minutes: int = 15,
) -> str:
    """
    Issues a cryptographically signed, time-limited single-use password reset token.
    Claims contain: sub (user_id), username, purpose='password_reset', jti (nonce), and exp.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "purpose": "password_reset",
        "jti": secrets.token_hex(16),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    p1 = _b64_url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p2 = _b64_url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    secret_bytes = settings.JWT_SECRET_KEY.encode("utf-8")
    signing_input = f"{p1}.{p2}".encode("utf-8")
    sig = _b64_url_encode(hmac.new(secret_bytes, signing_input, hashlib.sha256).digest())
    return f"{p1}.{p2}.{sig}"


def decode_password_reset_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates a password reset token signature, expiration, and purpose claim.
    Returns payload claims dict if valid, None if invalid, expired, or purpose mismatch.
    """
    payload = decode_access_token(token)
    if not payload:
        return None
    if payload.get("purpose") != "password_reset":
        return None
    return payload


def generate_secure_random_password(length: int = 14) -> str:
    """Generates an alphanumeric password with special characters suitable for temporary resets."""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(max(length, 12)))

