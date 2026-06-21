from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

# Loaded lazily on first use; cached for the process lifetime.
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(get_settings().embedding_model_name, device="cpu")
    return _model


def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a Python list of floats."""
    return _get_model().encode(text).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Returns a list of float lists, one per input text."""
    return _get_model().encode(texts).tolist()
