from skillmaster.pipeline.validator import validate_skill_md


def test_valid_skill():
    skill_md = """---
name: scoring-leads
description: Evaluates inbound leads against ICP criteria. Use when qualifying new MQLs.
---

# Scoring Leads

## Quick start
Evaluate leads.
"""
    result = validate_skill_md(skill_md)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_missing_frontmatter():
    result = validate_skill_md("# No frontmatter here")
    assert result.is_valid is False
    assert any("frontmatter" in e.lower() for e in result.errors)


def test_missing_name():
    skill_md = """---
description: Does something useful.
---
# Content
"""
    result = validate_skill_md(skill_md)
    assert result.is_valid is False
    assert any("name" in e.lower() for e in result.errors)


def test_missing_description():
    skill_md = """---
name: valid-name
---
# Content
"""
    result = validate_skill_md(skill_md)
    assert result.is_valid is False
    assert any("description" in e.lower() for e in result.errors)


def test_name_too_long():
    long_name = "a" * 65
    skill_md = f"""---
name: {long_name}
description: A valid description.
---
# Content
"""
    result = validate_skill_md(skill_md)
    assert result.is_valid is False
    assert any("64" in e for e in result.errors)


def test_name_invalid_chars():
    skill_md = """---
name: Invalid_Name
description: A valid description.
---
# Content
"""
    result = validate_skill_md(skill_md)
    assert result.is_valid is False
    assert any("lowercase" in e.lower() for e in result.errors)


def test_name_reserved_word():
    skill_md = """---
name: anthropic-helper
description: A valid description.
---
# Content
"""
    result = validate_skill_md(skill_md)
    assert result.is_valid is False
    assert any("reserved" in e.lower() for e in result.errors)


def test_body_too_long():
    body = "\n".join([f"Line {i}" for i in range(501)])
    skill_md = f"""---
name: valid-name
description: A valid description.
---
{body}
"""
    result = validate_skill_md(skill_md)
    assert result.is_valid is False
    assert any("500" in e for e in result.errors)


def test_first_person_warning():
    skill_md = """---
name: valid-name
description: I can help you with leads.
---
# Content
"""
    result = validate_skill_md(skill_md)
    assert any("third person" in w.lower() for w in result.warnings)
