from app.schemas.retrieval import SearchResultResponse


def build_prompt(question: str, chunks: list[SearchResultResponse]) -> str:
    context_blocks = []
    for i, chunk in enumerate(chunks, start=1):
        block = (
            f"[Source {i}]\n"
            f"Filename: {chunk.filename}\n"
            f"Chunk ID: {chunk.chunk_id}\n"
            f"Content:\n{chunk.content}"
        )
        context_blocks.append(block)

    context = "\n\n".join(context_blocks)

    return (
        "You are an enterprise knowledge assistant.\n\n"
        "Answer the user's question using ONLY the context provided below.\n\n"
        "Rules:\n"
        '- If the answer is not present in the context, say: "I don\'t know based on the provided documents."\n'
        "- Do not invent facts, policies, numbers, names, or procedures.\n"
        "- Keep the answer concise and direct.\n"
        "- Prefer the most relevant context when multiple chunks overlap.\n\n"
        f"Question:\n{question}\n\n"
        f"Context:\n{context}\n\n"
        "Answer:"
    )
