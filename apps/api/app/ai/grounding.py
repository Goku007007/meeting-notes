from typing import Any


def _normalize(s: str) -> str:
    # Normalize whitespace/casing so matching is resilient to formatting differences.
    return " ".join(s.lower().split())


def validate_citations(
    citations: list[dict[str, Any]] | None,
    chunk_text_by_id: dict[str, str],
    max_quote_chars: int = 200,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """
    Returns (valid_citations, invalid_citations).
    A citation is invalid if:
      - chunk_id not in retrieved set
      - quote missing/too long
      - quote not found in that chunk (after normalization)
    """
    valid: list[dict[str, str]] = []
    invalid: list[dict[str, Any]] = []

    for c in citations or []:
        chunk_id = str(c.get("chunk_id", "")).strip()
        quote = str(c.get("quote", "")).strip()

        # Prevent citing chunks that were not retrieved for this answer.
        if not chunk_id or chunk_id not in chunk_text_by_id:
            invalid.append({**c, "reason": "chunk_id_not_allowed"})
            continue

        if not quote:
            invalid.append({**c, "reason": "missing_quote"})
            continue

        if len(quote) > max_quote_chars:
            invalid.append({**c, "reason": "quote_too_long"})
            continue

        haystack = _normalize(chunk_text_by_id[chunk_id])
        needle = _normalize(quote)
        if needle not in haystack:
            invalid.append({**c, "reason": "quote_not_in_chunk"})
            continue

        valid.append({"chunk_id": chunk_id, "quote": quote})

    return valid, invalid
