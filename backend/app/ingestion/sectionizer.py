"""Groups extracted blocks into sections by heading, keeping tables inline.

Falls back to token-based chunking when a document has no detectable heading
structure (e.g. a single wall of text), so every document — however it's
formatted — always ends up as a list of reasonably sized sections.
"""

import tiktoken

from app.ingestion.extract import extract_blocks

ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def group_blocks_into_sections(blocks: list[dict]) -> list[dict]:
    sections: list[dict] = []
    current = None
    for block in blocks:
        if block["kind"] == "heading":
            if current and current["content"].strip():
                sections.append(current)
            current = {"title": block["text"], "content": "", "table_count": 0}
        else:
            if current is None:
                current = {"title": "Introduction", "content": "", "table_count": 0}
            current["content"] += block["text"] + "\n\n"
            if block["kind"] == "table":
                current["table_count"] += 1
    if current and current["content"].strip():
        sections.append(current)
    return sections


def chunk_by_tokens(blocks: list[dict], chunk_size: int = 3000, overlap: int = 300) -> list[dict]:
    full_text = "\n\n".join(b["text"] for b in blocks)
    tokens = ENCODING.encode(full_text)
    chunks = []
    start = 0
    chunk_num = 1
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_text = ENCODING.decode(tokens[start:end])
        chunks.append({"title": f"Section {chunk_num}", "content": chunk_text, "table_count": chunk_text.count("[TABLE")})
        chunk_num += 1
        start += chunk_size - overlap
    return chunks


def build_section_map(file_path: str) -> dict:
    extraction = extract_blocks(file_path)
    if "error" in extraction:
        return extraction

    blocks = extraction["blocks"]
    sections = group_blocks_into_sections(blocks)
    detection_method = "heading_based"

    if len(sections) < 2:
        sections = chunk_by_tokens(blocks)
        detection_method = "token_chunked"

    for i, section in enumerate(sections):
        section["sec_id"] = f"S-{i + 1:03d}"
        section["token_count"] = count_tokens(section["title"] + " " + section["content"])

    total_tokens = sum(s["token_count"] for s in sections)
    return {
        "sections": sections,
        "total_tokens": total_tokens,
        "section_count": len(sections),
        "table_count": extraction["table_count"],
        "detection_method": detection_method,
        "processing_mode": "single" if total_tokens <= 80000 else "chunked",
    }
