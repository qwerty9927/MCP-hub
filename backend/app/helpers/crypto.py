"""Symmetric encryption for secrets stored in the database (OAuth tokens and client credentials)."""

from cryptography.fernet import Fernet, InvalidToken


class SecretCipher:
    """Encrypts and decrypts text with a Fernet key (AES-128-CBC + HMAC-SHA256)."""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Return the plaintext, or raise ValueError if the value was not encrypted with this key."""
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Stored secret cannot be decrypted with OAUTH_ENCRYPTION_KEY") from exc
