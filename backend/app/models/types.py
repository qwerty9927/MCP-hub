"""Custom SQLAlchemy types with transparent at-rest encryption."""

from typing import Any

from sqlalchemy import JSON, Text, TypeDecorator

from app.core.encryption import get_encryption_service


class EncryptedJSON(TypeDecorator):
    """SQLAlchemy TypeDecorator providing automatic at-rest encryption for JSON fields.

    In the database, data is stored as a JSON envelope: {"__encrypted__": "<fernet_ciphertext>"}.
    When read by the ORM, it is automatically decrypted back into a native Python dictionary.
    Unencrypted legacy data is loaded transparently as fallback without breaking existing rows.
    """

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        service = get_encryption_service()
        return service.encrypt_dict(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        service = get_encryption_service()
        return service.decrypt_dict(value)


class EncryptedString(TypeDecorator):
    """SQLAlchemy TypeDecorator providing automatic at-rest encryption for string fields."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        service = get_encryption_service()
        return service.encrypt(str(value))

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        service = get_encryption_service()
        try:
            return service.decrypt(str(value))
        except Exception:
            # Fallback for unencrypted legacy strings
            return str(value)
