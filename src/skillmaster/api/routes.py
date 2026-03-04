import logging
import uuid

from fastapi import APIRouter, HTTPException

from skillmaster.api.models import (
    SkillGenerateRequest,
    SkillGenerateResponse,
    SkillValidateRequest,
    ValidationResult,
)
from skillmaster.pipeline.orchestrator import generate_skill
from skillmaster.pipeline.validator import validate_skill_md
from skillmaster.processors import process_input
from skillmaster.storage.config_resolver import resolve_bucket
from skillmaster.storage.gcs import upload_skill, download_skill, list_skills

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/skills/generate", response_model=SkillGenerateResponse)
async def generate(request: SkillGenerateRequest):
    """Generate a Claude Agent Skill from input content."""
    skill_id = str(uuid.uuid4())
    logger.info("Generating skill %s from %s input", skill_id, request.input_type)

    # Process input into normalized text
    processed = await process_input(request.input_type, request.content, request.metadata)

    # Generate skill via Claude Agent SDK pipeline
    result = await generate_skill(processed, skill_id)

    # Validate
    validation = validate_skill_md(result.skill_md)

    # Resolve storage bucket
    bucket = await resolve_bucket(request.org_id, request.team_id)

    # Store to GCS
    gcs_path = await upload_skill(skill_id, result.skill_md, bucket, result.additional_files)

    return SkillGenerateResponse(
        skill_id=skill_id,
        name=result.name,
        status="valid" if validation.is_valid else "valid_with_warnings",
        gcs_path=gcs_path,
        skill_md_preview=result.skill_md[:500],
        validation_errors=validation.errors,
    )


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str, org_id: str | None = None, team_id: str | None = None):
    """Retrieve a generated skill by ID."""
    bucket = await resolve_bucket(org_id, team_id)
    content = await download_skill(skill_id, bucket)
    if content is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"skill_id": skill_id, "skill_md": content}


@router.get("/skills")
async def list_all_skills(org_id: str | None = None, team_id: str | None = None):
    """List all generated skills."""
    bucket = await resolve_bucket(org_id, team_id)
    skills = await list_skills(bucket)
    return {"skills": skills}


@router.post("/skills/validate", response_model=ValidationResult)
async def validate(request: SkillValidateRequest):
    """Validate a SKILL.md without storing it."""
    return validate_skill_md(request.skill_md)
