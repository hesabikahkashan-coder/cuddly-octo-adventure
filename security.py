"""
NWH Crypto Trading Bot - Security Module
Enterprise-grade security: JWT, AES-256, 2FA, API key encryption.
"""

import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple

import pyotp
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


class AESEncryption:
    """AES-256-GCM encryption for sensitive data like API keys."""

    def __init__(self, key: str):
        # Derive a 32-byte key from the provided key using SHA-256
        self._key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext using AES-256-GCM."""
        iv = secrets.token_bytes(12)  # 96-bit IV for GCM
        cipher = Cipher(
            algorithms.AES(self._key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext.encode()) + encryptor.finalize()
        tag = encryptor.tag

        # Combine IV + tag + ciphertext and base64 encode
        encrypted = iv + tag + ciphertext
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt AES-256-GCM encrypted text."""
        try:
            decoded = base64.urlsafe_b64decode(encrypted_text.encode())
            iv = decoded[:12]
            tag = decoded[12:28]
            ciphertext = decoded[28:]

            cipher = Cipher(
                algorithms.AES(self._key),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data")


# Global encryption instance
_encryptor = AESEncryption(settings.security.ENCRYPTION_KEY)


def encrypt_api_key(api_key: str) -> str:
    """Encrypt exchange API key for secure storage."""
    return _encryptor.encrypt(api_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt exchange API key for use."""
    return _encryptor.decrypt(encrypted_key)


class PasswordManager:
    """Password hashing and verification."""

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def is_strong_password(password: str) -> Tuple[bool, str]:
        """Validate password strength."""
        if len(password) < 12:
            return False, "Password must be at least 12 characters"
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False, "Password must contain at least one special character"
        return True, "Password is strong"


class JWTManager:
    """JWT token management with access and refresh tokens."""

    @staticmethod
    def create_access_token(
        subject: str,
        extra_claims: Optional[Dict[str, Any]] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a short-lived access token."""
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=settings.security.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        payload = {
            "sub": str(subject),
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access",
            "jti": secrets.token_urlsafe(16),
        }
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(payload, settings.security.SECRET_KEY, algorithm=settings.security.ALGORITHM)

    @staticmethod
    def create_refresh_token(subject: str) -> str:
        """Create a long-lived refresh token."""
        expire = datetime.now(timezone.utc) + timedelta(days=settings.security.REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": str(subject),
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh",
            "jti": secrets.token_urlsafe(32),
        }
        return jwt.encode(payload, settings.security.SECRET_KEY, algorithm=settings.security.ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(
                token,
                settings.security.SECRET_KEY,
                algorithms=[settings.security.ALGORITHM]
            )
            return payload
        except JWTError as e:
            logger.warning(f"JWT decode failed: {e}")
            raise ValueError(f"Invalid token: {e}")

    @staticmethod
    def verify_access_token(token: str) -> str:
        """Verify access token and return subject."""
        payload = JWTManager.decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("Not an access token")
        subject = payload.get("sub")
        if not subject:
            raise ValueError("Token missing subject")
        return subject

    @staticmethod
    def verify_refresh_token(token: str) -> str:
        """Verify refresh token and return subject."""
        payload = JWTManager.decode_token(token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        subject = payload.get("sub")
        if not subject:
            raise ValueError("Token missing subject")
        return subject


class TwoFactorAuth:
    """TOTP-based 2FA using pyotp."""

    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret."""
        return pyotp.random_base32()

    @staticmethod
    def get_provisioning_uri(secret: str, username: str) -> str:
        """Get the provisioning URI for QR code generation."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=username,
            issuer_name=settings.security.TWO_FA_ISSUER
        )

    @staticmethod
    def verify_token(secret: str, token: str) -> bool:
        """Verify a TOTP token."""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)

    @staticmethod
    def get_current_token(secret: str) -> str:
        """Get the current TOTP token (for testing)."""
        totp = pyotp.TOTP(secret)
        return totp.now()


class IPWhitelist:
    """IP address whitelist management."""

    def __init__(self):
        self._allowed_ips = set(settings.security.ALLOWED_IPS)

    def is_allowed(self, ip: str) -> bool:
        """Check if an IP is whitelisted. Empty list means all IPs allowed."""
        if not self._allowed_ips:
            return True
        return ip in self._allowed_ips

    def add_ip(self, ip: str):
        self._allowed_ips.add(ip)

    def remove_ip(self, ip: str):
        self._allowed_ips.discard(ip)


class HMACValidator:
    """HMAC signature validation for webhook security."""

    @staticmethod
    def create_signature(payload: bytes, secret: str) -> str:
        """Create HMAC-SHA256 signature."""
        return hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    def verify_signature(payload: bytes, secret: str, signature: str) -> bool:
        """Verify HMAC-SHA256 signature."""
        expected = HMACValidator.create_signature(payload, secret)
        return hmac.compare_digest(expected, signature)


# Singleton instances
password_manager = PasswordManager()
jwt_manager = JWTManager()
two_factor_auth = TwoFactorAuth()
ip_whitelist = IPWhitelist()
