import logging

from skillmaster.config import settings, StorageMode

logger = logging.getLogger(__name__)


async def resolve_bucket(org_id: str | None = None, team_id: str | None = None) -> str:
    """Resolve which GCS bucket to use for skill storage.

    Controlled by SKILLMASTER_STORAGE_MODE env var:
    - "env": Use the bucket name from SKILLMASTER_GCS_BUCKET env var directly
    - "db": Multi-tenant mode — look up bucket per org/team from NeonDB
    """
    if settings.skillmaster_storage_mode == StorageMode.ENV:
        logger.info("Storage mode=env, using bucket: %s", settings.skillmaster_gcs_bucket)
        return settings.skillmaster_gcs_bucket

    if settings.skillmaster_storage_mode == StorageMode.DB:
        bucket = await _lookup_bucket_from_db(org_id, team_id)
        if bucket:
            return bucket
        raise ValueError(
            f"Storage mode=db but no bucket found for org_id={org_id}, team_id={team_id}. "
            "Ensure org/team settings exist in NeonDB."
        )

    raise ValueError(f"Unknown storage mode: {settings.skillmaster_storage_mode}")


async def _lookup_bucket_from_db(org_id: str | None, team_id: str | None) -> str | None:
    """Query NeonDB for org/team-specific bucket configuration.

    TODO: Replace stub with real NeonDB queries once schema is deployed.
    """
    # --- STUB: replace with real DB queries ---
    # from skillmaster.db.queries import get_team_settings, get_org_settings
    #
    # if team_id:
    #     team_settings = await get_team_settings(team_id)
    #     if team_settings and team_settings.get("gcs_bucket"):
    #         return team_settings["gcs_bucket"]
    #
    # if org_id:
    #     org_settings = await get_org_settings(org_id)
    #     if org_settings and org_settings.get("gcs_bucket"):
    #         return org_settings["gcs_bucket"]
    # --- END STUB ---

    logger.warning("DB bucket lookup is stubbed out. org_id=%s, team_id=%s", org_id, team_id)
    return None
