from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_EMBEDDING = [0.1] * 384

_CHROMA_RESULT = [
    {
        "id": "chunk-uuid-1",
        "document": "Employees must follow password security rules.",
        "metadata": {
            "document_id": "doc-uuid-1",
            "filename": "policy.txt",
            "chunk_index": 2,
            "token_count": 87,
        },
        "distance": 0.2,
    },
    {
        "id": "chunk-uuid-2",
        "document": "All passwords must be at least 12 characters.",
        "metadata": {
            "document_id": "doc-uuid-1",
            "filename": "policy.txt",
            "chunk_index": 3,
            "token_count": 60,
        },
        "distance": 0.5,
    },
]


# ---------------------------------------------------------------------------
# Retrieval service — unit tests
# ---------------------------------------------------------------------------


def test_retrieve_embeds_query():
    with (
        patch("app.services.retrieval.embed_text", return_value=_FAKE_EMBEDDING) as mock_embed,
        patch("app.services.retrieval.search_chunks", return_value=[]),
    ):
        from app.services.retrieval import retrieve

        retrieve("password rules", k=5)
        mock_embed.assert_called_once_with("password rules")


def test_retrieve_passes_embedding_to_search():
    with (
        patch("app.services.retrieval.embed_text", return_value=_FAKE_EMBEDDING),
        patch("app.services.retrieval.search_chunks", return_value=[]) as mock_search,
    ):
        from app.services.retrieval import retrieve

        retrieve("password rules", k=3)
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["query_embedding"] == _FAKE_EMBEDDING
        assert call_kwargs["k"] == 3


def test_retrieve_transforms_chroma_payload():
    with (
        patch("app.services.retrieval.embed_text", return_value=_FAKE_EMBEDDING),
        patch("app.services.retrieval.search_chunks", return_value=_CHROMA_RESULT),
    ):
        from app.services.retrieval import retrieve

        results = retrieve("password rules", k=5)

    assert len(results) == 2
    r = results[0]
    assert r.chunk_id == "chunk-uuid-1"
    assert r.document_id == "doc-uuid-1"
    assert r.filename == "policy.txt"
    assert r.chunk_index == 2
    assert r.content == "Employees must follow password security rules."
    assert r.token_count == 87


def test_retrieve_similarity_score_formula():
    """similarity_score = round(1 / (1 + distance), 4)"""
    with (
        patch("app.services.retrieval.embed_text", return_value=_FAKE_EMBEDDING),
        patch("app.services.retrieval.search_chunks", return_value=_CHROMA_RESULT),
    ):
        from app.services.retrieval import retrieve

        results = retrieve("q", k=5)

    assert results[0].similarity_score == round(1 / (1 + 0.2), 4)
    assert results[1].similarity_score == round(1 / (1 + 0.5), 4)


def test_retrieve_similarity_score_perfect_match():
    """distance=0 → similarity_score=1.0"""
    perfect = [{**_CHROMA_RESULT[0], "distance": 0.0}]
    with (
        patch("app.services.retrieval.embed_text", return_value=_FAKE_EMBEDDING),
        patch("app.services.retrieval.search_chunks", return_value=perfect),
    ):
        from app.services.retrieval import retrieve

        results = retrieve("q", k=1)

    assert results[0].similarity_score == 1.0


def test_retrieve_similarity_score_bounded():
    """Scores are always in [0, 1]."""
    large_distance = [{**_CHROMA_RESULT[0], "distance": 1000.0}]
    with (
        patch("app.services.retrieval.embed_text", return_value=_FAKE_EMBEDDING),
        patch("app.services.retrieval.search_chunks", return_value=large_distance),
    ):
        from app.services.retrieval import retrieve

        results = retrieve("q", k=1)

    score = results[0].similarity_score
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# GET /search — endpoint tests
# ---------------------------------------------------------------------------


@patch("app.api.routes.search.count_query_tokens", return_value=10)
@patch("app.api.routes.search.retrieve")
def test_search_normal_query_under_limit(mock_retrieve, mock_count):
    from app.schemas.retrieval import SearchResultResponse

    mock_retrieve.return_value = [
        SearchResultResponse(
            chunk_id="c1",
            document_id="d1",
            filename="f.txt",
            chunk_index=0,
            content="text",
            token_count=10,
            similarity_score=0.9,
        )
    ]
    response = client.get("/search?q=what+are+the+password+rules")
    assert response.status_code == 200
    mock_retrieve.assert_called_once()


@patch("app.api.routes.search.count_query_tokens", return_value=513)
@patch("app.api.routes.search.retrieve", return_value=[])
def test_search_long_query_returns_422(mock_retrieve, mock_count):
    long_query = "word " * 600
    response = client.get(f"/search?q={long_query}")
    assert response.status_code == 422
    assert "too long" in response.json()["detail"].lower()
    assert "512" in response.json()["detail"]


@patch("app.api.routes.search.count_query_tokens", return_value=513)
@patch("app.api.routes.search.retrieve", return_value=[])
def test_search_embedding_not_called_for_long_query(mock_retrieve, mock_count):
    long_query = "word " * 600
    client.get(f"/search?q={long_query}")
    mock_retrieve.assert_not_called()


@patch("app.api.routes.search.retrieve", return_value=[])
def test_search_empty_query(mock_retrieve):
    response = client.get("/search?q=")
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
    mock_retrieve.assert_not_called()


@patch("app.api.routes.search.retrieve", return_value=[])
def test_search_whitespace_query(mock_retrieve):
    response = client.get("/search?q=   ")
    assert response.status_code == 400
    mock_retrieve.assert_not_called()


@patch("app.api.routes.search.retrieve", return_value=[])
def test_search_no_results_returns_404(mock_retrieve):
    response = client.get("/search?q=unrelated obscure topic")
    assert response.status_code == 404
    assert "no matching" in response.json()["detail"].lower()


@patch(
    "app.api.routes.search.retrieve",
    side_effect=RuntimeError("ChromaDB operation failed: connection refused"),
)
def test_search_chroma_unavailable(mock_retrieve):
    response = client.get("/search?q=password rules")
    assert response.status_code == 503
    assert "ChromaDB" in response.json()["detail"]


@patch("app.api.routes.search.retrieve")
def test_search_success(mock_retrieve):
    from app.schemas.retrieval import SearchResultResponse

    mock_retrieve.return_value = [
        SearchResultResponse(
            chunk_id="chunk-uuid-1",
            document_id="doc-uuid-1",
            filename="policy.txt",
            chunk_index=2,
            content="Employees must follow password security rules.",
            token_count=87,
            similarity_score=0.8333,
        )
    ]

    response = client.get("/search?q=password rules&k=3")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "password rules"
    assert data["result_count"] == 1
    assert len(data["results"]) == 1

    r = data["results"][0]
    assert r["chunk_id"] == "chunk-uuid-1"
    assert r["document_id"] == "doc-uuid-1"
    assert r["filename"] == "policy.txt"
    assert r["chunk_index"] == 2
    assert r["content"] == "Employees must follow password security rules."
    assert r["token_count"] == 87
    assert r["similarity_score"] == 0.8333

    mock_retrieve.assert_called_once_with("password rules", 3)


@patch("app.api.routes.search.retrieve")
def test_search_default_k_is_5(mock_retrieve):
    from app.schemas.retrieval import SearchResultResponse

    mock_retrieve.return_value = [
        SearchResultResponse(
            chunk_id="c1",
            document_id="d1",
            filename="f.txt",
            chunk_index=0,
            content="text",
            token_count=10,
            similarity_score=0.9,
        )
    ]
    client.get("/search?q=hello")
    mock_retrieve.assert_called_once_with("hello", 5)


@patch("app.api.routes.search.retrieve")
def test_search_result_count_matches_results_length(mock_retrieve):
    from app.schemas.retrieval import SearchResultResponse

    mock_retrieve.return_value = [
        SearchResultResponse(
            chunk_id=f"c{i}",
            document_id="d1",
            filename="f.txt",
            chunk_index=i,
            content=f"chunk {i}",
            token_count=10,
            similarity_score=0.9 - i * 0.1,
        )
        for i in range(3)
    ]

    response = client.get("/search?q=query&k=3")
    data = response.json()
    assert data["result_count"] == len(data["results"]) == 3
