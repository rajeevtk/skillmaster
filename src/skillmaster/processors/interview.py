import re

from skillmaster.processors import ProcessedInput


async def process(content: str, metadata: dict) -> ProcessedInput:
    """Process user interview transcripts.

    Extracts Q&A pairs, identifies pain points, workflows, requirements,
    and GTM-specific patterns.
    """
    sections = []

    # Detect Q&A pattern (Q: ... A: ... or Interviewer: ... Respondent: ...)
    qa_pattern = re.compile(
        r"(?:^|\n)\s*(?:Q|Question|Interviewer)\s*[:\.]?\s*(.+?)(?=\n\s*(?:A|Answer|Respondent)\s*[:\.]?)",
        re.IGNORECASE | re.DOTALL,
    )
    answer_pattern = re.compile(
        r"(?:^|\n)\s*(?:A|Answer|Respondent)\s*[:\.]?\s*(.+?)(?=\n\s*(?:Q|Question|Interviewer)\s*[:\.]?|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    questions = qa_pattern.findall(content)
    answers = answer_pattern.findall(content)

    if questions and answers:
        for i, (q, a) in enumerate(zip(questions, answers), 1):
            sections.append({
                "title": f"Q{i}: {q.strip()[:80]}",
                "body": a.strip(),
            })
    else:
        # Fallback: split by paragraphs
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs, 1):
            sections.append({"title": f"Section {i}", "body": para})

    return ProcessedInput(
        raw_text=content,
        source_type="interview",
        structured_sections=sections,
        metadata=metadata,
    )
