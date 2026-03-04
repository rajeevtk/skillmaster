from enum import Enum

from pydantic import BaseModel, Field


class InputType(str, Enum):
    PLAIN_TEXT = "plain_text"
    VOICE_TRANSCRIPT = "voice_transcript"
    GOOGLE_SLIDES = "google_slides"
    INTERVIEW = "interview"
    GENERIC = "generic"


class SkillGenerateRequest(BaseModel):
    input_type: InputType
    content: str = Field(..., description="Raw input content or URL/ID for external sources")
    org_id: str | None = Field(None, description="Organization ID for bucket resolution")
    team_id: str | None = Field(None, description="Team ID for bucket resolution")
    metadata: dict = Field(default_factory=dict, description="Additional metadata (e.g., slides ID, audio format)")


class SkillMetadata(BaseModel):
    skill_id: str
    name: str
    description: str
    gcs_path: str
    input_type: InputType
    org_id: str | None = None
    team_id: str | None = None


class SkillGenerateResponse(BaseModel):
    skill_id: str
    name: str
    status: str
    gcs_path: str
    skill_md_preview: str = Field(..., description="First 500 chars of generated SKILL.md")
    validation_errors: list[str] = Field(default_factory=list)


class SkillValidateRequest(BaseModel):
    skill_md: str = Field(..., description="SKILL.md content to validate")


class ValidationResult(BaseModel):
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
