import pytest

from skillmaster.processors.plaintext import process as process_plaintext
from skillmaster.processors.voice import process as process_voice
from skillmaster.processors.interview import process as process_interview
from skillmaster.processors.generic import process as process_generic


@pytest.mark.asyncio
async def test_plaintext_detects_headings():
    content = "# Overview\nSome text here\n## Details\nMore details"
    result = await process_plaintext(content, {})
    assert result.source_type == "plain_text"
    assert len(result.structured_sections) == 2
    assert result.structured_sections[0]["title"] == "Overview"
    assert result.structured_sections[1]["title"] == "Details"


@pytest.mark.asyncio
async def test_plaintext_no_headings():
    content = "Just a plain paragraph with no headings."
    result = await process_plaintext(content, {})
    assert len(result.structured_sections) == 1
    assert result.structured_sections[0]["title"] == "Overview"


@pytest.mark.asyncio
async def test_voice_cleans_filler_words():
    content = "So um basically we need to like improve the pipeline"
    result = await process_voice(content, {})
    assert "um" not in result.structured_sections[0]["body"]
    assert "basically" not in result.structured_sections[0]["body"]


@pytest.mark.asyncio
async def test_voice_detects_speakers():
    content = "Speaker 1: Hello there\nSpeaker 2: How are you"
    result = await process_voice(content, {})
    assert result.source_type == "voice_transcript"


@pytest.mark.asyncio
async def test_interview_parses_qa():
    content = "Q: What is your biggest challenge?\nA: Lead qualification is slow.\nQ: How do you handle it?\nA: Manual review."
    result = await process_interview(content, {})
    assert result.source_type == "interview"
    assert len(result.structured_sections) >= 1


@pytest.mark.asyncio
async def test_generic_passthrough():
    content = "Some unstructured content here"
    result = await process_generic(content, {})
    assert result.source_type == "generic"
    assert result.raw_text == content
