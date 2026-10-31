"""Unit tests for encryption service and database-level at-rest encryption."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.encryption import EncryptionService
from app.domain.entities import ExecutionEntity, ServerEntity
from app.infrastructure.database import async_session_factory
from app.infrastructure.repositories.sqlite import (
    SqliteExecutionRepository,
    SqliteServerRepository,
)
from app.schemas.server import ServerHealthStatus, StdioConfig, TransportType


def test_encryption_service_basic_encrypt_decrypt():
    """Test standard encryption and decryption round-trip."""
    service = EncryptionService()
    plaintext = "super-secret-api-key-12345"
    token = service.encrypt(plaintext)

    assert token != plaintext
    assert token.startswith("gAAAAA")
    assert service.is_encrypted_token(token) is True
    assert service.is_encrypted_token(plaintext) is False

    decrypted = service.decrypt(token)
    assert decrypted == plaintext


def test_encryption_service_custom_passphrase():
    """Test key derivation with arbitrary non-base64 passphrase."""
    service = EncryptionService(key="my-custom-passphrase-not-fernet-b64")
    plaintext = "confidential-payload"
    token = service.encrypt(plaintext)

    assert token != plaintext
    assert service.decrypt(token) == plaintext


def test_encryption_service_empty_and_invalid():
    """Test edge cases with empty strings and invalid tokens."""
    service = EncryptionService()
    assert service.encrypt("") == ""
    assert service.decrypt("") == ""

    with pytest.raises(ValueError, match="Failed to decrypt ciphertext"):
        service.decrypt("gAAAAABinvalidtokenstringthatdoesnotdecode")


def test_encryption_service_dict_envelope():
    """Test dictionary encryption and transparent decryption envelope."""
    service = EncryptionService()
    data = {
        "command": "python",
        "env": {"API_KEY": "sk-proj-xyz", "PORT": "8000"},
        "nested": {"secret": "very-secret"},
    }

    envelope = service.encrypt_dict(data)
    assert envelope is not None
    assert "__encrypted__" in envelope
    assert "sk-proj-xyz" not in str(envelope)

    decrypted_data = service.decrypt_dict(envelope)
    assert decrypted_data == data

    # Test None
    assert service.encrypt_dict(None) is None
    assert service.decrypt_dict(None) is None

    # Test legacy plaintext dict fallback
    plaintext_dict = {"already": "plain"}
    assert service.decrypt_dict(plaintext_dict) == plaintext_dict


def test_encryption_service_sensitive_keys_and_masking():
    """Test sensitive key detection and secret masking."""
    service = EncryptionService()

    assert service.is_sensitive_key("GITHUB_TOKEN") is True
    assert service.is_sensitive_key("DATABASE_URL") is True
    assert service.is_sensitive_key("APP_SECRET") is True
    assert service.is_sensitive_key("AWS_SECRET_ACCESS_KEY") is True
    assert service.is_sensitive_key("AUTH_HEADER") is True
    assert service.is_sensitive_key("PASSWORD") is True
    assert service.is_sensitive_key("SERVER_PORT") is False
    assert service.is_sensitive_key("HOST") is False

    # Masking
    assert service.mask_secret("") == ""
    assert service.mask_secret("123") == "********"
    masked = service.mask_secret("sk-1234567890abcdef", visible_last=4)
    assert masked == "***************cdef"
    assert len(masked) == len("sk-1234567890abcdef")
    assert masked.endswith("cdef")

    # Selective key encryption
    env_vars = {
        "SERVER_PORT": "8080",
        "GITHUB_TOKEN": "ghp_1234567890",
    }
    encrypted_env = service.encrypt_sensitive_values(env_vars)
    assert encrypted_env["SERVER_PORT"] == "8080"
    assert encrypted_env["GITHUB_TOKEN"].startswith("enc:gAAAAA")

    decrypted_env = service.decrypt_sensitive_values(encrypted_env)
    assert decrypted_env == env_vars


async def test_database_server_at_rest_encryption():
    """Verify that Server stdio_config is encrypted in SQLite at rest and decrypted on fetch."""
    repo = SqliteServerRepository()
    server_id = uuid4()
    secret_key = "sk-super-secret-enterprise-key-999"

    server = ServerEntity(
        id=server_id,
        name="secure-sqlite-server",
        transport=TransportType.STDIO,
        stdio_config=StdioConfig(
            command="python3",
            args=["run.py"],
            env={"OPENAI_API_KEY": secret_key, "MODE": "production"},
        ),
        enabled=True,
        health_status=ServerHealthStatus.HEALTHY,
    )

    # 1. Save via repository
    await repo.create(server)

    # 2. Inspect RAW database content directly using raw SQL
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT stdio_config FROM mcp_servers WHERE id = :id"),
            {"id": str(server_id)},
        )
        raw_row = result.fetchone()
        assert raw_row is not None
        raw_stdio_config = raw_row[0]

        # The raw DB value must be either a dict or JSON string with '__encrypted__'
        raw_str = (
            json.dumps(raw_stdio_config)
            if isinstance(raw_stdio_config, dict)
            else str(raw_stdio_config)
        )

        # CRITICAL ASSERTIONS: Secret must NOT appear in raw database storage
        assert secret_key not in raw_str
        assert "__encrypted__" in raw_str
        assert "gAAAAA" in raw_str

    # 3. Retrieve through repository: Must be transparently decrypted
    fetched = await repo.get_by_id(server_id)
    assert fetched is not None
    assert fetched.stdio_config is not None
    assert fetched.stdio_config.env is not None
    assert fetched.stdio_config.env["OPENAI_API_KEY"] == secret_key
    assert fetched.stdio_config.env["MODE"] == "production"


async def test_database_execution_arguments_at_rest_encryption():
    """Verify that ExecutionEntity arguments are encrypted in SQLite at rest and decrypted on fetch."""
    server_repo = SqliteServerRepository()
    exec_repo = SqliteExecutionRepository()

    server_id = uuid4()
    exec_id = uuid4()
    secret_param = "jwt-super-confidential-token-abc"

    # Create parent server first
    server = ServerEntity(
        id=server_id,
        name="exec-server",
        transport=TransportType.STDIO,
    )
    await server_repo.create(server)

    execution = ExecutionEntity(
        id=exec_id,
        server_id=server_id,
        server_name="exec-server",
        tool_name="authenticated_tool",
        arguments={"auth_token": secret_param, "limit": 10},
        is_error=False,
        duration_ms=45.0,
        executed_at=datetime.now(UTC),
    )

    await exec_repo.create(execution)

    # Inspect raw SQL row
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT arguments FROM tool_executions WHERE id = :id"),
            {"id": str(exec_id)},
        )
        raw_row = result.fetchone()
        assert raw_row is not None
        raw_arguments = raw_row[0]
        raw_str = (
            json.dumps(raw_arguments) if isinstance(raw_arguments, dict) else str(raw_arguments)
        )

        assert secret_param not in raw_str
        assert "__encrypted__" in raw_str

    # Fetch through repository: Decrypted
    fetched = await exec_repo.get_by_id(exec_id)
    assert fetched is not None
    assert fetched.arguments == {"auth_token": secret_param, "limit": 10}


async def test_database_legacy_unencrypted_fallback():
    """Verify that legacy unencrypted rows in database load gracefully without crashing."""
    repo = SqliteServerRepository()
    server_id = uuid4()
    legacy_json_raw = json.dumps({"command": "node", "args": ["index.js"]})

    # Direct raw SQL insert with plaintext JSON (simulating legacy database record)
    async with async_session_factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO mcp_servers (id, name, transport, stdio_config, enabled, health_status, discovered_tool_count, created_at, updated_at)
                VALUES (:id, :name, :transport, :stdio_config, :enabled, :health_status, :discovered_tool_count, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
            ),
            {
                "id": str(server_id),
                "name": "legacy-plain-server",
                "transport": "stdio",
                "stdio_config": legacy_json_raw,
                "enabled": True,
                "health_status": "UNKNOWN",
                "discovered_tool_count": 0,
            },
        )
        await session.commit()

    # Repository should load it smoothly via fallback
    fetched = await repo.get_by_id(server_id)
    assert fetched is not None
    assert fetched.name == "legacy-plain-server"
    assert fetched.stdio_config is not None
    assert fetched.stdio_config.command == "node"
    assert fetched.stdio_config.args == ["index.js"]
