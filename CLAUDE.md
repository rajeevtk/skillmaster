# Skill Master — Project Instructions

## What is this?

Skill Master is a Python service that generates Claude Agent Skills for GTM (Go-To-Market / Sales & Marketing) use cases. It accepts plain text, voice transcripts, Google Slides, user interviews, and other inputs — then uses the Claude Agent SDK to produce well-structured SKILL.md files following Anthropic's best practices.

## Tech Stack

- **Python 3.12+** with FastAPI
- **Claude Agent SDK** (`claude-code-sdk`) for agentic skill generation
- **Google Cloud Storage** for skill persistence
- **NeonDB** (serverless Postgres) for org/team configuration
- **Terraform** for GCP infrastructure (Cloud Run, GCS, IAM)

## Project Structure

```
src/skillmaster/          # Main application code
  main.py                 # FastAPI entrypoint
  config.py               # Pydantic Settings
  api/                    # REST endpoints and models
  processors/             # Input source processors (text, voice, slides, etc.)
  pipeline/               # Skill generation pipeline (orchestrator, analyzer, generator, validator)
  storage/                # GCS operations + bucket config resolution
  db/                     # NeonDB connection and queries
skills/skill-master/      # Skill Master's own skill definition
terraform/                # Infrastructure as code
tests/                    # pytest test suite
```

## Key Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run locally
uvicorn src.skillmaster.main:app --reload --port 8080

# Run tests
pytest tests/ -v

# Build Docker image
docker build -t skillmaster .

# Deploy infrastructure
cd terraform && terraform init && terraform apply
```

## Skills & Agents

See [Agents.md](Agents.md) for details on:
- How the skill generation pipeline works
- How to use the skill-master skill itself
- Claude Agent SDK patterns used in this project

See [skills/skill-master/SKILL.md](skills/skill-master/SKILL.md) for the Skill Master's own agent skill definition.

## Environment Variables

Copy `.env.example` to `.env` and fill in:
- `ANTHROPIC_API_KEY` — Required for Claude API access
- `SKILLMASTER_STORAGE_MODE` — `env` (default: use bucket from env var) or `db` (multi-tenant NeonDB lookup)
- `SKILLMASTER_GCS_BUCKET` — GCS bucket name (used when STORAGE_MODE=env)
- `SKILLMASTER_GCS_PROJECT` — GCP project ID for GCS client
- `NEONDB_URL` — NeonDB connection string (required when STORAGE_MODE=db)

## Development Guidelines

- Follow the implementation phases in [PLAN.md](PLAN.md)
- Generated skills must pass the validator in `src/skillmaster/pipeline/validator.py`
- All generated SKILL.md files must follow [Anthropic's skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- Keep generated skills concise (SKILL.md body < 500 lines)
- Use progressive disclosure: main SKILL.md references additional files
- Test with real GTM use cases before shipping
