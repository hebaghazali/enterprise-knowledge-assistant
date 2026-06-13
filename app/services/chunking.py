def estimate_token_count(text: str) -> int:
    return len(text.split())


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """Split text into overlapping character-based chunks.

    Example: text="ABCDEFGHIJ", chunk_size=5, chunk_overlap=2
    → ["ABCDE", "DEFGH", "GHIJ"]
    """
    if not text.strip():
        return []
    if len(text) <= chunk_size:
        return [text]

    step = max(1, chunk_size - chunk_overlap)
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(text):
            break
        start += step

    return chunks
