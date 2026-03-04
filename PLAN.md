# Skill Master — Implementation Plan

## Overview

**Skill Master** is a Python service that generates Claude Agent Skills for GTM (Go-To-Market / Sales & Marketing) use cases from diverse input sources: plain text, voice transcripts, Google Slides, user interviews, and more.

It uses the **Claude Agent SDK** (`claude-code-sdk`) to orchestrate an agentic skill-creation pipeline, stores generated skills in **GCS**, and deploys as a containerized **Google Cloud Run** service via **Terraform**.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   REST API (FastAPI)                 │
│  POST /skills/generate   GET /skills/{id}           │
│  POST /skills/validate   GET /skills                │
└───────────┬─────────────────────────┬───────────────┘
            │                         │
    ┌───────▼────────┐      ┌────────▼──────────┐
    │ Input Processor │      │  Skill Retrieval  │
    │ (parse/extract) │      │  (GCS + NeonDB)   │
    │                 │      └───────────────────┘
    │ • PlainText     │
    │ • VoiceTranscr. │
    │ • GoogleSlides  │
    │ • Interview     │
    │ • Generic       │
    └───────┬─────────┘
            │ normalized text
    ┌───────▼─────────────────────────────┐
    │      Skill Generation Pipeline      │
    │  (Claude Agent SDK orchestration)   │
    │                                     │
    │  1. Analyze & classify input        │
    │  2. Extract GTM requirements        │
    │  3. Draft SKILL.md (best practices) │
    │  4. Validate structure & quality    │
    │  5. Store to GCS                    │
    └───────┬─────────────────────────────┘
            │
    ┌───────▼──────────┐
    │   Storage Layer   │
    │  GCS Bucket       │
    │  (configurable:   │
    │   env var or      │
    │   NeonDB lookup)  │
    └──────────────────┘
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12+ |
| Web Framework | FastAPI + uvicorn |
| Agent Orchestration | `claude-code-sdk` (Python) + Anthropic API |
| Cloud Storage | Google Cloud Storage (GCS) |
| Database | NeonDB (serverless Postgres) for org/team settings |
| Infrastructure | Terraform (Cloud Run, GCS, IAM, Artifact Registry) |
| Containerization | Docker |
| Audio Processing | `google-cloud-speech` or `openai/whisper` for voice transcripts |
| Slides Processing | `google-api-python-client` (Google Slides API) |
| Testing | pytest + pytest-asyncio |

---

## Project Structure

```
skillmaster/
├── CLAUDE.md                  # Project instructions for Claude
├── Agents.md                  # Agent & skill reference docs
├── PLAN.md                    # This plan
├── README.md                  # (optional, not auto-created)
├── pyproject.toml             # Python project config
├── Dockerfile                 # Container image
├── docker-compose.yml         # Local dev
├── .env.example               # Environment variable template
│
├── src/
│   └── skillmaster/
│       ├── __init__.py
│       ├── main.py            # FastAPI app entrypoint
│       ├── config.py          # Settings (env vars, defaults)
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py      # API endpoints
│       │   └── models.py      # Pydantic request/response models
│       │
│       ├── processors/
│       │   ├── __init__.py
│       │   ├── base.py        # BaseProcessor ABC
│       │   ├── plaintext.py   # Plain text input
│       │   ├── voice.py       # Voice transcript processing
│       │   ├── slides.py      # Google Slides extraction
│       │   ├── interview.py   # User interview parsing
│       │   └── generic.py     # Fallback for other inputs
│       │
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── orchestrator.py # Main pipeline (Agent SDK calls)
│       │   ├── analyzer.py     # Input analysis & classification
│       │   ├── generator.py    # SKILL.md generation
│       │   └── validator.py    # Skill structure validation
│       │
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── gcs.py         # GCS bucket operations
│       │   └── config_resolver.py  # Resolve bucket from env or NeonDB
│       │
│       └── db/
│           ├── __init__.py
│           ├── connection.py   # NeonDB connection pool
│           └── queries.py      # Org/team settings queries
│
├── skills/
│   └── skill-master/
│       ├── SKILL.md           # Skill Master's own skill definition
│       ├── GTM_TEMPLATES.md   # GTM-specific skill templates
│       └── VALIDATION.md      # Validation rules reference
│
├── terraform/
│   ├── main.tf               # Provider, Cloud Run, GCS
│   ├── variables.tf          # Input variables
│   ├── outputs.tf            # Output values
│   ├── cloud_run.tf          # Cloud Run service
│   ├── gcs.tf                # GCS bucket
│   ├── iam.tf                # Service account & permissions
│   ├── neondb.tf             # (optional) NeonDB connection config
│   └── terraform.tfvars.example
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_api.py
    ├── test_processors.py
    ├── test_pipeline.py
    ├── test_storage.py
    └── test_validator.py
```

---

## Phase 1: Foundation (Core Infrastructure)

### 1.1 Project Setup
- Initialize `pyproject.toml` with dependencies
- Create `Dockerfile` and `.env.example`
- Set up `src/skillmaster/config.py` with Pydantic Settings

### 1.2 FastAPI Application
- `src/skillmaster/main.py` — FastAPI app with health check
- `src/skillmaster/api/models.py` — Request/response Pydantic models:
  - `SkillGenerateRequest`: input_type, content, org_id, team_id, metadata
  - `SkillGenerateResponse`: skill_id, name, status, gcs_path, skill_md_preview
  - `SkillListResponse`: list of generated skills with metadata
- `src/skillmaster/api/routes.py` — Endpoints:
  - `POST /api/v1/skills/generate` — Generate a skill from input
  - `GET /api/v1/skills/{skill_id}` — Retrieve a generated skill
  - `GET /api/v1/skills` — List skills (with org/team filter)
  - `POST /api/v1/skills/validate` — Validate a SKILL.md without storing

### 1.3 Storage Layer
- `src/skillmaster/storage/gcs.py`:
  - `upload_skill(skill_id, skill_content, bucket_name)` → GCS path
  - `download_skill(skill_id, bucket_name)` → skill content
  - `list_skills(prefix, bucket_name)` → list of skill metadata
- `src/skillmaster/storage/config_resolver.py`:
  - `resolve_bucket(org_id, team_id)` → bucket name
  - Controlled by `SKILLMASTER_STORAGE_MODE` flag: `env` (use `SKILLMASTER_GCS_BUCKET` directly) or `db` (multi-tenant NeonDB lookup per org/team)
- `src/skillmaster/db/connection.py`: async connection pool to NeonDB
- `src/skillmaster/db/queries.py`:
  - `get_org_settings(org_id)` → bucket, preferences
  - `get_team_settings(org_id, team_id)` → team-specific overrides

### 1.4 Terraform Infrastructure
- GCS bucket with versioning enabled
- Cloud Run service (min 0, max 10 instances)
- Service account with GCS write + Anthropic API access
- Artifact Registry for Docker images
- Environment variables for configuration

---

## Phase 2: Input Processors

### 2.1 Base Processor Interface
```python
class BaseProcessor(ABC):
    @abstractmethod
    async def process(self, content: bytes | str, metadata: dict) -> ProcessedInput:
        """Extract structured text from input source."""
        ...

@dataclass
class ProcessedInput:
    raw_text: str
    source_type: str
    structured_sections: list[Section]  # title, body pairs
    metadata: dict  # source-specific metadata
```

### 2.2 Plain Text Processor
- Accept raw text descriptions of desired skills
- Basic structure detection (headings, lists, paragraphs)
- Pass through with minimal transformation

### 2.3 Voice Transcript Processor
- Accept pre-transcribed text OR audio files
- For audio: use Google Cloud Speech-to-Text or Whisper
- Speaker diarization to identify different speakers
- Clean up filler words, segment by topic

### 2.4 Google Slides Processor
- Use Google Slides API to extract slide content
- Parse speaker notes, titles, bullet points, descriptions
- Handle images by extracting alt text / descriptions
- Reconstruct narrative flow from slide order

### 2.5 Interview Processor
- Parse Q&A format transcripts
- Extract: pain points, workflows, requirements, terminology
- Identify GTM-specific patterns (sales process, marketing campaigns, customer segments)

### 2.6 Generic Processor
- Fallback for unstructured content
- Uses Claude to classify and extract relevant information

---

## Phase 3: Skill Generation Pipeline (Claude Agent SDK)

### 3.1 Orchestrator (`pipeline/orchestrator.py`)
The main pipeline uses `claude-code-sdk` to run an agentic loop:

```python
from claude_code_sdk import query, ClaudeCodeOptions

async def generate_skill(processed_input: ProcessedInput, config: SkillConfig) -> GeneratedSkill:
    # Step 1: Analyze input and determine skill type
    analysis = await analyze_input(processed_input)

    # Step 2: Generate SKILL.md using Claude with skill-creator pattern
    skill_md = await generate_skill_md(analysis, config)

    # Step 3: Validate the generated skill
    validation = validate_skill(skill_md)

    # Step 4: Store and return
    if validation.is_valid:
        skill_id = await store_skill(skill_md, config)
        return GeneratedSkill(id=skill_id, content=skill_md, validation=validation)
    else:
        # Re-generate with feedback
        skill_md = await regenerate_with_feedback(skill_md, validation, config)
        ...
```

### 3.2 Analyzer (`pipeline/analyzer.py`)
Uses Claude to:
- Classify the GTM use case (sales enablement, marketing automation, lead scoring, pipeline management, campaign planning, competitive intelligence, customer success, etc.)
- Extract key entities: personas, workflows, data sources, tools, metrics
- Determine appropriate skill complexity (simple instructions vs. multi-file with scripts)

### 3.3 Generator (`pipeline/generator.py`)
Uses Claude with the **skill-creator pattern**:
- Prompt includes: best practices (concise, progressive disclosure, proper YAML frontmatter)
- Generates SKILL.md with:
  - Proper `name` (lowercase, hyphens, gerund form preferred)
  - Specific `description` (third person, includes triggers)
  - Body under 500 lines
  - GTM-specific templates and workflows
  - Feedback loops for quality-critical tasks
- For complex skills: generates additional reference files

### 3.4 Validator (`pipeline/validator.py`)
Validates generated skills against best practices:
- YAML frontmatter: name ≤64 chars, lowercase/hyphens only, no reserved words
- Description: non-empty, ≤1024 chars, no XML tags, third person
- Body: ≤500 lines, no deeply nested references
- Consistent terminology
- No time-sensitive information
- File references are one level deep

---

## Phase 4: GTM Skill Templates & Patterns

### 4.1 Pre-built GTM Templates
Create `skills/skill-master/GTM_TEMPLATES.md` with templates for common GTM use cases:

- **Sales Enablement**: Battle cards, objection handling, demo scripts
- **Lead Scoring**: Qualification criteria, ICP matching, scoring models
- **Pipeline Management**: Stage definitions, forecasting, deal review
- **Campaign Planning**: Brief templates, audience targeting, channel strategy
- **Competitive Intelligence**: Competitor tracking, win/loss analysis
- **Customer Success**: Health scoring, QBR prep, expansion playbooks
- **Content Creation**: Blog posts, case studies, whitepapers from interviews
- **ABM (Account-Based Marketing)**: Account research, personalization

### 4.2 GTM-Specific Skill Patterns
- Include domain terminology (MQL, SQL, ARR, CAC, LTV, etc.)
- Structured workflows for common GTM processes
- Integration points with common GTM tools (Salesforce, HubSpot, Outreach, etc.)

---

## Phase 5: Testing & Validation

### 5.1 Unit Tests
- Processor tests (each input type)
- Validator tests (valid/invalid skills)
- Config resolver tests (env var vs. NeonDB)
- API endpoint tests

### 5.2 Integration Tests
- End-to-end skill generation from each input type
- GCS storage round-trip
- NeonDB query tests

### 5.3 Skill Quality Evaluation
- Create 3+ evaluation scenarios per GTM use case
- Test generated skills with Haiku, Sonnet, and Opus
- Verify skills follow all best practice checklist items

---

## Phase 6: Deployment & Operations

### 6.1 Docker Image
- Multi-stage build (builder + runtime)
- Python 3.12 slim base
- Non-root user
- Health check endpoint

### 6.2 Terraform Deployment
- `terraform init && terraform plan && terraform apply`
- Outputs: Cloud Run URL, GCS bucket name, service account email

### 6.3 CI/CD (Future)
- GitHub Actions for build, test, deploy
- Automated skill quality checks on PRs

---

## Implementation Order

| Order | Phase | Description | Dependencies |
|-------|-------|-------------|--------------|
| 1 | 1.1 | Project setup, pyproject.toml, Docker | None |
| 2 | 1.2 | FastAPI app + API models | 1 |
| 3 | 1.3 | GCS storage + config resolver + NeonDB | 1 |
| 4 | 1.4 | Terraform infrastructure | 1 |
| 5 | 2.1-2.2 | Base processor + plain text | 2 |
| 6 | 3.1-3.4 | Skill generation pipeline | 2, 5 |
| 7 | 2.3-2.6 | Remaining input processors | 5 |
| 8 | 4.1-4.2 | GTM templates & patterns | 6 |
| 9 | 5.x | Testing & validation | All above |
| 10 | 6.x | Deployment | All above |

---

## Key Environment Variables

| Variable | Description | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API key | (required) |
| `SKILLMASTER_STORAGE_MODE` | Storage mode: `env` = use GCS_BUCKET, `db` = NeonDB lookup | `env` |
| `SKILLMASTER_GCS_BUCKET` | GCS bucket name (used when STORAGE_MODE=env) | `skillmaster-skills` |
| `SKILLMASTER_GCS_PROJECT` | GCP project ID | (required for GCS) |
| `NEONDB_URL` | NeonDB connection string (required when STORAGE_MODE=db) | — |
| `SKILLMASTER_PORT` | Service port | `8080` |
| `SKILLMASTER_LOG_LEVEL` | Logging level | `INFO` |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account key path | (auto on Cloud Run) |

---

## Key Design Decisions

1. **Python over TypeScript**: Better GCP client libraries, audio processing, and Google Slides API support
2. **FastAPI**: Async-first, automatic OpenAPI docs, Pydantic validation
3. **NeonDB**: Serverless Postgres — scales to zero, no ops overhead, compatible with asyncpg
4. **Explicit storage mode flag** (`SKILLMASTER_STORAGE_MODE`): `env` for single-tenant (use env var bucket), `db` for multi-tenant NeonDB lookup — no implicit cascading
5. **Skill-creator pattern**: Follow the analyze → draft → validate → iterate loop from the official skill-creator skill
6. **Progressive disclosure in generated skills**: Main SKILL.md stays concise, reference files for details
7. **GTM focus**: Templates and domain knowledge baked into the generation prompts, not hard-coded in output
