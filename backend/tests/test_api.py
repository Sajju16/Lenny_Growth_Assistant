from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fastapi.testclient import TestClient
from main import app
from rag.retriever import RetrievalResult, Citation

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "backend" in data
    assert "ollama" in data
    assert "knowledge_base" in data


def test_knowledge_status_endpoint():
    response = client.get("/api/knowledge/status")
    assert response.status_code == 200
    data = response.json()
    assert "collection_name" in data
    assert "embedding_model" in data
    assert "total_chunks" in data


@patch("main.retriever.retrieve")
@patch("httpx.AsyncClient.post")
def test_chat_with_grounded_citations(mock_post, mock_retrieve):
    # Mock retrieval with strong evidence
    mock_retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="--- EVIDENCE EXCERPT 1 ---\nEpisode: Founder-Led Sales\nGuest: Pete Kazanjy\n\nFounders should personally do sales first.",
        citations=[
            Citation(
                guest="Pete Kazanjy",
                episode_title="Founder-Led Sales",
                youtube_url="https://youtube.com/watch?v=sample",
                publish_date="2022-12-15",
                excerpt="Founders should personally do sales first.",
                relevance_score=0.88,
            )
        ],
        raw_chunks=[{"text": "Founders should personally do sales first."}],
    )

    # Mock Ollama chat response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5:3b",
        "message": {"role": "assistant", "content": "Pete Kazanjy recommends founders personally handle sales initially."},
        "done": True,
        "eval_count": 42,
        "total_duration": 1200000,
    }
    mock_post.return_value = mock_resp

    payload = {
        "message": "Why should founders do sales themselves?",
        "model": "qwen2.5:3b",
        "history": [],
        "use_rag": True,
    }

    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_sufficient_context"] is True
    assert len(data["citations"]) == 1
    assert data["citations"][0]["guest"] == "Pete Kazanjy"
    assert "Pete Kazanjy recommends" in data["response"]


@patch("main.retriever.retrieve")
def test_chat_insufficient_evidence(mock_retrieve):
    # Mock retrieval with insufficient evidence
    mock_retrieve.return_value = RetrievalResult(
        has_sufficient_context=False,
        context_text="",
        citations=[],
        raw_chunks=[],
    )

    payload = {
        "message": "What is the secret recipe for baking croissants?",
        "model": "qwen2.5:3b",
        "history": [],
        "use_rag": True,
    }

    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_sufficient_context"] is False
    assert len(data["citations"]) == 0
    assert "insufficient evidence" in data["response"].lower()


def test_chat_real_sourdough_croissants_unsupported():
    """
    Integration test with live retriever: 'How do I bake sourdough croissants?'
    must fail closed at the evidence gate, returning an insufficient-evidence refusal
    with an empty citation list and NO generated recipe.
    """
    payload = {
        "message": "How do I bake sourdough croissants?",
        "model": "qwen2.5:3b",
        "history": [],
        "use_rag": True,
    }

    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_sufficient_context"] is False
    assert len(data["citations"]) == 0
    assert "insufficient evidence" in data["response"].lower()
    # Must NOT contain a fabricated croissant recipe
    assert "butter" not in data["response"].lower()
    assert "flour" not in data["response"].lower()
    assert "knead" not in data["response"].lower()


@patch("main.retriever.retrieve")
@patch("httpx.AsyncClient.post")
def test_chat_filters_empty_and_whitespace_history_messages(mock_post, mock_retrieve):
    """
    Regression test: ChatRequest must filter out empty or whitespace-only history items
    without raising Pydantic 422 ('String should have at least 1 character').
    """
    mock_retrieve.return_value = RetrievalResult(
        has_sufficient_context=False,
        context_text="",
        citations=[],
        raw_chunks=[],
    )

    payload = {
        "message": "What is product-market fit?",
        "model": "qwen2.5:3b",
        "history": [
            {"role": "user", "content": "Initial question"},
            {"role": "assistant", "content": ""},       # empty string
            {"role": "assistant", "content": "   "},    # whitespace-only
            {"role": "assistant", "content": "Valid answer"},
        ],
        "use_rag": True,
    }

    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200, f"Expected 200 but got {response.status_code}: {response.text}"


@patch("main.retriever.retrieve")
@patch("httpx.AsyncClient.post")
def test_chat_deduplicates_trailing_user_prompt_in_history(mock_post, mock_retrieve):
    """
    Regression test: Trailing user message identical to current prompt must be deduplicated
    from provider history to prevent prompt repetition.
    """
    mock_retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="Evidence",
        citations=[Citation(guest="Lenny", episode_title="Growth", excerpt="Context", relevance_score=0.9)],
        raw_chunks=[{"text": "Context"}],
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen2.5:3b",
        "message": {"role": "assistant", "content": "Grounded answer."},
        "done": True,
    }
    mock_post.return_value = mock_resp

    prompt_text = "Explain product-market fit"
    payload = {
        "message": prompt_text,
        "model": "qwen2.5:3b",
        "history": [
            {"role": "user", "content": "Prior question"},
            {"role": "assistant", "content": "Prior answer"},
            {"role": "user", "content": prompt_text},  # duplicate of current message
        ],
        "use_rag": True,
    }

    with patch("main.get_llm_provider") as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.model_name = "qwen2.5:3b"
        mock_provider.provider_name = "ollama"
        from llm.base import ProviderResponse
        mock_provider.generate_response = AsyncMock(return_value=ProviderResponse(
            content="Grounded answer.",
            model="qwen2.5:3b",
            provider="ollama",
            citations=[],
        ))
        mock_get_provider.return_value = mock_provider

        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        # Verify provider generate_response was called and history does not end with prompt_text
        call_kwargs = mock_provider.generate_response.call_args.kwargs
        passed_history = call_kwargs["history"]
        assert len(passed_history) == 2
        assert passed_history[-1]["content"] == "Prior answer"
