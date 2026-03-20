# Skill Whisperer — Implementation Plan

This plan builds incrementally on the existing Skill Master codebase. Each phase produces a working system that can be demoed and tested end-to-end.

---

## Phase 1 — MVP Foundation (Google Docs → GCS)

**Goal:** A user shares a Google Doc with the service account. The service extracts content, generates a validated SKILL.md + assets, and deploys to GCS. Poexis agents can read the skill.

### 1.1 Google Docs Extractor

**New file:** `src/skillmaster/processors/google_docs.py`

- Use Google Docs API (`documents.get`) to read document structure
- Extract heading hierarchy, paragraphs, lists, and tables into `ProcessedContent`
- Map Google Docs heading levels (HEADING_1–6) to section structure
- Extract inline images: download from Google, store as asset references
- Handle numbered/bulleted lists as structured content
- Accept either a `document_id` + credentials or pre-extracted text (for testing)

**Changes to existing:**
- `src/skillmaster/processors/__init__.py` — add `GOOGLE_DOCS` to `InputType` enum and route to new processor
- `src/skillmaster/api/models.py` — add `GOOGLE_DOCS` to `InputType` enum

**Tests:** `tests/test_processors.py` — add tests for heading extraction, list parsing, image handling, and fallback behavior

### 1.2 Google Drive Webhook Receiver

**New file:** `src/skillmaster/api/webhooks.py`

- `POST /api/v1/webhooks/drive` — receives Google Drive push notifications
- Validates the webhook payload (channel ID, resource state)
- On `change` event for a shared document:
  1. Determines document type (Doc or Slides) from MIME type
  2. Reads the document via Docs/Slides API
  3. Calls the existing pipeline (`process_input → generate_skill → upload`)
  4. Returns 200 to acknowledge the webhook
- `POST /api/v1/webhooks/drive/register` — registers a watch on a specific file or folder (admin use)
- Idempotency: tracks processed document IDs + revision IDs to avoid reprocessing

**New file:** `src/skillmaster/ingestion/drive_watcher.py`

- `register_watch(file_id, webhook_url)` — calls Drive API `files.watch()`
- `verify_notification(headers, body)` — validates webhook authenticity
- `get_document_metadata(file_id)` — retrieves MIME type, title, last modifier

**Changes to existing:**
- `src/skillmaster/main.py` — mount webhook router
- `src/skillmaster/config.py` — add `SKILLMASTER_DRIVE_WEBHOOK_URL`, `SKILLMASTER_GOOGLE_SERVICE_ACCOUNT_KEY_PATH`

**Tests:** `tests/test_webhooks.py` — mock Drive notifications, test idempotency, test MIME type routing

### 1.3 AlloyDB Migration (from NeonDB)

**Changes to existing:**
- `src/skillmaster/db/connection.py` — update connection logic for AlloyDB (still PostgreSQL wire protocol, so `asyncpg` works; update connection string format and add AlloyDB Auth Proxy support)
- `src/skillmaster/db/queries.py` — expand with new tables: `skills`, `processing_events`
- `src/skillmaster/config.py` — rename `NEONDB_URL` → `ALLOYDB_URL`, add `ALLOYDB_INSTANCE` for Auth Proxy

**New file:** `src/skillmaster/db/migrations/001_initial_schema.sql`

- Create tables: `organizations`, `teams`, `skills`, `processing_events`
- Seed with a default organization for MVP testing

**New file:** `src/skillmaster/db/migrations/run_migrations.py`

- Simple sequential SQL file runner for dev/CI

### 1.4 Skill Metadata Recording

**Changes to existing:**
- `src/skillmaster/pipeline/orchestrator.py` — after GCS upload, insert row into `skills` table with metadata (source_type, source_ref, gcs_path, validation_result)
- `src/skillmaster/pipeline/orchestrator.py` — insert `processing_events` rows at each pipeline stage (extract, analyze, generate, validate, deploy) with timing

**New file:** `src/skillmaster/db/skill_repository.py`

- `create_skill(skill_metadata) → skill_id`
- `get_skill(skill_id) → SkillRecord`
- `list_skills(org_id, team_id) → list[SkillRecord]`
- `log_processing_event(skill_id, stage, status, duration_ms, details)`

### 1.5 Org-Scoped GCS Paths

**Changes to existing:**
- `src/skillmaster/storage/gcs.py` — update path convention from `skills/{skill_id}/` to `skills/{org_id}/{skill_id}/`
- `src/skillmaster/storage/config_resolver.py` — resolve bucket from AlloyDB `organizations` table

### 1.6 Infrastructure Updates

**Changes to existing:**
- `terraform/main.tf` — add AlloyDB API enablement
- `terraform/variables.tf` — add AlloyDB variables (instance_id, cluster_id, password)

**New files:**
- `terraform/alloydb.tf` — AlloyDB cluster + primary instance + database
- `terraform/pubsub.tf` — placeholder topic for `skill-events` (used in Phase 4, but create now for forward compatibility)

**Changes to existing:**
- `terraform/cloud_run.tf` — add AlloyDB connection, remove NeonDB secret
- `terraform/iam.tf` — add AlloyDB client role to service account, add Drive API scopes

### 1.7 Observability Baseline

**New file:** `src/skillmaster/observability.py`

- Structured JSON logger with correlation IDs (event_id flows through all stages)
- `@trace_stage(stage_name)` decorator that logs start/end/duration and writes to `processing_events`
- Request middleware that assigns a correlation ID to each request

**Changes to existing:**
- `src/skillmaster/main.py` — add logging middleware
- `src/skillmaster/pipeline/orchestrator.py` — wrap each stage with `@trace_stage`

### Phase 1 Deliverables

| Deliverable | Verification |
|-------------|-------------|
| Google Docs processor | Unit tests pass; processes a real Google Doc |
| Drive webhook endpoint | Receives notification, triggers pipeline |
| AlloyDB schema + connection | Migration runs; queries work |
| Skill metadata in AlloyDB | Skill record created after generation |
| Org-scoped GCS paths | Skills land at `gs://bucket/skills/{org_id}/{skill_id}/` |
| Processing event log | Each stage logged with duration |
| Terraform for AlloyDB | `terraform plan` succeeds |
| End-to-end test | Share a Google Doc → skill appears in GCS |

---

## Phase 2 — Policies & Compliance Pipeline

**Goal:** Organizations can define custom rules that are applied during validation. Skills that violate policies are flagged or blocked.

### 2.1 Policy Engine

**New file:** `src/skillmaster/pipeline/policy_engine.py`

- `load_policies(org_id) → list[PolicyRule]` — fetch from AlloyDB `policy_rules` table
- `apply_policies(skill_md, policies) → PolicyResult` — run each rule against the skill
- Built-in rule types:
  - `banned_terms` — list of terms that must not appear (competitor names, profanity)
  - `required_sections` — sections that must exist in every skill (e.g., "Compliance Notes")
  - `terminology_map` — enforce consistent terminology (e.g., "customer" not "client")
  - `style_rules` — tone constraints (formal, no first-person, etc.)
  - `pii_detection` — flag or redact personal information patterns

### 2.2 Policy Management API

**New file:** `src/skillmaster/api/policy_routes.py`

- `POST /api/v1/orgs/{org_id}/policies` — create a policy rule
- `GET /api/v1/orgs/{org_id}/policies` — list policy rules
- `PUT /api/v1/orgs/{org_id}/policies/{rule_id}` — update a policy rule
- `DELETE /api/v1/orgs/{org_id}/policies/{rule_id}` — delete a policy rule

### 2.3 Pipeline Integration

**Changes to existing:**
- `src/skillmaster/pipeline/orchestrator.py` — add policy check stage between validate and deploy
- `src/skillmaster/pipeline/validator.py` — separate structural validation from policy validation
- Policy violations can be `blocking` (prevent deployment) or `warning` (deploy with flag)

### 2.4 Compliance Audit Trail

- Every policy check result stored in `processing_events` with full details
- `GET /api/v1/skills/{skill_id}/audit` — returns full processing + compliance history

### Phase 2 Deliverables

| Deliverable | Verification |
|-------------|-------------|
| Policy engine with 5 rule types | Unit tests for each rule type |
| Policy CRUD API | Integration tests |
| Pipeline applies org policies | Skill with banned term is blocked |
| Audit trail API | Returns full processing history |

---

## Phase 3 — Voice Agent Pipeline

**Goal:** A voice agent conducts a structured interview with the GTM user, captures responses, and produces a skill.

### 3.1 Voice Pipeline Architecture

```
User (phone/web) → Telephony/WebRTC → Speech-to-Text → Interview Processor → Pipeline
```

### 3.2 Components

**New file:** `src/skillmaster/processors/voice_agent.py`

- Extends existing `voice.py` with real-time streaming support
- Structured interview flow: the agent asks questions based on the detected GTM use case
- Uses Claude to guide the conversation and extract structured information
- Produces `ProcessedContent` identical to other processors

**New file:** `src/skillmaster/ingestion/voice_session.py`

- WebSocket endpoint for real-time voice streaming
- Session management (start, pause, resume, end)
- Transcript accumulation with speaker diarization

### 3.3 Infrastructure

- Google Cloud Speech-to-Text v2 for transcription
- WebSocket support on Cloud Run
- Session state in AlloyDB

### Phase 3 Deliverables

| Deliverable | Verification |
|-------------|-------------|
| Voice interview agent | Conducts structured Q&A, produces transcript |
| Real-time transcription | WebSocket streaming works |
| Voice → skill end-to-end | Voice session produces valid skill in GCS |

---

## Phase 4 — Event-Driven Pipeline

**Goal:** Decouple ingestion from processing using Pub/Sub. Enable async processing, retries, and dead-letter queues.

### 4.1 Components

- **Pub/Sub topics:** `skill-ingest-events`, `skill-deployed-events`, `skill-dlq`
- **Cloud Run subscriber:** pulls from `skill-ingest-events`, runs pipeline
- **Retry policy:** exponential backoff, max 3 attempts, then DLQ
- **Dead letter queue:** failed events land in `skill-dlq` for manual review

### 4.2 Changes

- Webhook handler publishes to Pub/Sub instead of calling pipeline directly
- API `/generate` endpoint can optionally be async (returns 202 + job ID)
- New endpoint: `GET /api/v1/jobs/{job_id}` — poll for async job status

### Phase 4 Deliverables

| Deliverable | Verification |
|-------------|-------------|
| Pub/Sub integration | Events flow through topics |
| Async processing | 202 response with job polling |
| Retry + DLQ | Failed events retry 3x then land in DLQ |

---

## Phase 5 — Multi-Experience Endpoints

**Goal:** Add Slack, email, and browser extension as input sources. All feed into the same pipeline.

### 5.1 Components

- **Slack bot:** User pastes content or shares a doc link in Slack → triggers pipeline
- **Email ingestion:** Forward an email to `skills@{domain}` → email content processed
- **Chrome extension:** Highlight text on any web page → send to Skill Whisperer

### 5.2 Architecture

Each new input source is a thin adapter that:
1. Receives input in its native format
2. Converts to `IngestEvent`
3. Publishes to `skill-ingest-events` Pub/Sub topic

The core pipeline is unchanged.

---

## Phase 6 — Enterprise Grade

**Goal:** Production hardening for enterprise customers.

### 6.1 Features

- **RBAC:** Role-based access control (org admin, team editor, viewer)
- **Skill versioning:** Track changes over time, diff between versions
- **Approval workflows:** Skills require manager approval before deployment
- **Multi-region:** Deploy to multiple GCP regions for latency and compliance
- **SSO integration:** SAML/OIDC for enterprise identity providers
- **Usage analytics:** Dashboard showing skill creation volume, agent consumption stats

---

## Implementation Sequence (Phase 1 Detail)

For Phase 1, the recommended implementation order optimizes for getting end-to-end flow working early, then hardening:

```
Week 1:  1.3 AlloyDB Migration        — Database foundation
         1.1 Google Docs Extractor     — New input processor
         1.7 Observability Baseline    — Logging infrastructure

Week 2:  1.4 Skill Metadata Recording  — DB integration in pipeline
         1.5 Org-Scoped GCS Paths      — Storage path update
         1.2 Drive Webhook Receiver    — Event-driven ingestion

Week 3:  1.6 Infrastructure Updates    — Terraform for AlloyDB
         End-to-end integration test   — Share Doc → skill in GCS
         Bug fixes and polish
```

---

## Migration Notes (Skill Master → Skill Whisperer)

The existing Skill Master codebase is the foundation. Key migration decisions:

| Aspect | Skill Master (current) | Skill Whisperer (target) |
|--------|----------------------|------------------------|
| Package name | `skillmaster` | Keep as `skillmaster` (internal); brand as "Skill Whisperer" externally |
| Database | NeonDB (optional) | AlloyDB (required for metadata) |
| Input trigger | API call only | Google Drive webhook + API |
| GCS path | `skills/{skill_id}/` | `skills/{org_id}/{skill_id}/` |
| Validation | Structural only | Structural + org policies |
| New processor | — | Google Docs (extends existing Slides processor pattern) |
| Observability | Basic logging | Structured logging + processing event table |

**What stays the same:**
- FastAPI framework and app structure
- All existing processors (plaintext, voice, slides, interview, generic)
- Pipeline architecture (orchestrator → analyzer → generator → validator)
- Claude API integration for analysis and generation
- GCS upload/download logic (path change only)
- Existing tests (extended, not replaced)
- Docker build and Cloud Run deployment pattern
