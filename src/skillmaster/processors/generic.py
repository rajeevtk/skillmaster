from skillmaster.processors import ProcessedInput


async def process(content: str, metadata: dict) -> ProcessedInput:
    """Fallback processor for unstructured/unknown input types.

    Passes content through with minimal processing. The Claude agent
    in the pipeline will classify and extract relevant information.
    """
    return ProcessedInput(
        raw_text=content,
        source_type="generic",
        structured_sections=[{"title": "Input", "body": content}],
        metadata=metadata,
    )
