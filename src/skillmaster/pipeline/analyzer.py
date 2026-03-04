import logging
from dataclasses import dataclass, field

import anthropic

from skillmaster.config import settings
from skillmaster.processors import ProcessedInput

logger = logging.getLogger(__name__)

GTM_USE_CASES = [
    "sales-enablement",
    "lead-scoring",
    "pipeline-management",
    "campaign-planning",
    "competitive-intelligence",
    "customer-success",
    "content-creation",
    "abm",
    "marketing-automation",
    "sales-operations",
    "general-gtm",
]


@dataclass
class InputAnalysis:
    use_case: str
    complexity: str  # "simple", "moderate", "complex"
    title: str
    summary: str
    key_entities: list[str] = field(default_factory=list)
    personas: list[str] = field(default_factory=list)
    workflows: list[str] = field(default_factory=list)
    tools_mentioned: list[str] = field(default_factory=list)
    raw_input: str = ""


ANALYSIS_PROMPT = """\
Analyze this input and extract GTM (Go-To-Market / Sales & Marketing) requirements for creating a Claude Agent Skill.

Input source type: {source_type}

Content:
{content}

Respond in this exact format (no markdown, no extra text):
USE_CASE: <one of: {use_cases}>
COMPLEXITY: <simple|moderate|complex>
TITLE: <short descriptive title, 3-6 words>
SUMMARY: <1-2 sentence summary of what the skill should do>
ENTITIES: <comma-separated key entities>
PERSONAS: <comma-separated target personas>
WORKFLOWS: <comma-separated workflows described>
TOOLS: <comma-separated tools/platforms mentioned>
"""


async def analyze_input(processed: ProcessedInput) -> InputAnalysis:
    """Use Claude to analyze and classify the input for skill generation."""
    content = processed.raw_text[:4000]  # Limit to avoid token bloat

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": ANALYSIS_PROMPT.format(
                source_type=processed.source_type,
                content=content,
                use_cases=", ".join(GTM_USE_CASES),
            ),
        }],
    )

    text = response.content[0].text
    return _parse_analysis(text, processed.raw_text)


def _parse_analysis(text: str, raw_input: str) -> InputAnalysis:
    """Parse the structured analysis response."""
    fields: dict[str, str] = {}
    for line in text.strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip().upper()] = value.strip()

    return InputAnalysis(
        use_case=fields.get("USE_CASE", "general-gtm"),
        complexity=fields.get("COMPLEXITY", "moderate"),
        title=fields.get("TITLE", "GTM Skill"),
        summary=fields.get("SUMMARY", ""),
        key_entities=[e.strip() for e in fields.get("ENTITIES", "").split(",") if e.strip()],
        personas=[p.strip() for p in fields.get("PERSONAS", "").split(",") if p.strip()],
        workflows=[w.strip() for w in fields.get("WORKFLOWS", "").split(",") if w.strip()],
        tools_mentioned=[t.strip() for t in fields.get("TOOLS", "").split(",") if t.strip()],
        raw_input=raw_input,
    )
