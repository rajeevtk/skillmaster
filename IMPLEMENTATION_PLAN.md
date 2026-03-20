# Skill Whisperer — Implementation Plan

This document breaks down the Skill Whisperer service into concrete implementation phases. Each phase delivers a working, testable system.

Reminder: Skill Whisperer produces tagged skill bundles and writes them to GCS. It does not manage skill lifecycle, deploy to agents, or provision infrastructure. See SPEC.md for scope boundaries.

---

## Phase 1 — MVP: Google Docs to Tagged Skill Bundle

**Outcome:** A user shares a Google Doc or Slide deck with the service account. The service detects the share, extracts content, generates a validated skill definition, tags it with the ownership hierarchy and metadata, and writes it to GCS.

---

### Step 1.1 — Project Scaffold

Create the project from scratch:

```
skill-whisperer/
├── src/
│   └── skill_whisperer/
│       ├── __init__.py
│       ├── main.py                    # FastAPI app, lifespan, health endpoint
│       ├── config.py                  # Pydantic Settings, all env vars
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py              # POST /generate, GET /skills/{id}
│       │   ├── webhooks.py            # POST /webhooks/drive
│       │   └── models.py             # Request/response Pydantic models
│       ├── extractors/
│       │   ├── __init__.py            # ExtractorRouter, ProcessedContent dataclass
│       │   ├── google_docs.py         # Google Docs API extractor
│       │   └── google_slides.py       # Google Slides API extractor
│       ├── pipeline/
│       │   ├── __init__.py            # SkillBundle dataclass
│       │   ├── orchestrator.py        # Runs extract → analyze → generate → validate → output
│       │   ├── analyzer.py            # Claude-based classification + auto-tagging
│       │   ├── generator.py           # Claude-based SKILL.md generation
│       │   └── validator.py           # Structural + content validation
│       ├── tagging/
│       │   ├── __init__.py
│       │   ├── models.py             # Ownership, TagEnvelope dataclasses
│       │   └── resolver.py           # Merges ownership + auto-tags + user-tags + project defaults
│       ├── output/
│       │   ├── __init__.py
│       │   └── gcs.py                 # Write skill bundle + metadata.json to GCS
│       ├── db/
│       │   ├── __init__.py
│       │   ├── connection.py          # AlloyDB async connection pool
│       │   ├── queries.py             # SQL queries for orgs, projects, skill_outputs, events
│       │   └── migrations/
│       │       └── 001_initial.sql    # Schema creation
│       └── observability.py           # Structured logging, correlation IDs, stage tracing
├── tests/
│   ├── conftest.py
│   ├── test_extractors.py
│   ├── test_pipeline.py
│   ├── test_validator.py
│   ├── test_tagging.py
│   ├── test_webhooks.py
│   └── test_output.py
├── Dockerfile
├── pyproject.toml
├── .env.example
└── CLAUDE.md
```

**Key decisions:**
- Package name: `skill_whisperer`
- `extractors/` — input-side, pluggable per source type
- `tagging/` — dedicated module for the ownership + metadata tag system
- `output/` — not `storage/`, not `deploy/` — this is write-only output
- `pipeline/` — the core processing stages
- No `terraform/` directory — infrastructure is a separate concern

**Config (env vars):**
```
ANTHROPIC_API_KEY              — Claude API access
GOOGLE_APPLICATION_CREDENTIALS — Service account key for Drive/Docs/Slides API
GCS_BUCKET                     — Output bucket for skill bundles
GCP_PROJECT                    — GCP project ID
ALLOYDB_URL                    — AlloyDB connection string
DRIVE_WEBHOOK_SECRET           — Shared secret for webhook verification
LOG_LEVEL                      — INFO default
PORT                           — 8080 default
```

**Dependencies:**
- `fastapi`, `uvicorn[standard]`
- `pydantic`, `pydantic-settings`
- `anthropic` (Claude API)
- `google-cloud-storage`
- `google-api-python-client`, `google-auth` (Drive, Docs, Slides APIs)
- `asyncpg` (AlloyDB/PostgreSQL)
- `pyyaml`, `python-multipart`
- Dev: `pytest`, `pytest-asyncio`, `httpx`, `ruff`

---

### Step 1.2 — Tagging Model

**Files:** `src/skill_whisperer/tagging/models.py`, `src/skill_whisperer/tagging/resolver.py`

This is the core contract between Skill Whisperer and every downstream service. Build it first.

**Data model:**

```python
@dataclass
class Ownership:
    org: str        # e.g., "acme-corp"
    project: str    # e.g., "enterprise-west-q2"
    user: str       # e.g., "jdoe@acme.com"

@dataclass
class TagEnvelope:
    skill_id: str
    ownership: Ownership
    tags: dict[str, str]         # flat key-value pairs
    validation: ValidationResult | None
```

**Auto-populated tags** (set by the analyzer):
- `source_type`, `source_ref`, `gtm_use_case`, `complexity`, `structure_type`, `generated_at`, `pipeline_version`

**Tag resolver** (`resolver.py`):
1. Start with project default tags (from `projects.default_tags` in AlloyDB)
2. Layer on auto-populated tags from the analyzer
3. Layer on user-supplied tags from the API request
4. Later wins (user-supplied overrides auto, auto overrides project defaults)
5. Validate: `ownership.org`, `ownership.project`, `ownership.user` must all be non-empty
6. Return `TagEnvelope`

**Tests:**
- Three-level hierarchy must be complete (reject if any level missing)
- User-supplied tags override auto tags
- Project default tags are applied
- Tag keys are normalized (lowercase, hyphens)

---

### Step 1.3 — Google Docs Extractor

**File:** `src/skill_whisperer/extractors/google_docs.py`

- Takes a Google Doc document ID
- Calls `docs.documents.get()` to retrieve the full document
- Walks the document body, extracting:
  - Headings (HEADING_1 through HEADING_6) → section titles
  - Paragraphs → section body text
  - Bulleted and numbered lists → preserved as markdown lists
  - Tables → converted to markdown tables
  - Inline images → downloaded, added to assets list
- Returns a `ProcessedContent` object

**ProcessedContent contract** (defined in `extractors/__init__.py`):
```python
@dataclass
class Section:
    title: str
    body: str
    type: str  # "heading", "list", "table", "text"

@dataclass
class Asset:
    name: str
    asset_type: str  # "image", "table", "chart"
    content: bytes | str
    content_type: str  # MIME type

@dataclass
class ProcessedContent:
    source_type: str
    raw_text: str
    sections: list[Section]
    assets: list[Asset]
    metadata: dict  # document_id, title, last_editor, revision_id
```

**Tests:**
- Extracts headings and body text from a mock document structure
- Handles documents with no headings (falls back to single section)
- Converts lists to markdown format
- Handles empty documents gracefully

---

### Step 1.4 — Google Slides Extractor

**File:** `src/skill_whisperer/extractors/google_slides.py`

- Takes a Google Slides presentation ID
- Calls `slides.presentations.get()` to retrieve all slides
- For each slide, extracts:
  - Slide title (from title placeholder)
  - Body text and bullet points
  - Speaker notes (high-signal — the user's verbal explanation)
  - Images (downloaded, added to assets)
- Reconstructs slides in order as a narrative flow
- Each slide becomes a `Section`

**Tests:**
- Extracts title and body from mock slides
- Speaker notes are captured and labeled
- Slide ordering is preserved
- Handles slides with only images

---

### Step 1.5 — Extractor Router

**File:** `src/skill_whisperer/extractors/__init__.py`

Simple dispatch:

```python
async def extract(source_type: str, source_ref: str, credentials) -> ProcessedContent:
    if source_type == "google_docs":
        return await google_docs_extract(source_ref, credentials)
    elif source_type == "google_slides":
        return await google_slides_extract(source_ref, credentials)
    else:
        raise ValueError(f"Unknown source type: {source_type}")
```

Extension point for future sources.

---

### Step 1.6 — Analysis Stage

**File:** `src/skill_whisperer/pipeline/analyzer.py`

- Takes `ProcessedContent`, sends it to Claude for classification
- Claude identifies:
  - **GTM use case** — demand generation, account planning, objection handling, competitive intel, customer success, campaign execution, territory planning, stakeholder management, etc.
  - **Complexity** — simple (single reference doc), moderate (multi-section guide), complex (multi-step workflow with decision points)
  - **Content structure** — playbook, reference guide, decision tree, workflow checklist, profile collection
  - **Named entities** — people, companies, products, processes
  - **Suggested skill name and description**
- Returns auto-tag values along with the analysis

**Output:**
```python
@dataclass
class AnalysisResult:
    use_case: str
    complexity: str
    structure_type: str
    entities: list[dict]
    suggested_name: str
    suggested_description: str
    key_topics: list[str]
    auto_tags: dict[str, str]   # gtm_use_case, complexity, structure_type
    raw_analysis: dict
```

---

### Step 1.7 — Generation Stage

**File:** `src/skill_whisperer/pipeline/generator.py`

- Takes `ProcessedContent` + `AnalysisResult`
- Sends to Claude with a system prompt for agent skill definition authoring
- Generates:
  - `SKILL.md` — valid YAML frontmatter + body under 500 lines
  - Asset files — for complex content, splits into referenced files
- Uses progressive disclosure: SKILL.md is the entry point, asset files hold the detail
- Supports re-generation with validation feedback (max 2 retries)

**Output:**
```python
@dataclass
class SkillBundle:
    skill_id: str
    name: str
    description: str
    skill_md: str
    additional_files: dict[str, str]  # relative_path → content
    analysis: AnalysisResult
    tag_envelope: TagEnvelope         # resolved tags attached to the bundle
```

---

### Step 1.8 — Validation Stage

**File:** `src/skill_whisperer/pipeline/validator.py`

**Checks (all run, results aggregated):**

| Check | Type | Rule |
|-------|------|------|
| YAML frontmatter present | Error | Must have `---` delimited frontmatter |
| `name` field | Error | Required, ≤64 chars, lowercase + hyphens |
| `description` field | Error | Required, ≤1024 chars |
| No reserved words in name | Error | Cannot contain "anthropic" or "claude" |
| Body length | Error | ≤500 lines |
| No XML tags in frontmatter | Error | Prevents injection |
| Reference depth | Warning | Referenced files should be one level deep |
| Third-person voice | Warning | Skill descriptions should use third person |
| No time-sensitive language | Warning | Avoid "currently", "as of 2024", etc. |
| Consistent terminology | Warning | Flag mixed terms for same concept |

**Output:**
```python
@dataclass
class ValidationResult:
    is_valid: bool       # True if zero errors (warnings OK)
    errors: list[str]
    warnings: list[str]
```

---

### Step 1.9 — Pipeline Orchestrator

**File:** `src/skill_whisperer/pipeline/orchestrator.py`

Wires the stages together:

```
extract(source_type, source_ref) → ProcessedContent
    │
    ▼
analyze(processed_content) → AnalysisResult
    │
    ▼
resolve_tags(ownership, analysis.auto_tags, user_tags, project_defaults) → TagEnvelope
    │
    ▼
generate(processed_content, analysis) → SkillBundle (with tag_envelope attached)
    │
    ▼
validate(skill_bundle.skill_md) → ValidationResult
    │
    ├── if errors and retries < 2: re-generate with feedback → loop back to validate
    │
    ▼
write_output(skill_bundle) → gcs_path
```

Each stage is wrapped with the observability decorator that logs start/end/duration and writes to `processing_events`.

---

### Step 1.10 — GCS Output

**File:** `src/skill_whisperer/output/gcs.py`

```python
async def write_skill_bundle(bundle: SkillBundle, bucket: str) -> str:
    """
    Writes to GCS using the ownership hierarchy as the path:

      gs://{bucket}/{org}/{project}/{skill_id}/SKILL.md
      gs://{bucket}/{org}/{project}/{skill_id}/metadata.json
      gs://{bucket}/{org}/{project}/{skill_id}/assets/{filename}

    metadata.json contains the full TagEnvelope (ownership + tags + validation).

    Returns the GCS path prefix.
    """
```

This is a write-only interface. Skill Whisperer never reads back from this path. No `download_skill`, no `list_skills` at the GCS level — that's downstream's job.

The only read Skill Whisperer does is from AlloyDB `skill_outputs` for dedup.

---

### Step 1.11 — AlloyDB Layer

**File:** `src/skill_whisperer/db/connection.py`
- `asyncpg` connection pool to AlloyDB
- Supports AlloyDB Auth Proxy
- Pool: min 1, max 10

**File:** `src/skill_whisperer/db/queries.py`
- `get_org(org_id) → row`
- `get_project(project_id) → row` (includes `default_tags`)
- `get_org_bucket(org_id) → str`
- `record_skill_output(skill_id, org_id, project_id, user_email, name, description, source_type, source_ref, source_revision, gcs_path, tags, validation_result)`
- `skill_already_processed(source_ref, source_revision) → bool` (dedup check)
- `log_event(skill_id, stage, status, duration_ms, details)`

**File:** `src/skill_whisperer/db/migrations/001_initial.sql`
- Creates: `organizations`, `projects`, `skill_outputs`, `processing_events`
- No `policy_rules` yet (Phase 2)

---

### Step 1.12 — Google Drive Webhook

**File:** `src/skill_whisperer/api/webhooks.py`

`POST /api/v1/webhooks/drive` — receives Drive push notifications
- Validates notification (channel token matches `DRIVE_WEBHOOK_SECRET`)
- Ignores `sync` messages (initial handshake)
- On `change` or `update`:
  1. Gets file ID from `X-Goog-Resource-ID`
  2. Calls Drive API for file metadata (MIME type, title, sharing info, last modifier email)
  3. Determines source type from MIME type
  4. Resolves ownership: org + project from configuration, user from the last modifier email
  5. Dedup check: `skill_already_processed(source_ref, source_revision)`
  6. Runs the pipeline orchestrator
  7. Returns 200

`POST /api/v1/webhooks/drive/register` — registers a Drive watch
- Takes a file ID or folder ID
- Calls `files.watch()` to set up push notifications

---

### Step 1.13 — API Routes

**File:** `src/skill_whisperer/api/routes.py`

`POST /api/v1/skills/generate` — manual trigger
```json
{
  "source_type": "google_docs",
  "source_ref": "document_id",
  "ownership": {
    "org": "acme-corp",
    "project": "enterprise-west-q2",
    "user": "jdoe@acme.com"
  },
  "tags": {
    "account": "globex-industries",
    "region": "west"
  }
}
```
Returns:
```json
{
  "skill_id": "uuid",
  "name": "handling-globex-objections",
  "gcs_path": "gs://bucket/acme-corp/enterprise-west-q2/uuid/",
  "tag_envelope": { ... },
  "validation": { "is_valid": true, "errors": [], "warnings": [] }
}
```

`GET /api/v1/skills/{skill_id}` — retrieve output record
- Returns the `skill_outputs` row from AlloyDB (including tags snapshot)
- Does NOT read from GCS

`POST /api/v1/skills/validate` — validate without producing output
- Body: `{ "skill_md": "..." }`
- Returns: `{ "is_valid": true, "errors": [], "warnings": [] }`

---

### Step 1.14 — Observability

**File:** `src/skill_whisperer/observability.py`

- **Structured JSON logger:** Every log line includes `correlation_id`, `stage`, `org_id`, `project_id`, `skill_id`
- **Correlation ID middleware:** Assigns a UUID to each request, threads through all stages
- **Stage tracing decorator:**
  ```python
  @trace_stage("analyze")
  async def analyze(content: ProcessedContent) -> AnalysisResult:
      ...
  ```
  Logs start/end, measures duration, writes to `processing_events`

---

### Step 1.15 — Tests

| Test file | What it covers |
|-----------|---------------|
| `test_tagging.py` | Ownership validation, tag merging precedence, project defaults, key normalization |
| `test_extractors.py` | Docs heading extraction, Slides narrative flow, empty doc handling |
| `test_pipeline.py` | Orchestrator wires stages correctly, retry on validation failure, tags attached to bundle |
| `test_validator.py` | All validation rules (frontmatter, name, description, body length, reserved words) |
| `test_webhooks.py` | Drive notification parsing, dedup logic, MIME type routing, ownership resolution |
| `test_output.py` | GCS path uses ownership hierarchy, metadata.json contains full tag envelope |

---

### Phase 1 — Implementation Order

```
Week 1: Foundation
  ├── 1.1  Project scaffold, config, FastAPI app shell, health endpoint
  ├── 1.2  Tagging model + resolver (core contract, no dependencies)
  ├── 1.11 AlloyDB connection + migrations
  ├── 1.14 Observability (logging, tracing decorator)
  └── 1.8  Validator (no external dependencies, easy to test first)

Week 2: Extractors + Pipeline
  ├── 1.3  Google Docs extractor
  ├── 1.4  Google Slides extractor
  ├── 1.5  Extractor router
  ├── 1.6  Analyzer (Claude integration + auto-tagging)
  └── 1.7  Generator (Claude integration)

Week 3: Wiring + Output
  ├── 1.9  Pipeline orchestrator (wire everything, integrate tag resolver)
  ├── 1.10 GCS output (write-only, metadata.json with tag envelope)
  ├── 1.13 API routes
  ├── 1.12 Drive webhook receiver
  └── 1.15 Tests for all components

Week 4: Polish + E2E
  ├── Dockerfile
  ├── End-to-end test: share Google Doc → tagged skill bundle in GCS
  ├── Verify metadata.json tag envelope is correct
  └── Bug fixes and hardening
```

### Phase 1 — Exit Criteria

- [ ] Share a Google Doc → tagged skill bundle appears in GCS with correct `{org}/{project}/{skill_id}/` path
- [ ] Share a Google Slides deck → same result
- [ ] `POST /api/v1/skills/generate` with ownership + tags produces a valid, tagged skill bundle
- [ ] `metadata.json` contains complete tag envelope (ownership + auto-tags + user-tags)
- [ ] Generated SKILL.md passes all structural validation rules
- [ ] Auto-tags (`gtm_use_case`, `complexity`, `structure_type`) are populated by the analyzer
- [ ] User-supplied tags override auto-tags when keys conflict
- [ ] Project default tags are applied from AlloyDB `projects.default_tags`
- [ ] Dedup: re-sharing the same doc at the same revision does not produce a duplicate
- [ ] Processing events are logged for each pipeline stage
- [ ] All tests pass
- [ ] Structured JSON logs include correlation IDs

---

## Phase 2 — Organization Policies & Compliance

**Outcome:** Organizations define custom rules (banned terms, required sections, terminology, PII detection). Skills are checked against these rules before output.

### Steps

**2.1 — Policy engine** (`src/skill_whisperer/pipeline/policy_engine.py`)
- Load rules from AlloyDB `policy_rules` table
- Built-in rule types: `banned_terms`, `required_sections`, `terminology_map`, `style_rules`, `pii_detection`
- Each rule returns pass/fail + details
- Rules can be `blocking` or `warning`

**2.2 — Policy CRUD API** (`src/skill_whisperer/api/policy_routes.py`)
- `POST /api/v1/orgs/{org_id}/policies`
- `GET /api/v1/orgs/{org_id}/policies`
- `PUT /api/v1/orgs/{org_id}/policies/{rule_id}`
- `DELETE /api/v1/orgs/{org_id}/policies/{rule_id}`

**2.3 — Pipeline integration**
- Add policy check stage between validate and output in orchestrator
- Blocking violations prevent output
- Policy results included in `metadata.json` validation section
- All results recorded in `processing_events`

**2.4 — Compliance audit API**
- `GET /api/v1/skills/{skill_id}/audit` — full processing + compliance history from `processing_events`

### Phase 2 — Exit Criteria

- [ ] Create a "banned_terms" policy → skill containing banned term is blocked from output
- [ ] Create a "required_sections" policy → skill missing required section is blocked
- [ ] Warnings do not block output
- [ ] Policy check results appear in `metadata.json`
- [ ] Audit endpoint shows full compliance trail
- [ ] Policy CRUD works end-to-end

---

## Phase 3 — Voice Agent Pipeline

**Outcome:** A voice agent conducts a structured interview with the user. The conversation is transcribed and processed into a tagged skill bundle.

### Steps

**3.1 — Voice session manager** (`src/skill_whisperer/ingestion/voice_session.py`)
- WebSocket endpoint for real-time audio streaming
- Session lifecycle: start → stream audio → end → trigger pipeline
- Session state stored in AlloyDB

**3.2 — Voice extractor** (`src/skill_whisperer/extractors/voice.py`)
- Uses Google Cloud Speech-to-Text v2 for transcription
- Speaker diarization to identify interviewer vs. user
- Cleans filler words, normalizes text
- Produces `ProcessedContent` like any other extractor
- Sets `source_type` tag to `voice`

**3.3 — Interview agent** (`src/skill_whisperer/extractors/interview_agent.py`)
- Claude-powered agent that guides the conversation
- Asks follow-up questions based on detected GTM use case
- Knows when it has enough information to generate a skill
- Produces structured Q&A that feeds into the standard pipeline

### Phase 3 — Exit Criteria

- [ ] User can start a voice session via WebSocket
- [ ] Agent asks relevant follow-up questions
- [ ] Completed session produces a valid tagged skill bundle in GCS
- [ ] Voice-generated skills pass all validation
- [ ] Tag envelope includes `source_type: voice`

---

## Phase 4 — Event-Driven Pipeline

**Outcome:** Ingestion is decoupled from processing via Pub/Sub. Enables async processing, retries, and dead-letter handling.

### Steps

**4.1 — Pub/Sub integration**
- Topics: `skill-ingest-events`, `skill-dlq`
- Webhook handler publishes to Pub/Sub instead of calling pipeline directly
- Subscriber pulls from ingest topic, runs pipeline

**4.2 — Async API**
- `POST /api/v1/skills/generate` returns 202 + job ID
- `GET /api/v1/jobs/{job_id}` — poll for status

**4.3 — Retry + DLQ**
- Exponential backoff, max 3 attempts
- Failed events land in `skill-dlq` for manual review

---

## Phase 5 — Multi-Experience Endpoints

**Outcome:** Slack, email, and browser extension feed into the same pipeline.

**5.1 — Slack bot** — paste content or share a doc link → triggers pipeline
**5.2 — Email ingestion** — forward to `skills@domain` → email body processed
**5.3 — Chrome extension** — highlight text, send to Skill Whisperer

Each is a thin adapter that produces an ingest event with ownership tags and publishes to Pub/Sub. The core pipeline is unchanged.
