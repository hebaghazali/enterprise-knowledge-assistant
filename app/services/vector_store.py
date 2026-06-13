import chromadb

from app.core.config import get_settings


def _make_client() -> chromadb.HttpClient:
    settings = get_settings()
    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)


def upsert_chunks(
    collection_name: str,
    ids: list[str],
    documents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
) -> None:
    """Upsert chunk vectors into a ChromaDB collection.

    Raises RuntimeError on any ChromaDB connectivity or operation failure
    so the caller can map it to an appropriate HTTP status code.
    """
    try:
        client = _make_client()
        collection = client.get_or_create_collection(name=collection_name)
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
    except Exception as exc:
        raise RuntimeError(f"ChromaDB operation failed: {exc}") from exc
