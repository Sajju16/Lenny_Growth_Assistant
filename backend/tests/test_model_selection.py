import json
import uuid
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from main import app
from rag.retriever import Citation, RetrievalResult
from llm.base import ProviderResponse
from llm.ollama_provider import OllamaProvider


client = TestClient(app)


def test_health_model_reporting():
    """Verify health endpoint reports active, default, and policy metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "active_model" in data
    assert "default_model" in data
    assert "model_selection_policy" in data
    assert data["model_selection_policy"] == "per_request_override_supported"
    assert data["default_model"] == data["active_model"]
    assert "available_local_models" in data


def test_chat_explicit_model_selection_1_5b():
    """Verify that selecting qwen2.5:1.5b propagates to generation, response, and DB persistence."""
    conv_id = f"test-model-15b-{uuid.uuid4().hex[:8]}"

    # 1. Create conversation session
    create_res = client.post(
        "/api/conversations",
        json={"id": conv_id, "title": "Test 1.5B Model Selection"},
    )
    assert create_res.status_code == 201

    mock_resp = ProviderResponse(
        content="Dan Hockenmaier explains that early retention focus is essential.",
        model="qwen2.5:1.5b",
        provider="ollama",
        citations=[
            Citation(
                guest="Dan Hockenmaier",
                episode_title="Retention & Engagement",
                excerpt="Focus on the early user experience first.",
                relevance_score=0.88,
            )
        ],
        has_sufficient_context=True,
    )

    with patch("main.get_llm_provider") as mock_get_provider:
        mock_provider = MagicMock(spec=OllamaProvider)
        mock_provider.model_name = "qwen2.5:3b"
        mock_provider._model_name = "qwen2.5:3b"
        mock_provider.generate_response = AsyncMock(return_value=mock_resp)
        mock_get_provider.return_value = mock_provider

        with patch("main.retriever.retrieve") as mock_retrieve:
            mock_retrieve.return_value = RetrievalResult(
                has_sufficient_context=True,
                context_text="Focus on the early user experience first.",
                citations=mock_resp.citations,
                raw_chunks=[{"text": "Focus on the early user experience first."}],
            )

            response = client.post(
                "/api/chat",
                json={
                    "message": "How do we improve early retention?",
                    "model": "qwen2.5:1.5b",
                    "conversation_id": conv_id,
                    "use_rag": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["model"] == "qwen2.5:1.5b"
            assert mock_provider._model_name == "qwen2.5:1.5b"

    # Verify persisted messages in PostgreSQL
    detail = client.get(f"/api/conversations/{conv_id}").json()
    messages = detail["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["model"] == "qwen2.5:1.5b"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["model"] == "qwen2.5:1.5b"

    # Cleanup
    client.delete(f"/api/conversations/{conv_id}")


def test_chat_explicit_model_selection_3b():
    """Verify that selecting qwen2.5:3b propagates cleanly to generation and DB persistence."""
    conv_id = f"test-model-3b-{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/conversations",
        json={"id": conv_id, "title": "Test 3B Model Selection"},
    )

    mock_resp = ProviderResponse(
        content="Elena Verna emphasizes PLG expansion loops.",
        model="qwen2.5:3b",
        provider="ollama",
        citations=[
            Citation(
                guest="Elena Verna",
                episode_title="B2B Growth Loops",
                excerpt="Product-led growth loops scale efficiently.",
                relevance_score=0.91,
            )
        ],
        has_sufficient_context=True,
    )

    with patch("main.get_llm_provider") as mock_get_provider:
        mock_provider = MagicMock(spec=OllamaProvider)
        mock_provider.model_name = "qwen2.5:3b"
        mock_provider._model_name = "qwen2.5:3b"
        mock_provider.generate_response = AsyncMock(return_value=mock_resp)
        mock_get_provider.return_value = mock_provider

        with patch("main.retriever.retrieve") as mock_retrieve:
            mock_retrieve.return_value = RetrievalResult(
                has_sufficient_context=True,
                context_text="Product-led growth loops scale efficiently.",
                citations=mock_resp.citations,
                raw_chunks=[{"text": "Product-led growth loops scale efficiently."}],
            )

            response = client.post(
                "/api/chat",
                json={
                    "message": "What are PLG expansion loops?",
                    "model": "qwen2.5:3b",
                    "conversation_id": conv_id,
                    "use_rag": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["model"] == "qwen2.5:3b"
            assert mock_provider._model_name == "qwen2.5:3b"

    detail = client.get(f"/api/conversations/{conv_id}").json()
    messages = detail["messages"]
    assert len(messages) == 2
    assert messages[0]["model"] == "qwen2.5:3b"
    assert messages[1]["model"] == "qwen2.5:3b"

    client.delete(f"/api/conversations/{conv_id}")


def test_chat_stream_explicit_model_selection_1_5b():
    """Verify that SSE streaming with model=qwen2.5:1.5b preserves the model in stream and DB."""
    conv_id = f"test-stream-15b-{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/conversations",
        json={"id": conv_id, "title": "Test 1.5B Streaming Model Selection"},
    )

    async def mock_stream_chunks(*args, **kwargs):
        yield {"delta": "Early "}
        yield {"delta": "retention."}
        yield {
            "done": True,
            "response": "Early retention.",
            "model": "qwen2.5:1.5b",
            "provider": "ollama",
            "eval_count": 2,
            "total_duration": 100000000,
            "metadata": {},
        }

    with patch("main.get_llm_provider") as mock_get_provider:
        mock_provider = MagicMock(spec=OllamaProvider)
        mock_provider.model_name = "qwen2.5:3b"
        mock_provider._model_name = "qwen2.5:3b"
        mock_provider.stream_response = mock_stream_chunks
        mock_get_provider.return_value = mock_provider

        with patch("main.retriever.retrieve") as mock_retrieve:
            mock_retrieve.return_value = RetrievalResult(
                has_sufficient_context=True,
                context_text="Evidence for retention.",
                citations=[
                    Citation(
                        guest="Dan Hockenmaier",
                        episode_title="Retention",
                        excerpt="Early retention.",
                        relevance_score=0.85,
                    )
                ],
                raw_chunks=[],
            )

            response = client.post(
                "/api/chat/stream",
                json={
                    "message": "How do we improve early retention?",
                    "model": "qwen2.5:1.5b",
                    "conversation_id": conv_id,
                    "use_rag": True,
                },
            )

            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            # Parse SSE events
            lines = response.text.split("\n")
            meta_data = None
            done_data = None
            for idx, line in enumerate(lines):
                if line.startswith("event: meta"):
                    for following in lines[idx+1:idx+3]:
                        if following.startswith("data:"):
                            meta_data = json.loads(following.replace("data:", "").strip())
                elif line.startswith("event: done"):
                    for following in lines[idx+1:idx+3]:
                        if following.startswith("data:"):
                            done_data = json.loads(following.replace("data:", "").strip())

            assert meta_data is not None
            assert meta_data["model"] == "qwen2.5:1.5b"

            assert done_data is not None
            assert done_data["model"] == "qwen2.5:1.5b"

    # Verify persisted message in DB has the exact model
    detail = client.get(f"/api/conversations/{conv_id}").json()
    messages = detail["messages"]
    assert len(messages) == 2
    assert messages[0]["model"] == "qwen2.5:1.5b"
    assert messages[1]["model"] == "qwen2.5:1.5b"

    client.delete(f"/api/conversations/{conv_id}")


def test_chat_stream_unsupported_question_preserves_selected_model():
    """Verify that an unsupported question during streaming preserves the selected model in refusal."""
    conv_id = f"test-stream-unsupported-{uuid.uuid4().hex[:8]}"

    client.post(
        "/api/conversations",
        json={"id": conv_id, "title": "Test Stream Unsupported Model"},
    )

    with patch("main.retriever.retrieve") as mock_retrieve:
        mock_retrieve.return_value = RetrievalResult(
            has_sufficient_context=False,
            context_text="",
            citations=[],
            raw_chunks=[],
        )

        response = client.post(
            "/api/chat/stream",
            json={
                "message": "How do I bake sourdough croissants?",
                "model": "qwen2.5:1.5b",
                "conversation_id": conv_id,
                "use_rag": True,
            },
        )

        assert response.status_code == 200
        lines = response.text.split("\n")
        done_data = None
        for idx, line in enumerate(lines):
            if line.startswith("event: done"):
                for following in lines[idx+1:idx+3]:
                    if following.startswith("data:"):
                        done_data = json.loads(following.replace("data:", "").strip())

        assert done_data is not None
        assert done_data["model"] == "qwen2.5:1.5b"
        assert done_data["has_sufficient_context"] is False
        assert done_data["citations"] == []

    detail = client.get(f"/api/conversations/{conv_id}").json()
    messages = detail["messages"]
    assert len(messages) == 2
    assert messages[0]["model"] == "qwen2.5:1.5b"
    assert messages[1]["model"] == "qwen2.5:1.5b"
    assert messages[1]["has_sufficient_context"] is False

    client.delete(f"/api/conversations/{conv_id}")
