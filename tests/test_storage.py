import pytest

from skillmaster.config import StorageMode
from skillmaster.storage.config_resolver import resolve_bucket


@pytest.mark.asyncio
async def test_env_mode_returns_env_bucket(monkeypatch):
    monkeypatch.setattr("skillmaster.storage.config_resolver.settings.skillmaster_storage_mode", StorageMode.ENV)
    monkeypatch.setattr("skillmaster.storage.config_resolver.settings.skillmaster_gcs_bucket", "my-bucket")
    result = await resolve_bucket()
    assert result == "my-bucket"


@pytest.mark.asyncio
async def test_db_mode_raises_when_no_bucket_found(monkeypatch):
    monkeypatch.setattr("skillmaster.storage.config_resolver.settings.skillmaster_storage_mode", StorageMode.DB)
    with pytest.raises(ValueError, match="no bucket found"):
        await resolve_bucket(org_id="test-org")
