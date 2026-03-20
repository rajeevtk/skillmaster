# Skill Whisperer — Service Specification

## Overview

Skill Whisperer is a service that converts unstructured knowledge from non-technical GTM (sales & marketing) users into validated, deployable Claude Agent Skill definitions. Users share knowledge via Google Docs, Google Slides, or (in future phases) voice conversations. The service processes these inputs through an analysis and compliance pipeline, producing `SKILL.md` files and associated asset folders that are deployed to Google Cloud Storage for consumption by Poexis agents.

This spec builds on the existing Skill Master codebase, evolving it into a production-grade, multi-tenant, loosely coupled system.

---

## 1. User Personas

### 1.1 End User — GTM Practitioner

- **Role:** Non-technical user in sales, marketing, or customer success
- **Technical level:** Comfortable with Google Docs/Slides; no coding skills
- **Inputs they produce:**
  - Account-specific demand generation guidelines
  - Named stakeholder profiles and preferences
  - Competitive intelligence and objection-handling playbooks
  - Campaign workflows and approval chains
  - Territory-specific selling motions
- **Interaction model (MVP):** Shares a Google Doc or Google Slide deck with the Skill Whisperer service account. The service detects the share, processes the document, and produces a skill folder in GCS.
- **Interaction model (future):** Speaks with a voice agent that conducts a structured interview and captures responses into skills.

### 1.2 Skill Consumer — Poexis Agent

- **Role:** Downstream Claude-based agent in the Poexis platform
- **Interaction:** Reads skill definitions from a well-known GCS path (`gs://{bucket}/skills/{org_id}/{skill_id}/SKILL.md`)
- **Expectation:** Skills are valid, compliant with the agent skills specification, and immediately usable without manual editing.

### 1.3 Platform Admin

- **Role:** Technical user who configures org/team policies, compliance rules, and pipeline settings
- **Interaction:** Manages configuration via API or database records
- **Introduced in:** Phase 3+

---

## 2. Architecture

### 2.1 Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Loosely coupled pipelines** | Each processing stage is an independent, swappable component connected via well-defined data contracts. New pipelines (voice, Slack, email) plug in without modifying core logic. |
| **Observable by default** | Every pipeline stage emits structured logs, traces, and metrics. Failures are visible, debuggable, and alertable. |
| **Event-driven ingestion** | Input sources trigger processing via events (Google Drive webhooks, Pub/Sub messages), not polling. |
| **Idempotent processing** | Re-processing the same document produces the same skill output. Safe to retry. |
| **Multi-tenant from day one** | Org/team isolation at the storage and policy layer, even if MVP starts single-tenant. |

### 2.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT SOURCES                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ Google   │  │ Google   │  │  Voice   │  │  Direct  │           │
│  │  Docs    │  │ Slides   │  │  Agent   │  │   API    │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘           │
│       │              │              │              │                 │
└───────┼──────────────┼──────────────┼──────────────┼─────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     INGESTION LAYER                                 │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  Event Router (Cloud Run + Pub/Sub)                      │      │
│  │  - Google Drive webhook receiver                         │      │
│  │  - API request handler                                   │      │
│  │  - Publishes IngestEvent to processing topic             │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PROCESSING PIPELINE                               │
│                                                                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │ 1. Extract │  │ 2. Analyze │  │ 3. Generate│  │ 4. Validate  │  │
│  │            │→ │            │→ │            │→ │ & Comply     │  │
│  │ Parse doc, │  │ Classify   │  │ Produce    │  │ Lint, policy │  │
│  │ normalize  │  │ use case,  │  │ SKILL.md + │  │ checks,      │  │
│  │ content    │  │ extract    │  │ asset files │  │ org rules    │  │
│  │            │  │ structure  │  │            │  │              │  │
│  └────────────┘  └────────────┘  └────────────┘  └──────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     DEPLOYMENT LAYER                                │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  Skill Deployer                                          │      │
│  │  - Writes skill folder to GCS                            │      │
│  │  - Records metadata in AlloyDB                           │      │
│  │  - Emits SkillDeployed event                             │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     CONSUMPTION LAYER                                │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  Poexis Agents                                           │      │
│  │  - Read skills from GCS: gs://{bucket}/skills/{org}/{id} │      │
│  │  - SKILL.md + referenced asset files                     │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 Data Contracts

#### IngestEvent

```json
{
  "event_id": "uuid",
  "source_type": "google_docs | google_slides | voice | api",
  "source_ref": "document_id or API request_id",
  "org_id": "string",
  "team_id": "string (optional)",
  "user_email": "string",
  "timestamp": "ISO8601",
  "metadata": {}
}
```

#### ProcessedContent

```json
{
  "event_id": "uuid",
  "raw_text": "string",
  "source_type": "string",
  "structured_sections": [
    {"title": "string", "body": "string", "type": "heading | qa | slide | speaker_turn"}
  ],
  "extracted_assets": [
    {"name": "string", "type": "image | table | chart", "content_ref": "string"}
  ],
  "metadata": {}
}
```

#### SkillBundle

```json
{
  "skill_id": "uuid",
  "org_id": "string",
  "name": "string",
  "description": "string",
  "skill_md": "string (SKILL.md content)",
  "additional_files": {"relative_path": "content"},
  "validation_result": {
    "is_valid": true,
    "errors": [],
    "warnings": [],
    "policy_violations": []
  },
  "source_event_id": "uuid",
  "created_at": "ISO8601"
}
```

### 2.4 Skill Folder Structure (Output)

```
gs://{bucket}/skills/{org_id}/{skill_id}/
├── SKILL.md              # Main skill definition (< 500 lines)
├── metadata.json         # Provenance: source doc, timestamps, validation
├── assets/               # Referenced files
│   ├── stakeholders.md   # e.g., account stakeholder profiles
│   ├── playbook.md       # e.g., objection handling scripts
│   └── guidelines.md     # e.g., demand gen guidelines
└── .validation/          # Audit trail
    └── report.json       # Full validation + compliance report
```

---

## 3. Infrastructure

### 3.1 Compute

| Component | Service | Purpose |
|-----------|---------|---------|
| API + Pipeline | Google Cloud Run | Hosts FastAPI app, processes pipeline |
| Event Ingestion | Cloud Run + Pub/Sub | Receives Drive webhooks, queues processing |
| Async Workers (future) | Cloud Run Jobs | Long-running voice processing, batch ops |

### 3.2 Storage

| Component | Service | Purpose |
|-----------|---------|---------|
| Skill Output | Google Cloud Storage | Deployed skill folders consumed by Poexis agents |
| Metadata & Config | AlloyDB (PostgreSQL) | Org/team config, skill metadata, audit logs, policy rules |
| Secrets | Secret Manager | API keys, service account credentials |

### 3.3 Integration

| Component | Service | Purpose |
|-----------|---------|---------|
| Document Access | Google Drive API + Docs/Slides API | Read shared documents |
| Change Detection | Google Drive Push Notifications (webhooks) | Detect when docs are shared/updated |
| Event Bus | Cloud Pub/Sub | Decouple ingestion from processing |
| Observability | Cloud Logging + Cloud Trace | Structured logs, distributed tracing |

### 3.4 AlloyDB Schema (replaces NeonDB)

```sql
-- Organization configuration
CREATE TABLE organizations (
    org_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    gcs_bucket      TEXT NOT NULL,
    skill_prefix    TEXT DEFAULT 'skills',
    policies        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Team configuration (inherits from org)
CREATE TABLE teams (
    team_id         TEXT PRIMARY KEY,
    org_id          TEXT REFERENCES organizations(org_id),
    name            TEXT NOT NULL,
    gcs_bucket      TEXT,  -- override org bucket if set
    policies        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Skill metadata and audit trail
CREATE TABLE skills (
    skill_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          TEXT REFERENCES organizations(org_id),
    team_id         TEXT REFERENCES teams(team_id),
    name            TEXT NOT NULL,
    description     TEXT,
    source_type     TEXT NOT NULL,
    source_ref      TEXT,           -- Google Doc ID, etc.
    source_user     TEXT,           -- email of the person who shared
    gcs_path        TEXT NOT NULL,
    status          TEXT DEFAULT 'active',  -- active, archived, draft
    version         INTEGER DEFAULT 1,
    validation_result JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Processing event log (observability)
CREATE TABLE processing_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id        UUID REFERENCES skills(skill_id),
    stage           TEXT NOT NULL,  -- extract, analyze, generate, validate, deploy
    status          TEXT NOT NULL,  -- started, completed, failed
    duration_ms     INTEGER,
    details         JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Organization policy rules
CREATE TABLE policy_rules (
    rule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          TEXT REFERENCES organizations(org_id),
    rule_type       TEXT NOT NULL,  -- terminology, banned_content, required_section, style
    rule_config     JSONB NOT NULL,
    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. Pipeline Stages (Detail)

### 4.1 Extract

Responsible for pulling content from the source and normalizing it into `ProcessedContent`.

**Google Docs extractor:**
- Uses Google Docs API to read document structure (headings, paragraphs, lists, tables)
- Preserves heading hierarchy as section structure
- Extracts inline images → saves to assets
- Handles comments as supplementary context

**Google Slides extractor:**
- Uses Google Slides API to read slides in order
- Extracts: slide titles, bullet points, speaker notes, images
- Speaker notes treated as high-signal content (the user's verbal explanation)
- Reconstructs narrative flow from slide order

### 4.2 Analyze

Uses Claude to classify and structure the extracted content.

- **GTM use-case classification:** Maps input to one of the defined GTM categories (sales-enablement, lead-scoring, pipeline-management, etc.)
- **Complexity assessment:** simple / moderate / complex — drives how many reference files to generate
- **Entity extraction:** People names, company names, product names, processes
- **Structure detection:** Identifies if the content maps to a workflow, a reference guide, a playbook, or a decision tree

### 4.3 Generate

Uses Claude to produce the SKILL.md and any referenced asset files.

- Follows Anthropic's agent skill authoring best practices
- SKILL.md body stays under 500 lines
- Complex content is split into reference files (progressive disclosure)
- Generated skills include concrete examples relevant to the detected GTM use case
- Supports re-generation with validator feedback (max 2 iterations)

### 4.4 Validate & Comply

Multi-layer validation:

1. **Structural validation** (existing): YAML frontmatter rules, body length, reference depth
2. **Content linting** (new): Consistent terminology, no time-sensitive language, third-person voice
3. **Organization policy checks** (new): Custom rules loaded from AlloyDB per org
   - Banned terminology or competitor mentions
   - Required sections (e.g., every skill must have a "Compliance" section)
   - Style rules (tone, formality level)
   - PII detection and redaction
4. **Skill spec compliance**: Validates against the Claude Agent Skills specification

### 4.5 Deploy

- Writes the skill folder to GCS at the org-scoped path
- Records metadata in AlloyDB
- Emits a `SkillDeployed` event (Pub/Sub) for downstream consumers
- Poexis agents discover new/updated skills via GCS path convention or event subscription

---

## 5. MVP Scope

The MVP delivers a focused, end-to-end flow:

**Input:** User shares a Google Doc or Google Slides deck with the Skill Whisperer service account.

**Processing:** The service extracts content, analyzes it, generates a SKILL.md + asset files, validates the output, and deploys to GCS.

**Output:** A skill folder in GCS that Poexis agents can consume.

### MVP Includes

- Google Docs and Google Slides as input sources
- Google Drive webhook receiver to detect shared documents
- Full processing pipeline (extract → analyze → generate → validate → deploy)
- GCS deployment with org-scoped paths
- AlloyDB for skill metadata and basic org config
- Structural + content validation (no custom org policies yet)
- Health check and basic observability (structured logging)
- Terraform for Cloud Run, GCS, AlloyDB, IAM
- FastAPI with `/api/v1/skills/generate` endpoint (manual trigger fallback)

### MVP Excludes

- Voice agent input
- Custom organization policy rules
- Pub/Sub event bus (MVP uses synchronous processing)
- Platform admin UI
- Skill versioning and diff
- Multi-region deployment
- Batch processing

---

## 6. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Latency (end-to-end) | < 60s for a typical 10-page Google Doc |
| Availability | 99.5% (Cloud Run SLA) |
| Concurrent processing | 10 simultaneous skill generations (MVP) |
| Skill output quality | Zero structural validation errors; warnings acceptable |
| Tenant isolation | Org-scoped GCS paths; no cross-org data leakage |
| Observability | Structured JSON logs; per-stage duration tracking |
| Security | Service account with least-privilege IAM; no user credentials stored |

---

## 7. Future Phases (Preview)

| Phase | Capability |
|-------|------------|
| **Phase 2 — Policies & Compliance** | Org-specific policy rules, PII detection, compliance audit trail |
| **Phase 3 — Voice Agent** | Interview-style voice input via telephony integration |
| **Phase 4 — Event-Driven Pipeline** | Pub/Sub decoupling, async processing, retry/DLQ |
| **Phase 5 — Multi-Experience** | Slack bot, email ingestion, Chrome extension |
| **Phase 6 — Enterprise** | Multi-region, RBAC, skill versioning, approval workflows |
