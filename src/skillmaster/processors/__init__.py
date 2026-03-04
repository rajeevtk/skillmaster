from dataclasses import dataclass, field

from skillmaster.api.models import InputType


@dataclass
class ProcessedInput:
    raw_text: str
    source_type: str
    structured_sections: list[dict] = field(default_factory=list)  # [{"title": ..., "body": ...}]
    metadata: dict = field(default_factory=dict)


async def process_input(input_type: InputType, content: str, metadata: dict) -> ProcessedInput:
    """Route input to the appropriate processor."""
    if input_type == InputType.PLAIN_TEXT:
        from skillmaster.processors.plaintext import process
        return await process(content, metadata)
    elif input_type == InputType.VOICE_TRANSCRIPT:
        from skillmaster.processors.voice import process
        return await process(content, metadata)
    elif input_type == InputType.GOOGLE_SLIDES:
        from skillmaster.processors.slides import process
        return await process(content, metadata)
    elif input_type == InputType.INTERVIEW:
        from skillmaster.processors.interview import process
        return await process(content, metadata)
    else:
        from skillmaster.processors.generic import process
        return await process(content, metadata)
