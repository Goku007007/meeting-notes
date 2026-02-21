def chunk_text(text: str, max_chars: int = 1200, overlap: int = 200) -> list[str]:
    # basic safety checks
    text = text.strip()
    if not text:
        return []

    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")
    
    chunks: list[str] = []
    start = 0

    # 2) slide a window across the text
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == len(text):
            break  # we reached the end

        # 3) move start forward, but keep some overlap
        start = end - overlap

    return chunks