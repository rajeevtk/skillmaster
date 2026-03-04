from skillmaster.processors import ProcessedInput


async def process(content: str, metadata: dict) -> ProcessedInput:
    """Process Google Slides content.

    Accepts either:
    - Pre-extracted slide text (content is the text)
    - A Google Slides presentation ID (requires Google API credentials in metadata)

    For presentation IDs, uses the Google Slides API to extract:
    - Slide titles, bullet points, speaker notes
    - Reconstructs narrative flow from slide order
    """
    slides_id = metadata.get("presentation_id")

    if slides_id:
        sections = await _extract_from_api(slides_id, metadata)
        raw_text = "\n\n".join(f"## {s['title']}\n{s['body']}" for s in sections)
    else:
        # Content is pre-extracted slide text
        sections = _parse_slide_text(content)
        raw_text = content

    return ProcessedInput(
        raw_text=raw_text,
        source_type="google_slides",
        structured_sections=sections,
        metadata=metadata,
    )


async def _extract_from_api(presentation_id: str, metadata: dict) -> list[dict]:
    """Extract slide content via Google Slides API."""
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    creds_info = metadata.get("google_credentials")
    if not creds_info:
        raise ValueError("google_credentials required in metadata for Slides API access")

    creds = Credentials.from_authorized_user_info(creds_info)
    service = build("slides", "v1", credentials=creds)
    presentation = service.presentations().get(presentationId=presentation_id).execute()

    sections = []
    for i, slide in enumerate(presentation.get("slides", []), 1):
        title = ""
        body_parts = []
        notes = ""

        for element in slide.get("pageElements", []):
            shape = element.get("shape", {})
            text_content = shape.get("text", {})
            placeholder_type = shape.get("placeholder", {}).get("type", "")

            text = _extract_text_from_elements(text_content)
            if placeholder_type == "TITLE" or placeholder_type == "CENTERED_TITLE":
                title = text
            elif text:
                body_parts.append(text)

        # Extract speaker notes
        notes_page = slide.get("slideProperties", {}).get("notesPage", {})
        for element in notes_page.get("pageElements", []):
            shape = element.get("shape", {})
            text_content = shape.get("text", {})
            placeholder_type = shape.get("placeholder", {}).get("type", "")
            if placeholder_type == "BODY":
                notes = _extract_text_from_elements(text_content)

        body = "\n".join(body_parts)
        if notes:
            body += f"\n\nSpeaker Notes: {notes}"

        sections.append({"title": title or f"Slide {i}", "body": body})

    return sections


def _extract_text_from_elements(text_content: dict) -> str:
    """Extract plain text from Slides text content structure."""
    parts = []
    for element in text_content.get("textElements", []):
        run = element.get("textRun", {})
        if run.get("content"):
            parts.append(run["content"])
    return "".join(parts).strip()


def _parse_slide_text(content: str) -> list[dict]:
    """Parse pre-extracted slide text into sections."""
    sections = []
    current_title = "Slide 1"
    current_body_lines: list[str] = []
    slide_num = 1

    for line in content.split("\n"):
        line_stripped = line.strip()
        if line_stripped.startswith("---") or line_stripped.lower().startswith("slide "):
            if current_body_lines:
                sections.append({"title": current_title, "body": "\n".join(current_body_lines).strip()})
            slide_num += 1
            current_title = line_stripped.lstrip("-").strip() or f"Slide {slide_num}"
            current_body_lines = []
        else:
            current_body_lines.append(line)

    if current_body_lines:
        sections.append({"title": current_title, "body": "\n".join(current_body_lines).strip()})

    return sections
