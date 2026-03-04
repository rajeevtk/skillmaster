import logging

from skillmaster.db.connection import get_pool

logger = logging.getLogger(__name__)


async def get_org_settings(org_id: str) -> dict | None:
    """Query org-level settings from NeonDB."""
    pool = await get_pool()
    if pool is None:
        return None

    row = await pool.fetchrow(
        "SELECT gcs_bucket, default_skill_prefix FROM org_settings WHERE org_id = $1",
        org_id,
    )
    return dict(row) if row else None


async def get_team_settings(team_id: str) -> dict | None:
    """Query team-level settings from NeonDB."""
    pool = await get_pool()
    if pool is None:
        return None

    row = await pool.fetchrow(
        "SELECT gcs_bucket, org_id FROM team_settings WHERE team_id = $1",
        team_id,
    )
    return dict(row) if row else None
