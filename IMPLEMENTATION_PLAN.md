# Skill Whisperer — Implementation Plan

This document breaks down the Skill Whisperer service into concrete implementation phases. Each phase delivers a working, testable system.

---

## Phase 1 — MVP: Google Docs to GCS

**Outcome:** A user shares a Google Doc or Slide deck with the service account. The service detects the share, extracts content, generates a validated skill definition, and deploys it to GCS where Poexis agents can read it.

---

### Step 1.1 — Project Scaffold

Create the project from scratch with the following structure:

```
skill-whisperer/
├── src/
│   └── skill_whisperer/
│       ├── __init__.py
│       ├── main.py                    # FastAPI app, lifespan, health endpoint
│       ├── config.py                  # Pydantic Settings, all env vars
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py              # POST /generate, GET /skills, GET /skills/{id}
│       │   ├── webhooks.py            # POST /webhooks/drive
│       │   └── models.py              # Request/response Pydantic models
│       ├── extractors/
│       │   ├── __init__.py            # ExtractorRouter, ProcessedContent dataclass
│       │   ├── google_docs.py         # Google Docs API extractor
│       │   └── google_slides.py       # Google Slides API extractor
│       ├── pipeline/
│       │   ├── __init__.py            # SkillBundle dataclass
│       │   ├── orchestrator.py        # Runs extract → analyze → generate → validate → deploy
│       │   ├── analyzer.py            # Claude-based input classification
│       │   ├── generator.py           # Claude-based SKILL.md generation
│       │   └── validator.py           # Structural + content validation
│       ├── storage/
│       │   ├── __init__.py
│       │   └── gcs.py                 # Upload/download/list skill folders
│       ├── db/
│       │   ├── __init__.py
│       │   ├── connection.py          # AlloyDB async connection pool
│       │   ├── queries.py             # SQL queries for orgs, skills, events
│       │   └── migrations/
│       │       └── 001_initial.sql    # Schema creation
│       └── observability.py           # Structured logging, correlation IDs, stage tracing
├── terraform/
│   ├── main.tf                        # Provider, API enablement
│   ├── variables.tf                   # Input variables
│   ├── cloud_run.tf                   # Cloud Run service
│   ├── gcs.tf                         # GCS bucket
│   ├── alloydb.tf                     # AlloyDB cluster + instance
│   ├── iam.tf                         # Service accounts, roles, secrets
│   └── outputs.tf                     # Service URL, bucket name, etc.
├── tests/
│   ├── conftest.py
│   ├── test_extractors.py
│   ├── test_pipeline.py
│   ├── test_validator.py
│   ├── test_webhooks.py
│   └── test_storage.py
├── Dockerfile
├── pyproject.toml
├── .env.example
└── CLAUDE.md
```

**Key decisions:**
- Package name: `skill_whisperer` (not `skillmaster`)
- Directory `extractors/` instead of `processors/` — clearer name for what it does
- `ProcessedContent` is the universal data contract between extractors and the pipeline

**Config (env vars):**
```
ANTHROPIC_API_KEY          — Claude API access
GOOGLE_APPLICATION_CREDENTIALS — Service account key for Drive/Docs/Slides API
GCS_BUCKET                 — Skill output bucket
GCP_PROJECT                — GCP project ID
ALLOYDB_URL                — AlloyDB connection string
DRIVE_WEBHOOK_SECRET       — Shared secret for webhook verification
LOG_LEVEL                  — INFO default
PORT                       — 8080 default
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

### Step 1.2 — Google Docs Extractor

**File:** `src/skill_whisperer/extractors/google_docs.py`

**What it does:**
- Takes a Google Doc document ID
- Calls `docs.documents.get()` to retrieve the full document
- Walks the document body, extracting:
  - Headings (HEADING_1 through HEADING_6) → section titles
  - Paragraphs → section body text
  - Bulleted and numbered lists → preserved as markdown lists
  - Tables → converted to markdown tables
  - Inline images → downloaded, added to assets list
- Returns a `ProcessedContent` object

**ProcessedContent contract:**
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

### Step 1.3 — Google Slides Extractor

**File:** `src/skill_whisperer/extractors/google_slides.py`

**What it does:**
- Takes a Google Slides presentation ID
- Calls `slides.presentations.get()` to retrieve all slides
- For each slide, extracts:
  - Slide title (from title placeholder)
  - Body text and bullet points
  - Speaker notes (high-signal — this is where the user explains the slide verbally)
  - Images (downloaded, added to assets)
- Reconstructs slides in order as a narrative flow
- Each slide becomes a `Section`

**Tests:**
- Extracts title and body from mock slides
- Speaker notes are captured and labeled
- Slide ordering is preserved
- Handles slides with only images

---

### Step 1.4 — Extractor Router

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

This is the extension point. Adding voice or Slack means adding a new extractor and one more branch here.

---

### Step 1.5 — Analysis Stage

**File:** `src/skill_whisperer/pipeline/analyzer.py`

**What it does:**
- Takes `ProcessedContent`, sends it to Claude for classification
- Claude identifies:
  - **GTM use case** — demand generation, account planning, objection handling, competitive intel, customer success, campaign execution, territory planning, stakeholder management, etc.
  - **Complexity** — simple (single reference doc), moderate (multi-section guide), complex (multi-step workflow with decision points)
  - **Content structure** — playbook, reference guide, decision tree, workflow checklist, profile collection
  - **Named entities** — people, companies, products, processes
  - **Suggested skill name and description**

**Output:**
```python
@dataclass
class AnalysisResult:
    use_case: str
    complexity: str  # simple, moderate, complex
    structure_type: str
    entities: list[dict]
    suggested_name: str
    suggested_description: str
    key_topics: list[str]
    raw_analysis: dict
```

---

### Step 1.6 — Generation Stage

**File:** `src/skill_whisperer/pipeline/generator.py`

**What it does:**
- Takes `ProcessedContent` + `AnalysisResult`
- Sends to Claude with a system prompt that instructs it to produce a valid agent skill definition
- Generates:
  - `SKILL.md` — valid YAML frontmatter + body under 500 lines
  - Asset files — for complex content, splits into referenced files (e.g., `assets/stakeholders.md`, `assets/playbook.md`)
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
```

---

### Step 1.7 — Validation Stage

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

### Step 1.8 — Pipeline Orchestrator

**File:** `src/skill_whisperer/pipeline/orchestrator.py`

Wires the stages together:

```
extract(source_type, source_ref) → ProcessedContent
    │
    ▼
analyze(processed_content) → AnalysisResult
    │
    ▼
generate(processed_content, analysis) → SkillBundle
    │
    ▼
validate(skill_bundle.skill_md) → ValidationResult
    │
    ├── if errors and retries < 2: re-generate with feedback → loop back to validate
    │
    ▼
deploy(skill_bundle, org_id) → gcs_path
```

Each stage is wrapped with the observability decorator that logs start/end/duration and writes to the `processing_events` table.

---

### Step 1.9 — GCS Storage

**File:** `src/skill_whisperer/storage/gcs.py`

**Functions:**

```python
async def upload_skill(skill_bundle: SkillBundle, org_id: str, bucket: str) -> str:
    """
    Writes:
      gs://{bucket}/skills/{org_id}/{skill_id}/SKILL.md
      gs://{bucket}/skills/{org_id}/{skill_id}/metadata.json
      gs://{bucket}/skills/{org_id}/{skill_id}/assets/{filename}
      gs://{bucket}/skills/{org_id}/{skill_id}/.validation/report.json

    Returns the GCS path prefix.
    """

async def download_skill(skill_id: str, org_id: str, bucket: str) -> dict | None:
    """Returns SKILL.md content and metadata, or None."""

async def list_skills(org_id: str, bucket: str) -> list[dict]:
    """Lists all skill folders for an org."""
```

**Path convention:** `skills/{org_id}/{skill_id}/` — this is what Poexis agents look for.

---

### Step 1.10 — AlloyDB Layer

**File:** `src/skill_whisperer/db/connection.py`
- Creates an `asyncpg` connection pool to AlloyDB
- Supports AlloyDB Auth Proxy (connect via Unix socket or localhost proxy)
- Pool: min 1, max 10 connections

**File:** `src/skill_whisperer/db/queries.py`
- `create_skill(org_id, name, description, source_type, source_ref, source_user, gcs_path, validation_result) → skill_id`
- `get_skill(skill_id) → row`
- `list_skills(org_id, team_id=None) → list[row]`
- `log_event(skill_id, stage, status, duration_ms, details)`
- `get_org(org_id) → row`
- `get_org_bucket(org_id) → str`

**File:** `src/skill_whisperer/db/migrations/001_initial.sql`
- Creates all tables from the schema in SPEC.md (except `policy_rules` — that's Phase 2)

---

### Step 1.11 — Google Drive Webhook

**File:** `src/skill_whisperer/api/webhooks.py`

**Endpoints:**

`POST /api/v1/webhooks/drive` — receives Drive push notifications
- Validates the notification (channel token matches `DRIVE_WEBHOOK_SECRET`)
- Ignores `sync` messages (initial handshake)
- On `change` or `update`:
  1. Reads `X-Goog-Resource-ID` to get the file ID
  2. Calls Drive API to get file metadata (MIME type, title, sharing info)
  3. Determines source type from MIME type:
     - `application/vnd.google-apps.document` → `google_docs`
     - `application/vnd.google-apps.presentation` → `google_slides`
  4. Checks if this document_id + revision has already been processed (dedup)
  5. Runs the pipeline orchestrator
  6. Returns 200 (Drive expects fast response; processing is synchronous in MVP)

`POST /api/v1/webhooks/drive/register` — registers a Drive watch
- Takes a file ID or folder ID
- Calls `files.watch()` to set up push notifications
- Stores the channel ID for verification

**Deduplication:** Before processing, check AlloyDB `skills` table for existing skill with same `source_ref` and same revision. Skip if already processed.

---

### Step 1.12 — API Routes

**File:** `src/skill_whisperer/api/routes.py`

`POST /api/v1/skills/generate` — manual trigger (fallback for testing and direct API use)
- Body: `{ source_type, source_ref, org_id, team_id?, metadata? }`
- Runs the full pipeline
- Returns: `{ skill_id, name, status, gcs_path, validation_errors, skill_md_preview }`

`GET /api/v1/skills/{skill_id}` — retrieve a skill
- Returns skill metadata from AlloyDB + SKILL.md content from GCS

`GET /api/v1/skills` — list skills
- Query params: `org_id` (required), `team_id` (optional)
- Returns list from AlloyDB

`POST /api/v1/skills/validate` — validate without storing
- Body: `{ skill_md: str }`
- Returns: `{ is_valid, errors, warnings }`

---

### Step 1.13 — Observability

**File:** `src/skill_whisperer/observability.py`

- **Structured JSON logger:** Every log line includes `correlation_id`, `stage`, `org_id`, `skill_id`
- **Correlation ID middleware:** Assigns a UUID to each request, threads it through all stages
- **Stage tracing decorator:**
  ```python
  @trace_stage("analyze")
  async def analyze(content: ProcessedContent) -> AnalysisResult:
      ...
  ```
  Automatically logs start/end, measures duration, writes to `processing_events`

---

### Step 1.14 — Terraform

**Files and what they provision:**

| File | Resources |
|------|-----------|
| `main.tf` | Google provider, enable APIs (run, storage, alloydb, secretmanager, docs, slides, drive) |
| `variables.tf` | project_id, region, service_name, gcs_bucket, alloydb vars, anthropic_api_key |
| `cloud_run.tf` | Cloud Run v2 service, env vars, startup probe on /health |
| `gcs.tf` | Bucket with uniform access, versioning, lifecycle rules |
| `alloydb.tf` | AlloyDB cluster, primary instance, database, user |
| `iam.tf` | Service account with GCS objectAdmin, AlloyDB client, Secret Manager accessor |
| `outputs.tf` | service_url, gcs_bucket, service_account_email |

---

### Step 1.15 — Tests

| Test file | What it covers |
|-----------|---------------|
| `test_extractors.py` | Google Docs heading extraction, Slides narrative flow, empty doc handling |
| `test_pipeline.py` | Orchestrator wires stages correctly, retry on validation failure |
| `test_validator.py` | All validation rules (frontmatter, name, description, body length, reserved words) |
| `test_webhooks.py` | Drive notification parsing, dedup logic, MIME type routing |
| `test_storage.py` | GCS path construction, org-scoped paths |

---

### Phase 1 — Implementation Order

```
Week 1: Foundation
  ├── 1.1  Project scaffold, config, FastAPI app shell, health endpoint
  ├── 1.10 AlloyDB connection + migrations
  ├── 1.13 Observability (logging, tracing decorator)
  └── 1.7  Validator (no external dependencies, easy to test)

Week 2: Extractors + Pipeline
  ├── 1.2  Google Docs extractor
  ├── 1.3  Google Slides extractor
  ├── 1.4  Extractor router
  ├── 1.5  Analyzer (Claude integration)
  └── 1.6  Generator (Claude integration)

Week 3: Wiring + Deploy
  ├── 1.8  Pipeline orchestrator (wire everything together)
  ├── 1.9  GCS storage (org-scoped paths)
  ├── 1.12 API routes
  ├── 1.11 Drive webhook receiver
  └── 1.15 Tests for all components

Week 4: Infrastructure + E2E
  ├── 1.14 Terraform (Cloud Run, GCS, AlloyDB, IAM)
  ├── Dockerfile
  ├── End-to-end test: share Google Doc → skill appears in GCS
  └── Bug fixes and hardening
```

### Phase 1 — Exit Criteria

- [ ] Share a Google Doc with the service account → skill folder appears in GCS within 60 seconds
- [ ] Share a Google Slides deck → same result
- [ ] `POST /api/v1/skills/generate` with a document ID produces a valid skill
- [ ] Generated SKILL.md passes all structural validation rules
- [ ] Skill metadata is recorded in AlloyDB
- [ ] Processing events are logged for each pipeline stage
- [ ] `GET /api/v1/skills?org_id=X` returns the generated skill
- [ ] All tests pass
- [ ] `terraform plan` succeeds with no errors
- [ ] Structured JSON logs include correlation IDs

---

## Phase 2 — Organization Policies & Compliance

**Outcome:** Organizations define custom rules (banned terms, required sections, terminology, PII detection). Skills are checked against these rules before deployment.

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
- Add policy check stage between validate and deploy in orchestrator
- Blocking violations prevent deployment
- All results recorded in `processing_events`

**2.4 — Compliance audit API**
- `GET /api/v1/skills/{skill_id}/audit` — full processing + compliance history

### Phase 2 — Exit Criteria

- [ ] Create a "banned_terms" policy → skill containing banned term is blocked
- [ ] Create a "required_sections" policy → skill missing required section is blocked
- [ ] Warnings do not block deployment
- [ ] Audit endpoint shows full compliance trail
- [ ] Policy CRUD works end-to-end

---

## Phase 3 — Voice Agent Pipeline

**Outcome:** A voice agent conducts a structured interview with the user. The conversation is transcribed and processed into a skill.

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

**3.3 — Interview agent** (`src/skill_whisperer/extractors/interview_agent.py`)
- Claude-powered agent that guides the conversation
- Asks follow-up questions based on detected GTM use case
- Knows when it has enough information to generate a skill
- Produces structured Q&A that feeds into the standard pipeline

### Phase 3 — Exit Criteria

- [ ] User can start a voice session via WebSocket
- [ ] Agent asks relevant follow-up questions
- [ ] Completed session produces a valid skill in GCS
- [ ] Voice-generated skills pass all validation

---

## Phase 4 — Event-Driven Pipeline

**Outcome:** Ingestion is decoupled from processing via Pub/Sub. Enables async processing, retries, and dead-letter handling.

### Steps

**4.1 — Pub/Sub integration**
- Topics: `skill-ingest-events`, `skill-deployed-events`, `skill-dlq`
- Webhook handler publishes to Pub/Sub instead of calling pipeline directly
- Cloud Run subscriber pulls from ingest topic

**4.2 — Async API**
- `POST /api/v1/skills/generate` returns 202 + job ID
- `GET /api/v1/jobs/{job_id}` — poll for status

**4.3 — Retry + DLQ**
- Exponential backoff, max 3 attempts
- Failed events land in `skill-dlq` for manual review

**4.4 — Terraform**
- Pub/Sub topics, subscriptions, DLQ
- Cloud Run subscriber service

---

## Phase 5 — Multi-Experience Endpoints

**Outcome:** Slack, email, and browser extension feed into the same pipeline.

### Steps

**5.1 — Slack bot** — paste content or share a doc link → triggers pipeline
**5.2 — Email ingestion** — forward to `skills@domain` → email body processed
**5.3 — Chrome extension** — highlight text, send to Skill Whisperer

Each is a thin adapter that produces an `IngestEvent` and publishes to Pub/Sub. The core pipeline is unchanged.

---

## Phase 6 — Enterprise

**Outcome:** Production hardening for enterprise deployment.

### Steps

**6.1 — RBAC** — org admin, team editor, viewer roles
**6.2 — Skill versioning** — track changes, diff between versions
**6.3 — Approval workflows** — skills require approval before deployment
**6.4 — Multi-region** — deploy to multiple GCP regions
**6.5 — SSO** — SAML/OIDC integration
**6.6 — Analytics** — skill creation volume, agent consumption stats
