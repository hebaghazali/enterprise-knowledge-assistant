from transformers import AutoTokenizer

# Loaded once at import time; cached in ~/.cache/huggingface after first download.
_TOKENIZER = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")


def estimate_token_count(text: str) -> int:
    """Return the number of tokens produced by the all-MiniLM-L6-v2 WordPiece tokenizer.

    Uses the same tokenizer as chunk_text(), so the count reflects real model
    token boundaries rather than whitespace splitting. Returns 0 for empty text.
    """
    if not text:
        return 0
    return len(_TOKENIZER.encode(text, add_special_tokens=False))


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[tuple[str, int]]:
    """Split text into overlapping TOKEN-based chunks using the all-MiniLM-L6-v2 tokenizer.

    Chunking is TOKEN-based: chunk_size and chunk_overlap are measured in tokenizer
    tokens, not characters. The text is first encoded to token IDs, then sliced
    with a sliding window, and each slice is decoded back to a string.

    Token count per chunk is the exact slice length (end - start), not a
    re-encoding of the decoded text, so it is always precise.

    Algorithm (step = chunk_size - chunk_overlap):
        chunk 0 : token_ids[0          : chunk_size]
        chunk 1 : token_ids[step       : step + chunk_size]
        chunk 2 : token_ids[step*2     : step*2 + chunk_size]
        ...

    Example: 9 tokens, chunk_size=5, chunk_overlap=2 (step=3)
        chunk 0: tokens[0:5]  → 5 tokens
        chunk 1: tokens[3:8]  → 5 tokens  (2-token overlap with chunk 0)
        chunk 2: tokens[6:9]  → 3 tokens  (2-token overlap with chunk 1)

    Returns a list of (decoded_text, token_count) tuples in chunk order.

    The caller is responsible for validating chunk_size > 0, chunk_overlap >= 0,
    and chunk_overlap < chunk_size before calling this function.
    """
    if not text.strip():
        return []

    token_ids = _TOKENIZER.encode(text, add_special_tokens=False)
    if not token_ids:
        return []

    if len(token_ids) <= chunk_size:
        decoded = _TOKENIZER.decode(token_ids, skip_special_tokens=True)
        return [(decoded, len(token_ids))]

    step = max(1, chunk_size - chunk_overlap)
    chunks: list[tuple[str, int]] = []
    start = 0
    while start < len(token_ids):
        end = min(start + chunk_size, len(token_ids))
        slice_ids = token_ids[start:end]
        decoded = _TOKENIZER.decode(slice_ids, skip_special_tokens=True)
        if decoded.strip():
            chunks.append((decoded, end - start))
        if end >= len(token_ids):
            break
        start += step

    return chunks
