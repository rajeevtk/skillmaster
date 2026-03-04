---
name: generating-gtm-skills
description: Generates Claude Agent Skills for GTM (Go-To-Market) use cases including sales enablement, lead scoring, pipeline management, campaign planning, and competitive intelligence. Use when creating new skills from plain text descriptions, voice transcripts, Google Slides presentations, user interviews, or other unstructured inputs about sales and marketing workflows.
---

# Generating GTM Skills

## Quick start

Generate a skill from a plain text description of a GTM workflow:

```python
import httpx

response = httpx.post("http://localhost:8080/api/v1/skills/generate", json={
    "input_type": "plain_text",
    "content": "We need a skill that helps SDRs qualify leads using BANT criteria...",
    "org_id": "my-org",
})
print(response.json()["skill_md_preview"])
```

## Skill generation workflow

Copy this checklist and track your progress:

```
Skill Generation Progress:
- [ ] Step 1: Gather input (text, transcript, slides, interview)
- [ ] Step 2: Classify the GTM use case
- [ ] Step 3: Extract requirements (personas, workflows, tools, metrics)
- [ ] Step 4: Draft SKILL.md with proper frontmatter
- [ ] Step 5: Validate against best practices
- [ ] Step 6: Store to GCS
```

**Step 1: Gather input**
Accept one of: plain text, voice transcript, Google Slides content, or interview notes. The input describes a GTM workflow or process that should become a reusable skill.

**Step 2: Classify the GTM use case**
Determine which category applies:
- Sales enablement (battle cards, objection handling, demo scripts)
- Lead scoring (qualification criteria, ICP matching)
- Pipeline management (stage definitions, forecasting, deal review)
- Campaign planning (briefs, audience targeting, channel strategy)
- Competitive intelligence (competitor tracking, win/loss analysis)
- Customer success (health scoring, QBR prep, expansion playbooks)
- Content creation (blog posts, case studies from interviews)
- ABM (account research, personalization)

**Step 3: Extract requirements**
Identify key entities, target personas, workflows, tools (Salesforce, HubSpot, Outreach, Gong, etc.), and success metrics (MQL, SQL, ARR, CAC, LTV).

**Step 4: Draft SKILL.md**
Generate a SKILL.md following these rules:
- `name`: gerund form, lowercase + hyphens, ≤64 chars
- `description`: third person, specific, includes what + when triggers
- Body: under 500 lines, concise, progressive disclosure
- Include concrete examples relevant to the GTM use case

**Step 5: Validate**
Check against the rules in [VALIDATION.md](VALIDATION.md). Fix any errors and re-validate.

**Step 6: Store**
Upload to GCS bucket (resolved from env var or org/team settings in NeonDB).

## Supported input types

| Input | Description |
|---|---|
| `plain_text` | Free-form text describing the GTM workflow |
| `voice_transcript` | Meeting/call transcript (pre-transcribed or audio) |
| `google_slides` | Presentation content (text or Slides API ID) |
| `interview` | Q&A format user interview notes |
| `generic` | Any other unstructured input |

## GTM templates

See [GTM_TEMPLATES.md](GTM_TEMPLATES.md) for pre-built templates by use case.

## Validation rules

See [VALIDATION.md](VALIDATION.md) for the complete validation checklist.
