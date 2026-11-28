"""Where the backend settings come from."""

from pathlib import Path

import pytest

from app.core.config import BASE_DIR, Settings


def test_settings_read_only_the_backend_env_file() -> None:
    assert Settings.model_config["env_file"] == BASE_DIR / ".env"


def test_settings_ignore_env_files_in_the_working_and_parent_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: a .env in the working folder and one in its parent, as with the Compose-only .env at the repo root
    working = tmp_path / "working"
    working.mkdir()
    (tmp_path / ".env").write_text("PROJECT_NAME=from-parent-env\n")
    (working / ".env").write_text("PROJECT_NAME=from-working-env\n")
    monkeypatch.chdir(working)
    monkeypatch.delenv("PROJECT_NAME", raising=False)

    # Act
    settings = Settings()

    # Assert: the value is backend/.env's, never one of the other two
    assert settings.PROJECT_NAME not in {"from-parent-env", "from-working-env"}
