import pytest
from httpx import ASGITransport, AsyncClient

from skillmaster.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_validate_valid_skill(client):
    skill_md = """---
name: scoring-leads
description: Evaluates inbound leads against ICP criteria. Use when qualifying new MQLs or prioritizing outbound targets.
---

# Scoring Leads

## Quick start
Evaluate a lead against ICP criteria.
"""
    response = await client.post("/api/v1/skills/validate", json={"skill_md": skill_md})
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True


@pytest.mark.asyncio
async def test_validate_missing_frontmatter(client):
    response = await client.post("/api/v1/skills/validate", json={"skill_md": "# No frontmatter"})
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is False
    assert any("frontmatter" in e.lower() for e in data["errors"])
