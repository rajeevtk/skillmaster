import re

from skillmaster.api.models import ValidationResult

RESERVED_WORDS = {"anthropic", "claude"}
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_BODY_LINES = 500
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def validate_skill_md(skill_md: str) -> ValidationResult:
    """Validate a SKILL.md against Anthropic's skill authoring best practices."""
    errors: list[str] = []
    warnings: list[str] = []

    # Check frontmatter exists
    frontmatter_match = re.search(r"^---\s*\n(.+?)\n---", skill_md, re.DOTALL)
    if not frontmatter_match:
        errors.append("Missing YAML frontmatter (must start with --- and end with ---)")
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    frontmatter = frontmatter_match.group(1)
    body = skill_md[frontmatter_match.end():].strip()

    # Parse frontmatter fields
    name = ""
    description = ""
    for line in frontmatter.split("\n"):
        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip('"').strip("'")

    # Validate name
    if not name:
        errors.append("Missing 'name' field in frontmatter")
    else:
        if len(name) > MAX_NAME_LENGTH:
            errors.append(f"Name exceeds {MAX_NAME_LENGTH} characters: {len(name)}")
        if not NAME_PATTERN.match(name):
            errors.append(f"Name must be lowercase letters, numbers, and hyphens only: '{name}'")
        if any(word in name for word in RESERVED_WORDS):
            errors.append(f"Name contains reserved word: '{name}'")
        if "<" in name or ">" in name:
            errors.append("Name must not contain XML tags")

    # Validate description
    if not description:
        errors.append("Missing 'description' field in frontmatter")
    else:
        if len(description) > MAX_DESCRIPTION_LENGTH:
            errors.append(f"Description exceeds {MAX_DESCRIPTION_LENGTH} characters: {len(description)}")
        if "<" in description and ">" in description:
            errors.append("Description must not contain XML tags")
        # Check third person
        first_person_patterns = [r"\bI can\b", r"\bI will\b", r"\bI help\b", r"\byou can\b", r"\byou should\b"]
        for pattern in first_person_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                warnings.append(f"Description should use third person (found: '{pattern.strip(chr(92)).strip('b')}')")
                break

    # Validate body
    body_lines = body.split("\n")
    if len(body_lines) > MAX_BODY_LINES:
        errors.append(f"Body exceeds {MAX_BODY_LINES} lines: {len(body_lines)}")

    # Check for deeply nested references (more than 1 level)
    ref_files = re.findall(r"\[.*?\]\((\S+\.md)\)", body)
    if len(ref_files) > 10:
        warnings.append(f"Many file references ({len(ref_files)}). Ensure they are one level deep from SKILL.md.")

    # Check for time-sensitive language
    time_patterns = [r"before \w+ 20\d{2}", r"after \w+ 20\d{2}", r"as of 20\d{2}", r"starting 20\d{2}"]
    for pattern in time_patterns:
        if re.search(pattern, body, re.IGNORECASE):
            warnings.append("Body may contain time-sensitive information")
            break

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
