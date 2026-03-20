# Skill Whisperer — Service Specification

## What Is Skill Whisperer

Skill Whisperer converts unstructured knowledge from non-technical business users into validated agent skill definitions. A salesperson describes how they work — in a Google Doc, a slide deck, or eventually a voice conversation — and Skill Whisperer produces a structured `SKILL.md` with supporting asset files, tagged with a three-level ownership hierarchy and arbitrary metadata.

Skill Whisperer's scope ends at producing the skill bundle. Deployment to runtime infrastructure, lifecycle management (versioning, archival, promotion), and agent consumption are handled by separate downstream services that read Skill Whisperer's output.

---

## Scope Boundaries

### Skill Whisperer owns:

- Ingesting content from input sources (Google Docs, Slides, future: voice)
- Extracting and normalizing that content
- Analyzing it to determine structure and use case
- Generating a valid SKILL.md + asset files compliant with the agent skills spec
- Validating and linting the output
- Applying organization compliance policies
- Tagging the skill bundle with ownership (user/project/org) and arbitrary metadata
- Writing the tagged skill bundle to GCS as its output location

### Skill Whisperer does NOT own:

- Infrastructure provisioning or deployment orchestration
- Skill lifecycle management (versioning, archival, promotion, deprecation)
- Agent runtime or skill discovery
- Skill consumption by Poexis agents or any other consumer
- Approval workflows or publishing gates

Downstream services read the skill bundles from GCS and handle everything from there. The tag hierarchy on each skill bundle is the contract that enables those services to route, filter, and manage skills.

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

### The Platform Admin (Phase 2+)

A technical user who configures organization policies, compliance rules, and pipeline settings via API.

---

## 2. Skill Tagging Model

Every skill bundle produced by Skill Whisperer carries a tag envelope. This is the primary contract between Skill Whisperer and all downstream services (lifecycle management, agent routing, analytics, etc.).

### Three-Level Ownership Hierarchy

```
org
 └── project
      └── user
```

| Level | What it represents | Example |
|-------|--------------------|---------|
| **org** | The top-level organization or company | `acme-corp` |
| **project** | A workstream, account, campaign, or initiative within the org | `enterprise-west-q2`, `acme-healthcare-vertical` |
| **user** | The individual who created the skill | `jdoe@acme.com` |

Every skill MUST have all three levels populated. This gives downstream services a consistent, hierarchical key to:
- **Route** skills to the right agent or team
- **Filter** skills by scope (all of an org's skills, all skills for a project, a user's personal skills)
- **Enforce** access policies (lifecycle services can gate by org/project)
- **Aggregate** analytics (skills created per project, per user)

### Arbitrary Metadata Tags

In addition to the ownership hierarchy, each skill carries a flat set of key-value tags. These are freeform — Skill Whisperer writes them, downstream services interpret them.

**Auto-populated tags** (Skill Whisperer sets these during generation):

| Tag | Description | Example value |
|-----|-------------|---------------|
| `source_type` | Input source that produced this skill | `google_docs`, `google_slides`, `voice` |
| `source_ref` | Reference to the original document | `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms` |
| `gtm_use_case` | Detected GTM category | `demand-generation`, `objection-handling`, `account-planning` |
| `complexity` | Assessed complexity level | `simple`, `moderate`, `complex` |
| `structure_type` | Detected content structure | `playbook`, `reference-guide`, `workflow`, `profile-collection` |
| `generated_at` | ISO8601 timestamp of generation | `2026-03-20T14:30:00Z` |
| `pipeline_version` | Version of the Skill Whisperer pipeline | `1.0.0` |

**User-supplied tags** (passed in via API or inferred from the document):

Users or the ingestion layer can attach additional tags. Examples:
- `account: globex-industries`
- `region: west`
- `quarter: q2-2026`
- `confidentiality: internal`
- `team: enterprise-sales`

### Tag Envelope (in metadata.json)

```json
{
  "skill_id": "uuid",
  "ownership": {
    "org": "acme-corp",
    "project": "enterprise-west-q2",
    "user": "jdoe@acme.com"
  },
  "tags": {
    "source_type": "google_docs",
    "source_ref": "1BxiMVs0XRA...",
    "gtm_use_case": "demand-generation",
    "complexity": "moderate",
    "structure_type": "playbook",
    "generated_at": "2026-03-20T14:30:00Z",
    "pipeline_version": "1.0.0",
    "account": "globex-industries",
    "region": "west",
    "quarter": "q2-2026"
  },
  "validation": {
    "is_valid": true,
    "errors": [],
    "warnings": ["Description uses first-person voice"]
  }
}
```

### GCS Output Path Convention

Skill bundles are written to GCS using the ownership hierarchy as the path:

```
gs://{bucket}/{org}/{project}/{skill_id}/
├── SKILL.md
├── metadata.json          ← contains the full tag envelope
└── assets/
    ├── stakeholders.md
    ├── playbook.md
    └── ...
```

Downstream services use the path structure and `metadata.json` to discover, filter, and manage skills. Skill Whisperer writes here; it never reads back or manages what's already there.

---

## 3. Core Workflow

```
 End User                    Skill Whisperer
 ────────                    ───────────────

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
                     │  Auto-populate tags.    │
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
                     │  6. OUTPUT              │
                     │  Write tagged skill     │
                     │  bundle to GCS.         │
                     │  Record in AlloyDB.     │
                     │                         │
                     │  Skill Whisperer's job  │
                     │  ends here.             │
                     └─────────────────────────┘
```

---

## 4. Architecture Principles

**Loosely coupled pipelines.** Each stage (extract, analyze, generate, validate) is an independent component with a clear input/output contract. Swapping or adding a new extractor (e.g., voice) does not require changes to the generator or validator.

**Observable.** Every pipeline stage emits structured logs with a correlation ID that follows the request from ingestion through output. Stage durations, errors, and outcomes are recorded in AlloyDB for debugging and analytics.

**Extensible input sources.** The MVP supports Google Docs and Google Slides. The architecture treats these as pluggable "extractors" behind a common interface. Adding voice, Slack, email, or any other input source means writing a new extractor — the rest of the pipeline is unchanged.

**Idempotent processing.** Re-processing the same document at the same revision produces the same output. Safe to retry on failure.

**Tags as the downstream contract.** Skill Whisperer doesn't know or care what happens after the skill bundle is written. The tag envelope (ownership hierarchy + metadata tags) is the interface that downstream services use to do their jobs.

---

## 5. System Architecture

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
│  Google Drive Webhook Receiver                                   │
│  - Detects shares / edits                                        │
│  - Determines document type (Doc vs Slides)                      │
│  - Resolves ownership tags (org/project/user)                    │
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
│  │          │   │ + Tag    │   │          │   │   Comply      │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────┘ │
│                                                                  │
│  Each stage: independent, traced, retryable                      │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    OUTPUT (GCS)                                   │
│                                                                  │
│  gs://{bucket}/{org}/{project}/{skill_id}/                       │
│  ├── SKILL.md              # The skill definition                │
│  ├── metadata.json         # Tag envelope (ownership + tags)     │
│  └── assets/               # Referenced supporting files         │
│                                                                  │
│  Skill Whisperer writes here and walks away.                     │
│  Downstream services (lifecycle, routing, agents) take over.     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Stores

Skill Whisperer uses two data stores:

| Store | Purpose |
|-------|---------|
| **Google Cloud Storage** | Write-only output. Skill bundles land here for downstream consumption. |
| **AlloyDB (PostgreSQL)** | Operational state: org config, processing event log, dedup tracking. NOT the system of record for skill lifecycle — that's downstream. |

### AlloyDB Schema

```sql
-- Organization configuration
CREATE TABLE organizations (
    org_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    gcs_bucket      TEXT NOT NULL,
    config          JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Project configuration (within an org)
CREATE TABLE projects (
    project_id      TEXT PRIMARY KEY,
    org_id          TEXT REFERENCES organizations(org_id),
    name            TEXT NOT NULL,
    default_tags    JSONB DEFAULT '{}',   -- tags auto-applied to all skills in this project
    config          JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Tracks what Skill Whisperer has produced (for dedup and observability, NOT lifecycle)
CREATE TABLE skill_outputs (
    skill_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          TEXT REFERENCES organizations(org_id),
    project_id      TEXT REFERENCES projects(project_id),
    user_email      TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    source_type     TEXT NOT NULL,
    source_ref      TEXT,
    source_revision TEXT,             -- for dedup: same doc + revision = skip
    gcs_path        TEXT NOT NULL,
    tags            JSONB NOT NULL,   -- full tag envelope snapshot
    validation_result JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Processing event log (observability)
CREATE TABLE processing_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id        UUID REFERENCES skill_outputs(skill_id),
    stage           TEXT NOT NULL,    -- extract, analyze, generate, validate, output
    status          TEXT NOT NULL,    -- started, completed, failed
    duration_ms     INTEGER,
    details         JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Phase 2+
CREATE TABLE policy_rules (
    rule_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          TEXT REFERENCES organizations(org_id),
    rule_type       TEXT NOT NULL,
    rule_config     JSONB NOT NULL,
    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

Note: `skill_outputs` is an output log, not a lifecycle table. It tracks "what did Skill Whisperer produce and when" for deduplication and debugging. It has no `status`, `version`, or `updated_at` fields — those concepts belong to downstream lifecycle services.

---

## 7. Pipeline Stage Detail

### 7.1 Extract

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

### 7.2 Analyze + Tag

Uses Claude to understand what the user wrote and how to structure it as a skill. Also populates the auto-generated tags.

- Classifies the GTM use case (demand gen, account planning, objection handling, competitive intel, etc.)
- Assesses complexity (simple reference vs. multi-step workflow)
- Extracts named entities (people, companies, products)
- Detects structure: is this a playbook? a reference guide? a decision tree? a workflow?
- Populates auto-tags: `gtm_use_case`, `complexity`, `structure_type`
- Merges with user-supplied tags and project default tags

### 7.3 Generate

Uses Claude to produce the actual skill definition files.

- Generates `SKILL.md` following the agent skills specification
  - Valid YAML frontmatter (`name`, `description`)
  - Body under 500 lines
  - Progressive disclosure: complex content split into referenced asset files
  - Concrete examples relevant to the detected use case
- Generates referenced asset files (stakeholder profiles, playbooks, guidelines, etc.)
- Supports a feedback loop: if validation fails, re-generates with error context (max 2 retries)

### 7.4 Validate & Comply

Multi-layer checks before a skill is output:

1. **Structural validation** — YAML frontmatter rules, body length limits, reference depth
2. **Content linting** — Consistent terminology, no time-sensitive language, appropriate tone
3. **Org policy checks (Phase 2+)** — Custom rules per organization:
   - Banned terms (competitor names, profanity)
   - Required sections
   - Terminology enforcement
   - PII detection and redaction
4. **Agent skills spec compliance** — Validates the output is a well-formed skill definition

Violations can be **blocking** (skill not output) or **warning** (output with flag in metadata).

### 7.5 Output

- Writes the skill folder to GCS at `gs://{bucket}/{org}/{project}/{skill_id}/`
- Includes `metadata.json` with the full tag envelope
- Records the output in AlloyDB `skill_outputs` for dedup and observability
- Logs a processing event for the output stage
- That's it. Skill Whisperer is done.

---

## 8. MVP Scope

### In Scope

- **Google Docs** as an input source — share a doc, get a skill
- **Google Slides** as an input source — share a deck, get a skill
- **Google Drive webhook receiver** — detects shares, triggers processing
- **Full processing pipeline** — extract, analyze, generate, validate, output
- **Tag envelope** — three-level ownership hierarchy + auto-populated and user-supplied tags
- **GCS output** — tagged skill bundles at `{org}/{project}/{skill_id}/`
- **AlloyDB** — org/project config, processing event log, dedup tracking
- **Manual API trigger** — `POST /api/v1/skills/generate` as fallback
- **Structural + content validation** — no custom org policies yet
- **Structured logging** with correlation IDs
- **Health and readiness endpoints**

### Out of Scope (MVP and beyond — not this service)

- Infrastructure provisioning (Terraform is a separate concern)
- Skill lifecycle management (versioning, archival, promotion, deprecation)
- Skill consumption / agent runtime
- Approval workflows or publishing gates
- Admin UI for skill management

### Out of Scope (MVP only — future phases of this service)

- Voice agent input
- Custom organization policy rules
- Pub/Sub event bus (synchronous processing in MVP)
- Batch processing
- Slack, email, or browser extension inputs

---

## 9. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| End-to-end latency | < 60 seconds for a typical 10-page document |
| Concurrent processing | 10 simultaneous generations (MVP) |
| Skill output quality | Zero structural errors; warnings acceptable |
| Tenant isolation | Org-scoped GCS paths; no cross-org data leakage |
| Observability | Structured JSON logs; per-stage duration tracking in AlloyDB |
| Idempotency | Same document + revision = same output; no duplicate processing |

---

## 10. Phase Roadmap

| Phase | Name | What It Adds |
|-------|------|-------------|
| **1 — MVP** | Google Docs to GCS | Docs/Slides input, full pipeline, tagged skill bundles to GCS |
| **2 — Policies** | Org Compliance | Custom policy rules engine, policy CRUD API, compliance audit trail |
| **3 — Voice** | Interview Agent | Voice agent conducts structured interviews, captures into skills |
| **4 — Events** | Async Pipeline | Pub/Sub decoupling, async processing, retry/DLQ |
| **5 — Multi-Experience** | More Input Sources | Slack bot, email ingestion, Chrome extension |
