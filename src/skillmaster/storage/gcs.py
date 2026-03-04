import json
import logging

from google.cloud import storage

from skillmaster.config import settings

logger = logging.getLogger(__name__)


def _get_client() -> storage.Client:
    return storage.Client(project=settings.skillmaster_gcs_project)


async def upload_skill(
    skill_id: str,
    skill_md: str,
    bucket_name: str,
    additional_files: dict[str, str] | None = None,
) -> str:
    """Upload a generated skill to GCS. Returns the GCS path prefix."""
    client = _get_client()
    bucket = client.bucket(bucket_name)
    prefix = f"skills/{skill_id}"

    # Upload SKILL.md
    blob = bucket.blob(f"{prefix}/SKILL.md")
    blob.upload_from_string(skill_md, content_type="text/markdown")
    logger.info("Uploaded SKILL.md to gs://%s/%s/SKILL.md", bucket_name, prefix)

    # Upload additional files
    if additional_files:
        for filename, content in additional_files.items():
            blob = bucket.blob(f"{prefix}/{filename}")
            blob.upload_from_string(content, content_type="text/markdown")
            logger.info("Uploaded %s to gs://%s/%s/%s", filename, bucket_name, prefix, filename)

    # Upload metadata
    metadata = {"skill_id": skill_id, "files": ["SKILL.md"] + list((additional_files or {}).keys())}
    meta_blob = bucket.blob(f"{prefix}/metadata.json")
    meta_blob.upload_from_string(json.dumps(metadata), content_type="application/json")

    return f"gs://{bucket_name}/{prefix}"


async def download_skill(skill_id: str, bucket_name: str) -> str | None:
    """Download a SKILL.md from GCS."""
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"skills/{skill_id}/SKILL.md")

    if not blob.exists():
        return None

    return blob.download_as_text()


async def list_skills(bucket_name: str) -> list[dict]:
    """List all skills in a bucket."""
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix="skills/", delimiter="/")

    skills = []
    for page in blobs.pages:
        for prefix in page.prefixes:
            skill_id = prefix.rstrip("/").split("/")[-1]
            skills.append({"skill_id": skill_id, "gcs_path": f"gs://{bucket_name}/{prefix}"})

    return skills
