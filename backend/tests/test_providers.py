import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from llm.base import BaseLLMProvider, ProviderResponse
from llm.ollama_provider import OllamaProvider
from llm.anthropic_provider import AnthropicProvider, is_valid_anthropic_key
from llm.factory import get_llm_provider
from rag.retriever import Citation


client = TestClient(app)


def test_provider_factory_resolution():
    ollama_p = get_llm_provider("ollama")
    assert isinstance(ollama_p, OllamaProvider)
    assert ollama_p.provider_name == "ollama"
    assert not ollama_p.is_cloud

    anthropic_p = get_llm_provider("anthropic")
    assert isinstance(anthropic_p, AnthropicProvider)
    assert anthropic_p.provider_name == "anthropic"
    assert anthropic_p.is_cloud

    with pytest.raises(HTTPException) as exc_info:
        get_llm_provider("openai_unsupported")
    assert exc_info.value.status_code == 400
    assert "Unsupported LLM provider" in exc_info.value.detail


def test_is_valid_anthropic_key_validation():
    assert not is_valid_anthropic_key(None)
    assert not is_valid_anthropic_key("")
    assert not is_valid_anthropic_key("   ")
    assert not is_valid_anthropic_key("your_anthropic_api_key_here")
    assert not is_valid_anthropic_key("placeholder")
    assert is_valid_anthropic_key("sk-ant-live-real-test-key-12345")


def test_anthropic_missing_key_raises_400():
    provider = AnthropicProvider(api_key=None)
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
        with pytest.raises(HTTPException) as exc_info:
            provider._ensure_api_key()
        assert exc_info.value.status_code == 400
        assert "Anthropic API key is not configured" in exc_info.value.detail


def test_anthropic_placeholder_key_raises_400():
    provider = AnthropicProvider(api_key="your_anthropic_api_key_here")
    with pytest.raises(HTTPException) as exc_info:
        provider._ensure_api_key()
    assert exc_info.value.status_code == 400
    assert "Anthropic API key is not configured" in exc_info.value.detail


@pytest.mark.anyio
async def test_anthropic_health_check_reporting():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
        provider = AnthropicProvider(api_key="")
        health = await provider.check_health()
        assert health["provider"] == "anthropic"
        assert health["is_cloud"] is True
        assert health["connected"] is False
        assert health["api_key_configured"] is False

    provider_live = AnthropicProvider(api_key="sk-ant-valid-key")
    health_live = await provider_live.check_health()
    assert health_live["connected"] is True
    assert health_live["api_key_configured"] is True


@pytest.mark.anyio
async def test_anthropic_generate_response_mocked():
    provider = AnthropicProvider(api_key="sk-ant-mock-key-12345", model_name="claude-3-5-sonnet-20241022")

    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "April Dunford recommends defining your unique competitive alternatives first."

    mock_usage = MagicMock()
    mock_usage.input_tokens = 120
    mock_usage.output_tokens = 45

    mock_response = MagicMock()
    mock_response.content = [mock_text_block]
    mock_response.model = "claude-3-5-sonnet-20241022"
    mock_response.usage = mock_usage
    mock_response.stop_reason = "end_turn"

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    citation = Citation(
        guest="April Dunford",
        episode_title="Positioning",
        excerpt="Positioning is context setting for your product.",
        relevance_score=0.88,
    )

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        result = await provider.generate_response(
            prompt="How should I position my product?",
            history=[],
            context_text="April Dunford says positioning is context.",
            citations=[citation],
            has_sufficient_context=True,
        )

        assert isinstance(result, ProviderResponse)
        assert result.content == "April Dunford recommends defining your unique competitive alternatives first."
        assert result.provider == "anthropic"
        assert result.model == "claude-3-5-sonnet-20241022"
        assert len(result.citations) == 1
        assert result.eval_count == 45


def test_api_chat_anthropic_missing_key_no_silent_fallback():
    """
    Verify that selecting Anthropic when ANTHROPIC_API_KEY is missing returns
    a clear HTTP 400 error and does NOT silently fall back to Ollama or a mock.
    """
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
        response = client.post(
            "/api/chat",
            json={
                "message": "What is the best pricing strategy?",
                "provider": "anthropic",
                "use_rag": False,
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "Anthropic API key is not configured" in data["detail"]


def test_api_chat_with_mocked_anthropic_success():
    """
    Verify /api/chat completes end-to-end with provider=anthropic when mocked.
    """
    mock_response = ProviderResponse(
        content="Elena Verna emphasizes product-led sales loops for rapid PLG growth.",
        model="claude-3-5-sonnet-20241022",
        provider="anthropic",
        citations=[
            Citation(
                guest="Elena Verna",
                episode_title="PLG Strategies",
                excerpt="B2B growth requires product-led motion coupled with sales.",
                relevance_score=0.91,
            )
        ],
        has_sufficient_context=True,
    )

    with patch("main.get_llm_provider") as mock_get_provider:
        mock_provider_instance = MagicMock()
        mock_provider_instance.model_name = "claude-3-5-sonnet-20241022"
        mock_provider_instance.generate_response = AsyncMock(return_value=mock_response)
        mock_get_provider.return_value = mock_provider_instance

        with patch("main.retriever.retrieve") as mock_retrieve:
            mock_retrieval_res = MagicMock()
            mock_retrieval_res.citations = mock_response.citations
            mock_retrieval_res.has_sufficient_context = True
            mock_retrieval_res.context_text = "Elena Verna excerpt."
            mock_retrieve.return_value = mock_retrieval_res

            response = client.post(
                "/api/chat",
                json={
                    "message": "Explain B2B PLG loops according to Elena Verna",
                    "provider": "anthropic",
                    "use_rag": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["provider"] == "anthropic"
            assert data["model"] == "claude-3-5-sonnet-20241022"
            assert "Elena Verna" in data["response"]
            assert len(data["citations"]) == 1
            assert data["citations"][0]["guest"] == "Elena Verna"
