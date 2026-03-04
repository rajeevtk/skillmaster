import logging
import re

import anthropic

from skillmaster.config import settings
from skillmaster.pipeline import GeneratedSkill
from skillmaster.pipeline.analyzer import InputAnalysis

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a Claude Agent Skill authoring expert. You create SKILL.md files that follow Anthropic's best practices:

- YAML frontmatter with `name` (lowercase, hyphens, ≤64 chars, gerund form preferred) and `description` (third person, ≤1024 chars, includes what it does AND when to use it)
- Body under 500 lines, concise — only include what Claude doesn't already know
- Progressive disclosure: reference additional files for details
- Consistent terminology, no time-sensitive info
- Concrete examples over abstract descriptions
- Workflows with checklists for complex tasks
- Feedback loops for quality-critical operations

You specialize in GTM (Go-To-Market / Sales & Marketing) skills.
"""

GENERATION_PROMPT = """\
Generate a SKILL.md file for this GTM use case.

Use case: {use_case}
Title: {title}
Summary: {summary}
Key entities: {entities}
Target personas: {personas}
Workflows: {workflows}
Tools mentioned: {tools}
Complexity: {complexity}

Source material:
{raw_input}

Requirements:
1. Output ONLY the SKILL.md content (YAML frontmatter + markdown body)
2. Name should use gerund form with hyphens (e.g., "scoring-leads", "managing-pipeline")
3. Description must be third person, specific, include both what and when
4. Body must be under 500 lines
5. Include concrete examples relevant to the use case
6. For complex skills, mention additional reference files that should be created
{feedback_section}
"""


async def generate_skill_md(
    analysis: InputAnalysis,
    skill_id: str,
    feedback: list[str] | None = None,
) -> GeneratedSkill:
    """Generate a SKILL.md using the Claude API."""
    feedback_section = ""
    if feedback:
        feedback_section = "\nFix these validation issues from the previous attempt:\n"
        feedback_section += "\n".join(f"- {e}" for e in feedback)

    prompt = GENERATION_PROMPT.format(
        use_case=analysis.use_case,
        title=analysis.title,
        summary=analysis.summary,
        entities=", ".join(analysis.key_entities),
        personas=", ".join(analysis.personas),
        workflows=", ".join(analysis.workflows),
        tools=", ".join(analysis.tools_mentioned),
        complexity=analysis.complexity,
        raw_input=analysis.raw_input[:6000],
        feedback_section=feedback_section,
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    skill_md = response.content[0].text

    # Strip any markdown code fences the model may have wrapped around the output
    skill_md = re.sub(r"^```(?:markdown|yaml)?\s*\n", "", skill_md)
    skill_md = re.sub(r"\n```\s*$", "", skill_md)

    # Extract name and description from frontmatter
    name, description = _extract_frontmatter(skill_md)

    return GeneratedSkill(
        skill_id=skill_id,
        name=name,
        description=description,
        skill_md=skill_md,
    )


def _extract_frontmatter(skill_md: str) -> tuple[str, str]:
    """Extract name and description from YAML frontmatter."""
    name = "generated-skill"
    description = ""

    frontmatter_match = re.search(r"^---\s*\n(.+?)\n---", skill_md, re.DOTALL)
    if frontmatter_match:
        for line in frontmatter_match.group(1).split("\n"):
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip('"').strip("'")

    return name, description
