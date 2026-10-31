"""Symmetric encryption service for database secrets and sensitive values."""

import base64
import hashlib
import json
import re
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

# Sensitive key patterns for field-level detection
SENSITIVE_KEY_PATTERNS = [
    re.compile(r".*TOKEN.*", re.IGNORECASE),
    re.compile(r".*SECRET.*", re.IGNORECASE),
    re.compile(r".*PASSWORD.*", re.IGNORECASE),
    re.compile(r".*KEY.*", re.IGNORECASE),
    re.compile(r".*AUTH.*", re.IGNORECASE),
    re.compile(r".*CREDENTIAL.*", re.IGNORECASE),
    re.compile(r".*DATABASE_URL.*", re.IGNORECASE),
]


class EncryptionService:
    """Cryptographic service for encrypting and decrypting sensitive values at rest."""

    def __init__(self, key: str | None = None) -> None:
        raw_key = key or get_settings().ENCRYPTION_KEY
        self._fernet = self._derive_fernet(raw_key)

    @staticmethod
    def _derive_fernet(key_material: str) -> Fernet:
        """Derive a valid 32-byte URL-safe base64 Fernet key from arbitrary key material."""
        key_bytes = key_material.strip().encode("utf-8")
        if len(key_bytes) == 44:
            try:
                # Try directly as standard Fernet key
                return Fernet(key_bytes)
            except Exception:
                pass

        # Derive 32-byte key via SHA-256 for arbitrary passphrases
        digest = hashlib.sha256(key_bytes).digest()
        derived_b64 = base64.urlsafe_b64encode(digest)
        return Fernet(derived_b64)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string and return a URL-safe Fernet ciphertext token."""
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a Fernet ciphertext token back to plaintext string."""
        if not ciphertext:
            return ""
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError(
                f"Failed to decrypt ciphertext with active encryption key: {exc}"
            ) from exc

    def is_encrypted_token(self, value: str) -> bool:
        """Check if a string has the characteristics of a Fernet ciphertext token."""
        if not isinstance(value, str) or not value.startswith("gAAAAA") or len(value) < 32:
            return False
        try:
            self._fernet.decrypt(value.encode("utf-8"))
            return True
        except Exception:
            return False

    def encrypt_dict(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        """Serialize a dictionary to JSON and wrap it into an encrypted token envelope."""
        if data is None:
            return None
        raw_json = json.dumps(data)
        token = self.encrypt(raw_json)
        return {"__encrypted__": token}

    def decrypt_dict(self, data: Any) -> Any:
        """Decrypt an encrypted envelope back to its original dictionary, supporting legacy fallback."""
        if data is None:
            return None
        if isinstance(data, dict) and "__encrypted__" in data:
            ciphertext = data["__encrypted__"]
            decrypted_json = self.decrypt(ciphertext)
            return json.loads(decrypted_json)
        return data

    @staticmethod
    def is_sensitive_key(key_name: str) -> bool:
        """Check if an environment variable or header key is considered sensitive."""
        return any(pattern.search(key_name) for pattern in SENSITIVE_KEY_PATTERNS)

    def encrypt_sensitive_values(self, data: dict[str, str]) -> dict[str, str]:
        """Encrypt only sensitive keys within a key-value dictionary."""
        result: dict[str, str] = {}
        for k, v in data.items():
            if self.is_sensitive_key(k) and not self.is_encrypted_token(v):
                result[k] = f"enc:{self.encrypt(v)}"
            else:
                result[k] = v
        return result

    def decrypt_sensitive_values(self, data: dict[str, str]) -> dict[str, str]:
        """Decrypt any encrypted sensitive values in a dictionary."""
        result: dict[str, str] = {}
        for k, v in data.items():
            if isinstance(v, str) and v.startswith("enc:"):
                raw_token = v[4:]
                try:
                    result[k] = self.decrypt(raw_token)
                except Exception:
                    result[k] = v
            else:
                result[k] = v
        return result

    @staticmethod
    def mask_secret(secret: str, visible_last: int = 4) -> str:
        """Mask a sensitive key or token, showing only the last few characters if long enough."""
        if not secret:
            return ""
        if len(secret) <= visible_last:
            return "********"
        return f"{'*' * (len(secret) - visible_last)}{secret[-visible_last:]}"


@lru_cache
def get_encryption_service() -> EncryptionService:
    """Return cached singleton instance of EncryptionService."""
    return EncryptionService()
