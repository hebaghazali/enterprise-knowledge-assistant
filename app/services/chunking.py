import re

from transformers import AutoTokenizer

# Loaded once at import time; cached in ~/.cache/huggingface after first download.
_TOKENIZER = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")


def _clean_text(text: str) -> str:
    """Light cleanup to make chunk text human-readable for storage and display.

    - Normalizes line endings.
    - Removes lines that are purely separator characters (4+ repeated =, -, _, *, ~, #).
    - Collapses runs of spaces/tabs within a line to a single space.
    - Collapses 3+ consecutive blank lines to 2.
    - Strips leading/trailing whitespace per line.
    Does NOT lowercase text or alter punctuation.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Lines consisting entirely of 4+ repeated separator chars are decorative — remove them.
    text = re.sub(r"^[ \t]*[=\-_*~#]{4,}[ \t]*$", "", text, flags=re.MULTILINE)
    # Collapse runs of spaces/tabs within a line.
    text = re.sub(r"[ \t]+", " ", text)
    # At most two consecutive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip each line individually, then strip the whole result.
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


def count_query_tokens(query: str) -> int:
    """Return the token count for a search query using the all-MiniLM-L6-v2 tokenizer."""
    return estimate_token_count(query)


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
    tokens, not characters. The tokenizer's character offset mapping is used to slice
    the *original text* at token boundaries — no token ID decoding. This preserves
    the original casing, punctuation, and spacing exactly as written.

    Each chunk's text is then lightly cleaned (separator lines removed, whitespace
    collapsed) before being returned as the display/storage string.

    Token count per chunk is the exact slice length (end - start).

    Algorithm (step = chunk_size - chunk_overlap):
        chunk 0 : tokens[0          : chunk_size]
        chunk 1 : tokens[step       : step + chunk_size]
        chunk 2 : tokens[step*2     : step*2 + chunk_size]
        ...

    Example: 9 tokens, chunk_size=5, chunk_overlap=2 (step=3)
        chunk 0: tokens[0:5]  → 5 tokens
        chunk 1: tokens[3:8]  → 5 tokens  (2-token overlap with chunk 0)
        chunk 2: tokens[6:9]  → 3 tokens  (2-token overlap with chunk 1)

    Returns a list of (display_text, token_count) tuples in chunk order.

    The caller is responsible for validating chunk_size > 0, chunk_overlap >= 0,
    and chunk_overlap < chunk_size before calling this function.
    """
    if not text.strip():
        return []

    encoding = _TOKENIZER(
        text,
        add_special_tokens=False,
        return_offsets_mapping=True,
        truncation=False,
    )
    token_ids = encoding["input_ids"]
    offset_mapping = encoding["offset_mapping"]

    if not token_ids:
        return []

    if len(token_ids) <= chunk_size:
        char_start = offset_mapping[0][0]
        char_end = offset_mapping[-1][1]
        display = _clean_text(text[char_start:char_end])
        if display:
            return [(display, len(token_ids))]
        return []

    step = max(1, chunk_size - chunk_overlap)
    chunks: list[tuple[str, int]] = []
    start = 0
    while start < len(token_ids):
        end = min(start + chunk_size, len(token_ids))
        char_start = offset_mapping[start][0]
        char_end = offset_mapping[end - 1][1]
        display = _clean_text(text[char_start:char_end])
        if display:
            chunks.append((display, end - start))
        if end >= len(token_ids):
            break
        start += step

    return chunks
