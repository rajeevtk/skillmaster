import logging

from skillmaster.pipeline import GeneratedSkill
from skillmaster.pipeline.analyzer import analyze_input
from skillmaster.pipeline.generator import generate_skill_md
from skillmaster.pipeline.validator import validate_skill_md
from skillmaster.processors import ProcessedInput

logger = logging.getLogger(__name__)

MAX_REGENERATION_ATTEMPTS = 2


async def generate_skill(processed: ProcessedInput, skill_id: str) -> GeneratedSkill:
    """Main skill generation pipeline.

    1. Analyze input to classify GTM use case and extract requirements
    2. Generate SKILL.md using Claude Agent SDK
    3. Validate against best practices
    4. Re-generate with feedback if validation fails
    """
    # Step 1: Analyze
    analysis = await analyze_input(processed)
    logger.info("Analyzed input: use_case=%s, complexity=%s", analysis.use_case, analysis.complexity)

    # Step 2: Generate
    result = await generate_skill_md(analysis, skill_id)

    # Step 3: Validate and iterate
    for attempt in range(MAX_REGENERATION_ATTEMPTS):
        validation = validate_skill_md(result.skill_md)
        if validation.is_valid:
            break
        logger.warning("Validation failed (attempt %d): %s", attempt + 1, validation.errors)
        result = await generate_skill_md(analysis, skill_id, feedback=validation.errors)

    return result
