import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.models import Conversation, LLMRun, Message
from app.db.session import get_db_session
from app.main import app
from app.schemas.answering import AnswerSourceResponse
from app.schemas.retrieval import SearchResultResponse
from app.services.answering import AnswerResult, RetrievalEmptyError
from app.services.llm import OllamaUnavailableError
from app.services.prompting import build_prompt

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_CONV_ID = uuid.uuid4()
_CREATED_AT = datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc)

_FAKE_CHUNK = SearchResultResponse(
    chunk_id="chunk-1",
    document_id="doc-1",
    filename="handbook.txt",
    chunk_index=0,
    content="Employees may work remotely up to three days per week.",
    token_count=12,
    similarity_score=0.9,
)

_FAKE_SOURCE = AnswerSourceResponse(
    chunk_id="chunk-1",
    document_id="doc-1",
    filename="handbook.txt",
    chunk_index=0,
    similarity_score=0.9,
    content_preview="Employees may work remotely up to three days per week.",
)

_FAKE_ANSWER_TEXT = "Employees may work remotely up to three days per week."

_FAKE_RESULT = AnswerResult(
    answer=_FAKE_ANSWER_TEXT,
    prompt="the full prompt",
    sources=[_FAKE_SOURCE],
    latency_ms=200,
)


def _make_mock_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.get = AsyncMock()
    db.execute = AsyncMock()
    return db


def _db_override(mock_db: AsyncMock):
    async def _override():
        yield mock_db

    return _override


def _make_scalars_result(items: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _fake_conversation(conv_id: uuid.UUID = _CONV_ID) -> Conversation:
    return Conversation(id=conv_id, created_at=_CREATED_AT, updated_at=_CREATED_AT)


def _fake_message(role: str, content: str) -> Message:
    return Message(
        id=uuid.uuid4(),
        conversation_id=_CONV_ID,
        role=role,
        content=content,
        created_at=_CREATED_AT,
    )


# ---------------------------------------------------------------------------
# POST /conversations — create conversation
# ---------------------------------------------------------------------------


def test_create_conversation_returns_201():
    mock_db = _make_mock_db()
    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/conversations")
        assert response.status_code == 201
    finally:
        app.dependency_overrides.clear()


def test_create_conversation_response_has_id_and_timestamp():
    mock_db = _make_mock_db()
    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/conversations")
        data = response.json()
        assert "conversation_id" in data
        assert "created_at" in data
        # id should be a valid UUID string
        uuid.UUID(data["conversation_id"])
    finally:
        app.dependency_overrides.clear()


def test_create_conversation_persists_to_db():
    mock_db = _make_mock_db()
    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post("/conversations")
        assert mock_db.add.called
        added = mock_db.add.call_args[0][0]
        assert isinstance(added, Conversation)
        assert mock_db.commit.called
    finally:
        app.dependency_overrides.clear()


def test_create_conversation_returns_unique_ids():
    mock_db = _make_mock_db()
    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        r1 = client.post("/conversations").json()
        r2 = client.post("/conversations").json()
        assert r1["conversation_id"] != r2["conversation_id"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /conversations/{id} — retrieve conversation
# ---------------------------------------------------------------------------


def test_get_conversation_returns_200():
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.get(f"/conversations/{_CONV_ID}")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_get_conversation_response_shape():
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        data = client.get(f"/conversations/{_CONV_ID}").json()
        assert data["conversation_id"] == str(_CONV_ID)
        assert "created_at" in data
        assert data["messages"] == []
    finally:
        app.dependency_overrides.clear()


def test_get_conversation_returns_messages_in_order():
    msg1 = _fake_message("user", "First question")
    msg2 = _fake_message("assistant", "First answer")

    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([msg1, msg2])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        data = client.get(f"/conversations/{_CONV_ID}").json()
        messages = data["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "First question"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "First answer"
    finally:
        app.dependency_overrides.clear()


def test_get_conversation_message_has_expected_fields():
    msg = _fake_message("user", "Hello")

    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([msg])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        data = client.get(f"/conversations/{_CONV_ID}").json()
        m = data["messages"][0]
        assert "message_id" in m
        assert "role" in m
        assert "content" in m
        assert "created_at" in m
    finally:
        app.dependency_overrides.clear()


def test_get_conversation_not_found_returns_404():
    mock_db = _make_mock_db()
    mock_db.get.return_value = None

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.get(f"/conversations/{_CONV_ID}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_get_conversation_invalid_uuid_returns_422():
    response = client.get("/conversations/not-a-uuid")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /conversations/{id}/messages — send message
# ---------------------------------------------------------------------------


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_success(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "How many remote days?", "k": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == str(_CONV_ID)
        assert data["answer"] == _FAKE_ANSWER_TEXT
        assert "message_id" in data
        assert "sources" in data
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_sources_included(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        data = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "remote days?", "k": 3},
        ).json()
        assert len(data["sources"]) == 1
        src = data["sources"][0]
        assert src["chunk_id"] == "chunk-1"
        assert src["filename"] == "handbook.txt"
        assert src["similarity_score"] == 0.9
    finally:
        app.dependency_overrides.clear()


def test_send_message_conversation_not_found_returns_404():
    mock_db = _make_mock_db()
    mock_db.get.return_value = None

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "Hello?", "k": 5},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_send_message_empty_message_returns_400():
    mock_db = _make_mock_db()
    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "", "k": 5},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_send_message_whitespace_message_returns_400():
    mock_db = _make_mock_db()
    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "   ", "k": 5},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_send_message_k_zero_returns_422():
    mock_db = _make_mock_db()
    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "test?", "k": 0},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_send_message_k_too_large_returns_422():
    mock_db = _make_mock_db()
    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "test?", "k": 11},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=600)
def test_send_message_long_message_returns_422(mock_count):
    mock_db = _make_mock_db()
    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "word " * 600, "k": 5},
        )
        assert response.status_code == 422
        assert "too long" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_ollama_unavailable_returns_503(mock_gen, mock_count):
    mock_gen.side_effect = OllamaUnavailableError("Cannot connect to Ollama.")
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "remote days?", "k": 5},
        )
        assert response.status_code == 503
        assert "Ollama" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_chroma_unavailable_returns_503(mock_gen, mock_count):
    mock_gen.side_effect = RuntimeError("ChromaDB connection refused")
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "remote days?", "k": 5},
        )
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_no_chunks_returns_404(mock_gen, mock_count):
    mock_gen.side_effect = RetrievalEmptyError("No chunks found.")
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "obscure?", "k": 5},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_send_message_invalid_uuid_returns_422():
    response = client.post(
        "/conversations/not-a-uuid/messages",
        json={"message": "test?", "k": 5},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Prompt builder — history unit tests (pure functions, no mocks)
# ---------------------------------------------------------------------------


def test_prompt_with_no_history_omits_history_section():
    prompt = build_prompt("What is the policy?", [_FAKE_CHUNK])
    assert "Conversation History:" not in prompt


def test_prompt_with_empty_history_omits_history_section():
    prompt = build_prompt("What is the policy?", [_FAKE_CHUNK], history=[])
    assert "Conversation History:" not in prompt


def test_prompt_with_history_includes_history_section():
    history = [{"role": "user", "content": "How many remote days?"}]
    prompt = build_prompt("What about PTO?", [_FAKE_CHUNK], history=history)
    assert "Conversation History:" in prompt
    assert "How many remote days?" in prompt


def test_prompt_history_user_role_label():
    history = [{"role": "user", "content": "Hello"}]
    prompt = build_prompt("Follow up?", [_FAKE_CHUNK], history=history)
    assert "User:\nHello" in prompt


def test_prompt_history_assistant_role_label():
    history = [{"role": "assistant", "content": "Hi there"}]
    prompt = build_prompt("Follow up?", [_FAKE_CHUNK], history=history)
    assert "A:\nHi there" in prompt


def test_prompt_history_multiple_turns():
    history = [
        {"role": "user", "content": "How many remote days?"},
        {"role": "assistant", "content": "Three days per week."},
        {"role": "user", "content": "What about PTO?"},
        {"role": "assistant", "content": "Twenty days per year."},
    ]
    prompt = build_prompt("Any exceptions?", [_FAKE_CHUNK], history=history)
    assert "How many remote days?" in prompt
    assert "Three days per week." in prompt
    assert "What about PTO?" in prompt
    assert "Twenty days per year." in prompt


def test_prompt_history_appears_before_context():
    history = [{"role": "user", "content": "Prior question"}]
    prompt = build_prompt("New question?", [_FAKE_CHUNK], history=history)
    history_pos = prompt.index("Conversation History:")
    context_pos = prompt.index("Context:")
    assert history_pos < context_pos


def test_prompt_history_appears_before_question():
    history = [{"role": "user", "content": "Prior question"}]
    prompt = build_prompt("New question?", [_FAKE_CHUNK], history=history)
    history_pos = prompt.index("Conversation History:")
    question_pos = prompt.index("Question:")
    assert history_pos < question_pos


def test_prompt_without_history_still_includes_question_and_context():
    prompt = build_prompt("What is policy?", [_FAKE_CHUNK])
    assert "Question:" in prompt
    assert "Context:" in prompt
    assert "What is policy?" in prompt
    assert "handbook.txt" in prompt


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_stores_user_message(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "How many remote days?", "k": 5},
        )
        added = [c.args[0] for c in mock_db.add.call_args_list]
        user_messages = [a for a in added if isinstance(a, Message) and a.role == "user"]
        assert len(user_messages) == 1
        assert user_messages[0].content == "How many remote days?"
        assert user_messages[0].conversation_id == _CONV_ID
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_stores_assistant_message_on_success(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "remote days?", "k": 5},
        )
        added = [c.args[0] for c in mock_db.add.call_args_list]
        assistant_messages = [a for a in added if isinstance(a, Message) and a.role == "assistant"]
        assert len(assistant_messages) == 1
        assert assistant_messages[0].content == _FAKE_ANSWER_TEXT
        assert assistant_messages[0].conversation_id == _CONV_ID
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_no_assistant_message_on_failure(mock_gen, mock_count):
    mock_gen.side_effect = OllamaUnavailableError("down")
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "remote days?", "k": 5},
        )
        added = [c.args[0] for c in mock_db.add.call_args_list]
        assistant_messages = [a for a in added if isinstance(a, Message) and a.role == "assistant"]
        assert len(assistant_messages) == 0
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_commits_even_on_failure(mock_gen, mock_count):
    mock_gen.side_effect = OllamaUnavailableError("down")
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "remote days?", "k": 5},
        )
        assert mock_db.commit.called
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# LLM run logging tests
# ---------------------------------------------------------------------------


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_llm_run_linked_to_conversation(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "remote days?", "k": 5},
        )
        added = [c.args[0] for c in mock_db.add.call_args_list]
        llm_runs = [a for a in added if isinstance(a, LLMRun)]
        assert len(llm_runs) == 1
        assert llm_runs[0].conversation_id == _CONV_ID
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_llm_run_success_logged(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "remote days?", "k": 5},
        )
        added = [c.args[0] for c in mock_db.add.call_args_list]
        llm_run = next(a for a in added if isinstance(a, LLMRun))
        assert llm_run.status == "success"
        assert llm_run.provider == "ollama"
        assert llm_run.response == _FAKE_ANSWER_TEXT
        assert llm_run.error_message is None
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_llm_run_failure_logged(mock_gen, mock_count):
    mock_gen.side_effect = OllamaUnavailableError("Ollama is down.")
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "remote days?", "k": 5},
        )
        added = [c.args[0] for c in mock_db.add.call_args_list]
        llm_run = next(a for a in added if isinstance(a, LLMRun))
        assert llm_run.status == "failed"
        assert llm_run.error_message is not None
        assert llm_run.response is None
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_llm_run_metadata_includes_question_and_k(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "remote days?", "k": 3},
        )
        added = [c.args[0] for c in mock_db.add.call_args_list]
        llm_run = next(a for a in added if isinstance(a, LLMRun))
        assert llm_run.run_metadata["question"] == "remote days?"
        assert llm_run.run_metadata["k"] == 3
        assert "source_chunk_ids" in llm_run.run_metadata
        assert "source_document_ids" in llm_run.run_metadata
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_llm_run_logged_even_on_404(mock_gen, mock_count):
    mock_gen.side_effect = RetrievalEmptyError("No chunks.")
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "obscure?", "k": 5},
        )
        assert response.status_code == 404
        added = [c.args[0] for c in mock_db.add.call_args_list]
        llm_run = next(a for a in added if isinstance(a, LLMRun))
        assert llm_run.status == "failed"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# History loading tests
# ---------------------------------------------------------------------------


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_passes_history_to_generate_answer(mock_gen, mock_count):
    prior_user = _fake_message("user", "Prior question")
    prior_assistant = _fake_message("assistant", "Prior answer")

    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    # Route queries ORDER BY created_at DESC (newest first) then reverses.
    # Provide assistant (newer) before user (older) to simulate DB ordering.
    mock_db.execute.return_value = _make_scalars_result([prior_assistant, prior_user])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "Follow up?", "k": 5},
        )
        call_kwargs = mock_gen.call_args.kwargs
        assert "history" in call_kwargs
        history = call_kwargs["history"]
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Prior question"}
        assert history[1] == {"role": "assistant", "content": "Prior answer"}
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_passes_empty_history_on_first_message(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "First question?", "k": 5},
        )
        call_kwargs = mock_gen.call_args.kwargs
        assert call_kwargs["history"] == []
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.conversations.count_query_tokens", return_value=10)
@patch("app.api.routes.conversations.generate_answer", new_callable=AsyncMock)
def test_send_message_response_message_id_is_assistant_id(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()
    mock_db.get.return_value = _fake_conversation()
    mock_db.execute.return_value = _make_scalars_result([])

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        data = client.post(
            f"/conversations/{_CONV_ID}/messages",
            json={"message": "remote days?", "k": 5},
        ).json()
        # message_id in response must match the assistant message that was stored
        added = [c.args[0] for c in mock_db.add.call_args_list]
        assistant_msg = next(a for a in added if isinstance(a, Message) and a.role == "assistant")
        assert data["message_id"] == str(assistant_msg.id)
    finally:
        app.dependency_overrides.clear()
