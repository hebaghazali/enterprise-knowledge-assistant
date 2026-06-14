from app.core.config import get_settings
from app.schemas.retrieval import SearchResultResponse
from app.services.embeddings import embed_text
from app.services.vector_store import search_chunks


def retrieve(query: str, k: int) -> list[SearchResultResponse]:
    """Embed query, search ChromaDB, return ranked SearchResultResponse list."""
    settings = get_settings()
    query_embedding = embed_text(query)
    raw = search_chunks(
        collection_name=settings.chroma_collection_name,
        query_embedding=query_embedding,
        k=k,
    )
    results = []
    for item in raw:
        meta = item["metadata"]
        similarity_score = round(1 / (1 + item["distance"]), 4)
        results.append(
            SearchResultResponse(
                chunk_id=item["id"],
                document_id=meta.get("document_id", ""),
                filename=meta.get("filename", ""),
                chunk_index=int(meta.get("chunk_index", 0)),
                content=item["document"],
                token_count=meta.get("token_count"),
                similarity_score=similarity_score,
            )
        )
    return results
