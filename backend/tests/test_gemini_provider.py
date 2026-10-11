"""
Tests for the Google Gemini LLM provider.

Covers:
- API key validation (valid, missing, placeholder)
- Factory resolution for 'gemini' provider
- Health check reporting (configured vs. unconfigured)
- generate_response with mocked HTTP responses (success, auth error, rate limit, empty)
- stream_response with mocked SSE chunks
- Insufficient context refusal (non-streaming and streaming)
- Chat API integration with mocked Gemini provider
"""

import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from llm.base import ProviderResponse
from llm.gemini_provider import GeminiProvider, is_valid_gemini_key
from llm.factory import get_llm_provider
from rag.retriever import Citation


client = TestClient(app)


# ==============================================================================
# API Key Validation
# ==============================================================================

class TestGeminiKeyValidation:
    def test_none_key(self):
        assert not is_valid_gemini_key(None)

    def test_empty_key(self):
        assert not is_valid_gemini_key("")

    def test_whitespace_key(self):
        assert not is_valid_gemini_key("   ")

    def test_placeholder_key(self):
        assert not is_valid_gemini_key("your_gemini_api_key_here")

    def test_placeholder_none(self):
        assert not is_valid_gemini_key("none")

    def test_placeholder_generic(self):
        assert not is_valid_gemini_key("placeholder")

    def test_your_prefix_key(self):
        assert not is_valid_gemini_key("your_custom_key")

    def test_valid_key(self):
        assert is_valid_gemini_key("AIzaSyB-real-test-key-12345")


# ==============================================================================
# Factory Resolution
# ==============================================================================

class TestGeminiFactory:
    def test_factory_resolves_gemini(self):
        provider = get_llm_provider("gemini")
        assert isinstance(provider, GeminiProvider)
        assert provider.provider_name == "gemini"
        assert provider.is_cloud is True

    def test_factory_env_gemini(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}, clear=False):
            provider = get_llm_provider()
            assert isinstance(provider, GeminiProvider)


# ==============================================================================
# Provider Properties
# ==============================================================================

class TestGeminiProperties:
    def test_provider_name(self):
        p = GeminiProvider()
        assert p.provider_name == "gemini"

    def test_is_cloud(self):
        p = GeminiProvider()
        assert p.is_cloud is True

    def test_default_model(self):
        p = GeminiProvider()
        assert "gemini" in p.model_name.lower()

    def test_custom_model(self):
        p = GeminiProvider(model_name="gemini-2.0-flash")
        assert p.model_name == "gemini-2.0-flash"


# ==============================================================================
# API Key Enforcement
# ==============================================================================

class TestGeminiKeyEnforcement:
    def test_missing_key_raises_400(self):
        provider = GeminiProvider(api_key=None)
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            with pytest.raises(HTTPException) as exc_info:
                provider._ensure_api_key()
            assert exc_info.value.status_code == 400
            assert "Gemini API key is not configured" in exc_info.value.detail

    def test_placeholder_key_raises_400(self):
        provider = GeminiProvider(api_key="your_gemini_api_key_here")
        with pytest.raises(HTTPException) as exc_info:
            provider._ensure_api_key()
        assert exc_info.value.status_code == 400

    def test_valid_key_returns_stripped(self):
        provider = GeminiProvider(api_key="  AIzaSyB-test-key  ")
        key = provider._ensure_api_key()
        assert key == "AIzaSyB-test-key"


# ==============================================================================
# Health Check
# ==============================================================================

class TestGeminiHealth:
    @pytest.mark.anyio
    async def test_unconfigured_health(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            provider = GeminiProvider(api_key="")
            health = await provider.check_health()
            assert health["provider"] == "gemini"
            assert health["is_cloud"] is True
            assert health["connected"] is False
            assert health["api_key_configured"] is False
            assert health["error"] is not None

    @pytest.mark.anyio
    async def test_configured_health(self):
        provider = GeminiProvider(api_key="AIzaSyB-valid-key")
        health = await provider.check_health()
        assert health["connected"] is True
        assert health["api_key_configured"] is True
        assert health["error"] is None


# ==============================================================================
# generate_response (mocked HTTP)
# ==============================================================================

class TestGeminiGenerate:
    @pytest.mark.anyio
    async def test_successful_generation(self):
        provider = GeminiProvider(api_key="AIzaSyB-mock-key", model_name="gemini-2.5-flash")

        mock_response_data = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "April Dunford recommends focusing on competitive alternatives first."}],
                },
                "finishReason": "STOP",
            }],
            "usageMetadata": {
                "promptTokenCount": 150,
                "candidatesTokenCount": 42,
            },
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data
        mock_resp.text = json.dumps(mock_response_data)

        citation = Citation(
            guest="April Dunford",
            episode_title="Positioning",
            excerpt="Positioning is context setting for your product.",
            relevance_score=0.88,
        )

        with patch("llm.gemini_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await provider.generate_response(
                prompt="How should I position my product?",
                history=[],
                context_text="April Dunford says positioning is context.",
                citations=[citation],
                has_sufficient_context=True,
            )

            assert isinstance(result, ProviderResponse)
            assert "April Dunford" in result.content
            assert result.provider == "gemini"
            assert result.model == "gemini-2.5-flash"
            assert len(result.citations) == 1
            assert result.eval_count == 42
            assert result.metadata["input_tokens"] == 150

    @pytest.mark.anyio
    async def test_auth_error_401(self):
        provider = GeminiProvider(api_key="AIzaSyB-bad-key", model_name="gemini-2.5-flash")

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "API key not valid"

        with patch("llm.gemini_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await provider.generate_response(
                    prompt="test prompt",
                    history=[],
                )
            assert exc_info.value.status_code == 401

    @pytest.mark.anyio
    async def test_rate_limit_429(self):
        provider = GeminiProvider(api_key="AIzaSyB-limited-key", model_name="gemini-2.5-flash")

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Resource exhausted"

        with patch("llm.gemini_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await provider.generate_response(
                    prompt="test prompt",
                    history=[],
                )
            assert exc_info.value.status_code == 429

    @pytest.mark.anyio
    async def test_billing_error_detection(self):
        provider = GeminiProvider(api_key="AIzaSyB-free-key", model_name="gemini-2.5-flash")

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Billing account required. Enable billing at console.cloud.google.com"

        with patch("llm.gemini_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await provider.generate_response(
                    prompt="test prompt",
                    history=[],
                )
            assert exc_info.value.status_code == 402
            assert "billing" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_empty_response_raises_502(self):
        provider = GeminiProvider(api_key="AIzaSyB-mock-key", model_name="gemini-2.5-flash")

        mock_response_data = {
            "candidates": [{
                "content": {
                    "parts": [{"text": ""}],
                },
                "finishReason": "STOP",
            }],
            "usageMetadata": {},
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data
        mock_resp.text = json.dumps(mock_response_data)

        with patch("llm.gemini_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await provider.generate_response(
                    prompt="test prompt",
                    history=[],
                )
            assert exc_info.value.status_code == 502

    @pytest.mark.anyio
    async def test_insufficient_context_refusal(self):
        provider = GeminiProvider(api_key="AIzaSyB-mock-key", model_name="gemini-2.5-flash")

        result = await provider.generate_response(
            prompt="What color is the sky on Mars?",
            history=[],
            has_sufficient_context=False,
        )

        assert result.provider == "gemini"
        assert result.has_sufficient_context is False
        assert "insufficient evidence" in result.content.lower()
        assert result.citations == []


# ==============================================================================
# stream_response (mocked SSE)
# ==============================================================================

class TestGeminiStream:
    @pytest.mark.anyio
    async def test_insufficient_context_stream(self):
        """Streaming with insufficient context should yield refusal without hitting the API."""
        provider = GeminiProvider(api_key="AIzaSyB-mock-key", model_name="gemini-2.5-flash")

        chunks = []
        async for chunk in provider.stream_response(
            prompt="Irrelevant question",
            history=[],
            has_sufficient_context=False,
        ):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert "delta" in chunks[0]
        assert "insufficient evidence" in chunks[0]["delta"].lower()
        assert chunks[1]["done"] is True
        assert chunks[1]["has_sufficient_context"] is False

    @pytest.mark.anyio
    async def test_successful_stream(self):
        """Verify SSE streaming parses data lines and yields delta chunks."""
        provider = GeminiProvider(api_key="AIzaSyB-mock-key", model_name="gemini-2.5-flash")

        # Simulate SSE lines from streamGenerateContent
        sse_lines = [
            'data: {"candidates":[{"content":{"parts":[{"text":"Hello "}]}}]}',
            'data: {"candidates":[{"content":{"parts":[{"text":"World"}]},"finishReason":"STOP"}],"usageMetadata":{"promptTokenCount":10,"candidatesTokenCount":2}}',
        ]

        async def mock_aiter_lines():
            for line in sse_lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("llm.gemini_provider.httpx.AsyncClient", return_value=mock_client):
            chunks = []
            async for chunk in provider.stream_response(
                prompt="Say hello",
                history=[],
                context_text="",
            ):
                chunks.append(chunk)

        # Should have 2 delta chunks + 1 done chunk
        deltas = [c for c in chunks if "delta" in c]
        dones = [c for c in chunks if c.get("done")]

        assert len(deltas) == 2
        assert deltas[0]["delta"] == "Hello "
        assert deltas[1]["delta"] == "World"

        assert len(dones) == 1
        assert dones[0]["response"] == "Hello World"
        assert dones[0]["provider"] == "gemini"
        assert dones[0]["model"] == "gemini-2.5-flash"


# ==============================================================================
# Contents Builder
# ==============================================================================

class TestContentBuilder:
    def test_empty_history(self):
        provider = GeminiProvider(api_key="key")
        contents = provider._build_contents("Hello", [])
        assert len(contents) == 1
        assert contents[0]["role"] == "user"
        assert contents[0]["parts"][0]["text"] == "Hello"

    def test_history_role_mapping(self):
        provider = GeminiProvider(api_key="key")
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        contents = provider._build_contents("Follow up", history)
        assert len(contents) == 3
        assert contents[0]["role"] == "user"
        assert contents[1]["role"] == "model"  # assistant -> model
        assert contents[2]["role"] == "user"

    def test_system_role_skipped(self):
        provider = GeminiProvider(api_key="key")
        history = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hi"},
        ]
        contents = provider._build_contents("Follow up", history)
        # System messages are filtered out (not user/model)
        assert len(contents) == 2


# ==============================================================================
# Chat API Integration (mocked provider)
# ==============================================================================

class TestChatAPIGemini:
    def test_chat_gemini_missing_key_returns_400(self):
        """Verify that selecting Gemini when GEMINI_API_KEY is missing returns HTTP 400."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            response = client.post(
                "/api/chat",
                json={
                    "message": "What is the best pricing strategy?",
                    "provider": "gemini",
                    "use_rag": False,
                },
            )
            assert response.status_code == 400
            data = response.json()
            assert "Gemini API key is not configured" in data["detail"]

    def test_chat_with_mocked_gemini_success(self):
        """Verify /api/chat completes end-to-end with provider=gemini when mocked."""
        mock_response = ProviderResponse(
            content="Elena Verna emphasizes product-led growth loops for rapid PLG expansion.",
            model="gemini-2.5-flash",
            provider="gemini",
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
            mock_provider_instance.model_name = "gemini-2.5-flash"
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
                        "provider": "gemini",
                        "use_rag": True,
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["provider"] == "gemini"
                assert data["model"] == "gemini-2.5-flash"
                assert "Elena Verna" in data["response"]
                assert len(data["citations"]) == 1
                assert data["citations"][0]["guest"] == "Elena Verna"
