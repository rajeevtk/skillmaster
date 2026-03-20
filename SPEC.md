# Skill Whisperer — Service Specification

## What Is Skill Whisperer

Skill Whisperer is a service that turns informal, unstructured knowledge from non-technical business users into validated, deployable agent skill definitions. A salesperson describes how they work — in a Google Doc, a slide deck, or eventually a voice conversation — and Skill Whisperer converts that into a structured `SKILL.md` with supporting asset files, applies organizational compliance rules, and deploys the result to Google Cloud Storage where Poexis agents pick it up and use it.

The service is built for Poexis and runs on Google Cloud (Cloud Run, GCS, AlloyDB).

---

## 1. Personas

### The End User: GTM Practitioner

A non-technical person in sales or marketing. They do not write code. They create content in tools they already use — Google Docs and Google Slides.

**What they produce:**
- Account-specific demand generation guidelines
- Named stakeholder profiles with personal preferences
- Objection-handling playbooks
- Territory-specific selling motions
- Campaign execution checklists

**How they interact (MVP):** They write a Google Doc or build a Google Slide deck describing how they do their work. They share that document with the Skill Whisperer service. That action kicks off the entire workflow. They don't need to visit a separate app or learn a new tool.

**How they interact (future):** They talk to a voice agent that interviews them — asks follow-up questions, probes for details — and captures the conversation into a skill.

### The Skill Consumer: Poexis Agent

A downstream Claude-based agent in the Poexis platform. It reads skill definitions from a known GCS location (`gs://{bucket}/skills/{org_id}/{skill_id}/SKILL.md`). It expects skills to be valid, complete, and immediately usable.

### The Platform Admin (Phase 3+)

A technical user who configures organization policies, compliance rules, and pipeline settings. Manages the system through API or admin tooling.

---

## 2. Core Workflow

```
 End User                    Skill Whisperer                        Poexis
 ────────                    ───────────────                        ──────

 Writes Google Doc
 or Slide Deck
       │
       │  shares with
       │  service account
       ▼
                     ┌─────────────────────────┐
                     │  1. DETECT              │
                     │  Google Drive webhook    │
                     │  notices the share       │
                     └───────────┬─────────────┘
                                 │
                                 ▼
                     ┌─────────────────────────┐
                     │  2. EXTRACT             │
                     │  Read doc via Docs/     │
                     │  Slides API. Parse      │
                     │  headings, bullets,     │
                     │  speaker notes, images  │
                     └───────────┬─────────────┘
                                 │
                                 ▼
                     ┌─────────────────────────┐
                     │  3. ANALYZE             │
                     │  Classify the use case. │
                     │  Extract entities,      │
                     │  workflows, structure.  │
                     └───────────┬─────────────┘
                                 │
                                 ▼
                     ┌─────────────────────────┐
                     │  4. GENERATE            │
                     │  Produce SKILL.md +     │
                     │  asset files following  │
                     │  agent skills spec.     │
                     └───────────┬─────────────┘
                                 │
                                 ▼
                     ┌─────────────────────────┐
                     │  5. VALIDATE & COMPLY   │
                     │  Structural checks.     │
                     │  Org policy checks.     │
                     │  Linting and style.     │
                     │  Loop if fixable.       │
                     └───────────┬─────────────┘
                                 │
                                 ▼
                     ┌─────────────────────────┐
                     │  6. DEPLOY              │
                     │  Write skill folder     │
                     │  to GCS. Record meta-   │
                     │  data in AlloyDB.       │
                     └───────────┬─────────────┘
                                 │
                                 ▼
                                              Poexis agents read
                                              from GCS and use
                                              the skill at runtime
```

---

## 3. Architecture Principles

**Loosely coupled pipelines.** Each stage (extract, analyze, generate, validate, deploy) is an independent component with a clear input/output contract. Swapping or adding a new extractor (e.g., voice) does not require changes to the generator or validator.

**Observable.** Every pipeline stage emits structured logs with a correlation ID that follows the request from ingestion to deployment. Stage durations, errors, and outcomes are recorded in AlloyDB for debugging and analytics.

**Extensible input sources.** The MVP supports Google Docs and Google Slides. The architecture treats these as pluggable "extractors" behind a common interface. Adding voice, Slack, email, or any other input source means writing a new extractor — the rest of the pipeline is unchanged.

**Idempotent processing.** Re-processing the same document at the same revision produces the same output. Safe to retry on failure.

**Multi-tenant from the start.** Org-scoped storage paths and configuration, even if the MVP serves a single organization.

---

## 4. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       INPUT SOURCES                              │
│                                                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│  │ Google Docs  │   │Google Slides│   │ Voice Agent │           │
│  │             │   │             │   │  (future)   │           │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘           │
│         │                  │                  │                   │
│         └────────┬─────────┘                  │                   │
│                  │ (MVP)                      │ (Phase 3+)       │
└──────────────────┼────────────────────────────┼──────────────────┘
                   │                            │
                   ▼                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    INGESTION LAYER                                │
│                                                                  │
│  Google Drive Webhook Receiver (Cloud Run)                       │
│  - Detects shares / edits                                        │
│  - Determines document type (Doc vs Slides)                      │
│  - Deduplicates by document_id + revision_id                     │
│  - Dispatches to processing pipeline                             │
│                                                                  │
│  Also: POST /api/v1/skills/generate (manual trigger / API use)  │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                   PROCESSING PIPELINE                             │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
│  │ Extract  │──▶│ Analyze  │──▶│ Generate │──▶│  Validate &  │ │
│  │          │   │          │   │          │   │   Comply      │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────┘ │
│                                                                  │
│  Each stage: independent, traced, retryable                      │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT LAYER                               │
│                                                                  │
│  - Writes skill folder to GCS                                    │
│  - Records metadata in AlloyDB                                   │
│  - (Phase 4+) Emits SkillDeployed event to Pub/Sub              │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                   GOOGLE CLOUD STORAGE                            │
│                                                                  │
│  gs://{bucket}/skills/{org_id}/{skill_id}/                       │
│  ├── SKILL.md                                                    │
│  ├── metadata.json                                               │
│  ├── assets/                                                     │
│  │   ├── stakeholders.md                                         │
│  │   ├── playbook.md                                             │
│  │   └── ...                                                     │
│  └── .validation/                                                │
│      └── report.json                                             │
│                                                                  │
│  Poexis agents read from here.                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Infrastructure

| Component | GCP Service | Purpose |
|-----------|-------------|---------|
| API + Pipeline | Cloud Run | Hosts the FastAPI app, runs the processing pipeline |
| Skill Output Store | Google Cloud Storage | Deployed skill folders; Poexis agents read from here |
| Metadata & Config | AlloyDB (PostgreSQL) | Org config, skill records, processing logs, policy rules |
| Document Access | Google Docs API, Slides API | Read shared documents |
| Change Detection | Google Drive Push Notifications | Webhook when documents are shared or updated |
| Secrets | Secret Manager | API keys, service account credentials |
| Event Bus (Phase 4+) | Cloud Pub/Sub | Decouple ingestion from processing |
| Observability | Cloud Logging + Cloud Trace | Structured logs, distributed tracing |

### AlloyDB Schema

```sql
CREATE TABLE organizations (
    org_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    gcs_bucket      TEXT NOT NULL,
    config          JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE teams (
    team_id         TEXT PRIMARY KEY,
    org_id          TEXT REFERENCES organizations(org_id),
    name            TEXT NOT NULL,
    gcs_bucket      TEXT,             -- optional override
    config          JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE skills (
    skill_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          TEXT REFERENCES organizations(org_id),
    team_id         TEXT REFERENCES teams(team_id),
    name            TEXT NOT NULL,
    description     TEXT,
    source_type     TEXT NOT NULL,    -- google_docs, google_slides, voice, api
    source_ref      TEXT,             -- document ID
    source_user     TEXT,             -- email of person who shared
    gcs_path        TEXT NOT NULL,
    status          TEXT DEFAULT 'active',
    version         INTEGER DEFAULT 1,
    validation_result JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE processing_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id        UUID REFERENCES skills(skill_id),
    stage           TEXT NOT NULL,    -- extract, analyze, generate, validate, deploy
    status          TEXT NOT NULL,    -- started, completed, failed
    duration_ms     INTEGER,
    details         JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Phase 2+
CREATE TABLE policy_rules (
    rule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          TEXT REFERENCES organizations(org_id),
    rule_type       TEXT NOT NULL,    -- banned_terms, required_sections, terminology, style, pii
    rule_config     JSONB NOT NULL,
    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. Pipeline Stage Detail

### 6.1 Extract

Reads the source document and produces normalized, structured content.

**Google Docs extractor:**
- Calls Docs API `documents.get` to read the full document
- Maps HEADING_1–6 to a section hierarchy
- Extracts paragraphs, numbered/bulleted lists, tables
- Downloads inline images, stores as asset references
- Treats document comments as supplementary context

**Google Slides extractor:**
- Calls Slides API `presentations.get` to read all slides
- For each slide: extracts title, body text, bullet points, speaker notes
- Speaker notes are treated as high-signal (the user's verbal explanation of the slide)
- Reconstructs narrative flow from slide order
- Downloads images, stores as asset references

**Common output contract:**

```
ProcessedContent:
    source_type: str
    raw_text: str
    sections: list[{title, body, type}]
    assets: list[{name, type, content_ref}]
    metadata: dict
```

Any future extractor (voice, email, Slack) produces the same `ProcessedContent`. This is the decoupling point.

### 6.2 Analyze

Uses Claude to understand what the user wrote and how to structure it as a skill.

- Classifies the GTM use case (demand gen, account planning, objection handling, competitive intel, etc.)
- Assesses complexity (simple reference vs. multi-step workflow)
- Extracts named entities (people, companies, products)
- Detects structure: is this a playbook? a reference guide? a decision tree? a workflow?
- Outputs an analysis object that guides the generator

### 6.3 Generate

Uses Claude to produce the actual skill definition files.

- Generates `SKILL.md` following the agent skills specification
  - Valid YAML frontmatter (`name`, `description`)
  - Body under 500 lines
  - Progressive disclosure: complex content split into referenced asset files
  - Concrete examples relevant to the detected use case
- Generates referenced asset files (stakeholder profiles, playbooks, guidelines, etc.)
- Supports a feedback loop: if validation fails, re-generates with error context (max 2 retries)

### 6.4 Validate & Comply

Multi-layer checks before a skill is deployed:

1. **Structural validation** — YAML frontmatter rules, body length limits, reference depth
2. **Content linting** — Consistent terminology, no time-sensitive language, appropriate tone
3. **Org policy checks (Phase 2+)** — Custom rules per organization:
   - Banned terms (competitor names, profanity)
   - Required sections
   - Terminology enforcement
   - PII detection and redaction
4. **Agent skills spec compliance** — Validates the output is a well-formed skill definition

Violations can be **blocking** (skill not deployed) or **warning** (deployed with flag).

### 6.5 Deploy

- Writes the skill folder to GCS at `gs://{bucket}/skills/{org_id}/{skill_id}/`
- Records the skill in AlloyDB with full metadata
- Logs a processing event for the deploy stage
- (Phase 4+) Publishes a `SkillDeployed` event

---

## 7. MVP Scope

### In Scope

- **Google Docs** as an input source — share a doc, get a skill
- **Google Slides** as an input source — share a deck, get a skill
- **Google Drive webhook receiver** — detects shares, triggers processing
- **Full processing pipeline** — extract, analyze, generate, validate, deploy
- **GCS deployment** — skill folders at org-scoped paths
- **AlloyDB** — skill metadata, processing event log, org config
- **Manual API trigger** — `POST /api/v1/skills/generate` as fallback
- **Structural + content validation** — no custom org policies yet
- **Structured logging** with correlation IDs
- **Terraform** for Cloud Run, GCS, AlloyDB, IAM
- **Health and readiness endpoints**

### Out of Scope (MVP)

- Voice agent input
- Custom organization policy rules
- Pub/Sub event bus (synchronous processing in MVP)
- Admin UI
- Skill versioning and diff
- Multi-region
- Batch processing
- Slack, email, or browser extension inputs

---

## 8. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| End-to-end latency | < 60 seconds for a typical 10-page document |
| Availability | 99.5% (Cloud Run SLA) |
| Concurrent processing | 10 simultaneous generations (MVP) |
| Skill output quality | Zero structural errors; warnings acceptable |
| Tenant isolation | Org-scoped GCS paths; no cross-org data leakage |
| Observability | Structured JSON logs; per-stage duration tracking in AlloyDB |
| Security | Least-privilege IAM; no user credentials stored; docs accessed via service account |

---

## 9. Phase Roadmap

| Phase | Name | What It Adds |
|-------|------|-------------|
| **1 — MVP** | Google Docs to GCS | Docs/Slides input, full pipeline, GCS deploy, AlloyDB metadata |
| **2 — Policies** | Org Compliance | Custom policy rules engine, policy CRUD API, compliance audit trail |
| **3 — Voice** | Interview Agent | Voice agent conducts structured interviews, captures into skills |
| **4 — Events** | Async Pipeline | Pub/Sub decoupling, async processing, retry/DLQ, job status API |
| **5 — Multi-Experience** | More Input Sources | Slack bot, email ingestion, Chrome extension |
| **6 — Enterprise** | Production Hardening | RBAC, skill versioning, approval workflows, multi-region, SSO |
