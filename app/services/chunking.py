from transformers import AutoTokenizer

# Loaded once at import time; cached in ~/.cache/huggingface after first download.
_TOKENIZER = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")


def estimate_token_count(text: str) -> int:
    """Return the number of tokens produced by the all-MiniLM-L6-v2 WordPiece tokenizer.

    Uses the same tokenizer that will be used for embedding in PR 6, so the
    count reflects real model token boundaries rather than whitespace splitting.
    Returns 0 for empty text.
    """
    if not text:
        return 0
    return len(_TOKENIZER.encode(text, add_special_tokens=False))


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """Split text into overlapping character-based chunks.

    Chunking is CHARACTER-based: chunk_size and chunk_overlap are measured in
    characters, not words or tokenizer tokens. Character boundaries are simple
    and require no tokenizer overhead during splitting.

    Token counts are measured separately after each chunk is created, using the
    all-MiniLM-L6-v2 WordPiece tokenizer (see estimate_token_count). A 500-char
    chunk of English prose typically contains 80–120 tokens; the two units are
    independent and do not influence each other.

    Future improvement: switch to token-based chunking using the same tokenizer
    so chunk_size directly controls the token budget fed to the embedding model.

    The caller is responsible for validating chunk_size > 0, chunk_overlap >= 0,
    and chunk_overlap < chunk_size before calling this function.

    Example: text="ABCDEFGHIJ", chunk_size=5, chunk_overlap=2  (step=3)
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
