import logging

from fastapi import FastAPI

from skillmaster.api.routes import router
from skillmaster.config import settings

logging.basicConfig(level=settings.skillmaster_log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Skill Master",
    description="Generate Claude Agent Skills for GTM use cases from plain text, voice transcripts, slides, interviews, and more.",
    version="0.1.0",
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
