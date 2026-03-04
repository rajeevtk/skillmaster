import re

from skillmaster.processors import ProcessedInput


async def process(content: str, metadata: dict) -> ProcessedInput:
    """Process voice transcript input.

    Accepts pre-transcribed text. For audio files, integrate with
    Google Cloud Speech-to-Text or Whisper in a future phase.
    """
    # Clean up common transcript artifacts
    cleaned = content
    # Remove filler words
    filler_pattern = r"\b(um|uh|like|you know|I mean|so|basically|actually|right)\b"
    cleaned = re.sub(filler_pattern, "", cleaned, flags=re.IGNORECASE)
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Try to detect speaker turns (e.g., "Speaker 1:", "[John]:", etc.)
    speaker_pattern = re.compile(r"(?:^|\n)\s*(?:\[?(?:Speaker\s*\d+|[A-Z][a-z]+)\]?\s*:)")
    segments = speaker_pattern.split(cleaned)
    speakers = speaker_pattern.findall(cleaned)

    sections = []
    for i, segment in enumerate(segments):
        segment = segment.strip()
        if not segment:
            continue
        title = speakers[i - 1].strip().rstrip(":") if i > 0 and i - 1 < len(speakers) else f"Segment {i + 1}"
        sections.append({"title": title, "body": segment})

    if not sections:
        sections = [{"title": "Transcript", "body": cleaned}]

    return ProcessedInput(
        raw_text=content,
        source_type="voice_transcript",
        structured_sections=sections,
        metadata=metadata,
    )
