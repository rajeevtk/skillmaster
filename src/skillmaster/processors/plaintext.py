import re

from skillmaster.processors import ProcessedInput


async def process(content: str, metadata: dict) -> ProcessedInput:
    """Process plain text input. Detect structure from headings and lists."""
    sections = []
    current_title = "Overview"
    current_body_lines: list[str] = []

    for line in content.split("\n"):
        heading_match = re.match(r"^#{1,3}\s+(.+)$", line)
        if heading_match:
            if current_body_lines:
                sections.append({"title": current_title, "body": "\n".join(current_body_lines).strip()})
            current_title = heading_match.group(1)
            current_body_lines = []
        else:
            current_body_lines.append(line)

    if current_body_lines:
        sections.append({"title": current_title, "body": "\n".join(current_body_lines).strip()})

    return ProcessedInput(
        raw_text=content,
        source_type="plain_text",
        structured_sections=sections,
        metadata=metadata,
    )
