import chromadb

from app.core.config import get_settings


def _make_client() -> chromadb.HttpClient:
    settings = get_settings()
    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)


def search_chunks(
    collection_name: str,
    query_embedding: list[float],
    k: int,
) -> list[dict]:
    """Query ChromaDB for the k most similar chunks to query_embedding.

    Returns a list of dicts with keys: id, document, metadata, distance.
    Raises RuntimeError on any ChromaDB connectivity or operation failure.
    """
    try:
        client = _make_client()
        collection = client.get_or_create_collection(name=collection_name)
        count = collection.count()
        if count == 0:
            return []
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, count),
            include=["documents", "metadatas", "distances"],
        )
        ids = result["ids"][0]
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]
        return [
            {
                "id": ids[i],
                "document": documents[i],
                "metadata": metadatas[i],
                "distance": distances[i],
            }
            for i in range(len(ids))
        ]
    except Exception as exc:
        raise RuntimeError(f"ChromaDB operation failed: {exc}") from exc


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
