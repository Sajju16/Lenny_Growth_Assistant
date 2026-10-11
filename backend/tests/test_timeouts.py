import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import httpx

from main import app
from database.models import Base, Conversation, Message, Artifact
from database.connection import get_db
import database.crud as crud
from database.schemas import ConversationCreate, MessageCreate, ArtifactCreate
from llm.ollama_provider import OllamaProvider
from llm.factory import get_llm_provider
from skills.essay_skill import generate_ship30_essay
from rag.retriever import RetrievalResult, Citation


@pytest.fixture
def mock_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_ollama_timeout_configuration(monkeypatch):
    """
    Verify OllamaProvider initializes with configurable explicit timeout settings.
    Default chat timeout is 180s, overridable by OLLAMA_CHAT_TIMEOUT or explicit argument.
    """
    monkeypatch.setenv("OLLAMA_CHAT_TIMEOUT", "240.0")
    provider_env = OllamaProvider()
    assert provider_env._timeout == 240.0

    provider_custom = OllamaProvider(timeout=420.0)
    assert provider_custom._timeout == 420.0


def test_factory_passes_timeout():
    """
    Verify get_llm_provider passes explicit timeout to OllamaProvider.
    """
    provider = get_llm_provider("ollama", timeout=420.0)
    assert isinstance(provider, OllamaProvider)
    assert provider._timeout == 420.0


@pytest.mark.anyio
async def test_ollama_generate_response_timeout_raises_504():
    """
    Verify that an httpx.TimeoutException raises HTTP 504 Gateway Timeout
    with clear hardware context and actionable remediation advice.
    """
    provider = OllamaProvider(timeout=180.0)

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(HTTPException) as exc_info:
            await provider.generate_response(
                prompt="Explain market positioning",
                history=[],
                context_text="Some context",
                has_sufficient_context=True,
            )

        assert exc_info.value.status_code == 504
        assert "180s" in exc_info.value.detail
        assert "CPU" in exc_info.value.detail or "timeout" in exc_info.value.detail.lower()


@pytest.mark.anyio
async def test_essay_skill_uses_dedicated_timeout(mock_db):
    """
    Verify generate_ship30_essay passes dedicated 420s essay timeout to provider.generate_response.
    """
    mock_provider = MagicMock()
    mock_provider.model_name = "qwen2.5:3b"
    mock_provider.provider_name = "ollama"

    mock_resp = MagicMock()
    mock_resp.content = "# Scaled Product Growth\n\n" + ("A structured executive framework for scaling loops. " * 180)
    mock_resp.model = "qwen2.5:3b"
    mock_resp.provider = "ollama"
    mock_resp.eval_count = 1200
    mock_resp.total_duration = 200000000000
    mock_provider.generate_response = AsyncMock(return_value=mock_resp)

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="Elena Verna explains loops.",
        citations=[Citation(
            guest="Elena Verna",
            episode_title="PLG Loops",
            youtube_url="https://youtube.com/watch?v=elena",
            timestamp="05:10",
            excerpt="Elena Verna explains PLG compounding loops.",
            relevance_score=0.92,
        )],
        raw_chunks=[{"text": "Elena Verna explains loops."}],
    )

    conv = crud.create_conversation(mock_db, ConversationCreate(id="conv-essay-test", title="Essay Test"))

    result = await generate_ship30_essay(
        topic="PLG Growth Loops",
        provider=mock_provider,
        retriever=mock_retriever,
        conversation_id=conv.id,
        db=mock_db,
        timeout=420.0,
    )

    assert result.has_sufficient_context is True
    # Verify generate_response was called with timeout=420.0
    mock_provider.generate_response.assert_called_once()
    _, kwargs = mock_provider.generate_response.call_args
    assert kwargs.get("timeout") == 420.0


@pytest.mark.anyio
async def test_artifact_deduplication_on_retry(mock_db):
    """
    Verify that generating an essay for the same conversation and topic multiple times
    updates the existing artifact instead of inserting duplicate artifacts.
    """
    mock_provider = MagicMock()
    mock_provider.model_name = "qwen2.5:3b"
    mock_provider.provider_name = "ollama"

    mock_resp = MagicMock()
    mock_resp.content = "# Superhuman PMF Engine\n\nInitial version."
    mock_resp.model = "qwen2.5:3b"
    mock_resp.provider = "ollama"
    mock_resp.eval_count = 500
    mock_resp.total_duration = 100000000000
    mock_provider.generate_response = AsyncMock(return_value=mock_resp)

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="Rahul Vohra details the 40% benchmark.",
        citations=[Citation(
            guest="Rahul Vohra",
            episode_title="Superhuman PMF Engine",
            youtube_url="https://youtube.com/watch?v=rahul",
            timestamp="02:00",
            excerpt="Rahul Vohra details the 40% benchmark.",
            relevance_score=0.95,
        )],
        raw_chunks=[{"text": "Rahul Vohra details the 40% benchmark."}],
    )

    conv = crud.create_conversation(mock_db, ConversationCreate(id="conv-dedup-test", title="Dedup Test"))

    # First run
    res1 = await generate_ship30_essay(
        topic="Superhuman PMF Engine",
        provider=mock_provider,
        retriever=mock_retriever,
        conversation_id=conv.id,
        db=mock_db,
    )

    # Second run (simulating a retry)
    mock_resp.content = "# Superhuman PMF Engine\n\nUpdated version after retry."
    res2 = await generate_ship30_essay(
        topic="Superhuman PMF Engine",
        provider=mock_provider,
        retriever=mock_retriever,
        conversation_id=conv.id,
        db=mock_db,
    )

    # Verify both runs refer to the same artifact ID
    assert res1.artifact_id == res2.artifact_id

    # Verify database has exactly 1 artifact for this conversation
    artifacts = crud.list_conversation_artifacts(mock_db, conv.id)
    assert len(artifacts) == 1
    assert "Updated version" in artifacts[0].content


def test_chat_message_deduplication_on_retry(mock_db):
    """
    Verify that in /api/chat, sending the identical user message consecutively
    does not create duplicate user messages in the session.
    """
    conv = crud.create_conversation(mock_db, ConversationCreate(id="conv-retry-chat", title="Retry Chat Test"))

    def override_get_db():
        try:
            yield mock_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        # First request times out
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
            resp1 = client.post("/api/chat", json={
                "message": "How to find product-market fit for an early-stage startup",
                "conversation_id": conv.id,
                "use_rag": False,
            })
            assert resp1.status_code == 504

        # Verify 1 user message exists
        msgs_after_first = crud.get_conversation_messages(mock_db, conv.id)
        assert len(msgs_after_first) == 1
        assert msgs_after_first[0].role == "user"

        # User retries the identical prompt
        mock_success = {
            "model": "qwen2.5:3b",
            "message": {"content": "Product-market fit can be measured using the Sean Ellis benchmark."},
            "eval_count": 50,
            "total_duration": 15000000000,
        }
        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 200
        mock_http_resp.json.return_value = mock_success

        with patch("httpx.AsyncClient.post", return_value=mock_http_resp):
            resp2 = client.post("/api/chat", json={
                "message": "How to find product-market fit for an early-stage startup",
                "conversation_id": conv.id,
                "use_rag": False,
            })
            assert resp2.status_code == 200

        # Verify that total user messages is still 1, followed by 1 assistant message (total 2)
        msgs_after_retry = crud.get_conversation_messages(mock_db, conv.id)
        assert len(msgs_after_retry) == 2
        assert msgs_after_retry[0].role == "user"
        assert msgs_after_retry[1].role == "assistant"
    finally:
        app.dependency_overrides.clear()
