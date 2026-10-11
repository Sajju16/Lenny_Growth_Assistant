import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from main import app
from llm.ollama_provider import OllamaProvider
from llm.base import ProviderResponse
from rag.retriever import Citation, RetrievalResult
from rag.vector_store import OllamaEmbeddingClient


@pytest.fixture
def client():
    return TestClient(app)


def test_query_embedding_cache():
    """Verify in-memory caching of query embeddings in OllamaEmbeddingClient."""
    embedder = OllamaEmbeddingClient()
    mock_emb = [0.123] * 768

    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"embeddings": [mock_emb]}
        mock_post.return_value = mock_resp

        # First query call (cache miss)
        res1 = embedder.get_embeddings(["What is retention?"], is_query=True)
        assert len(res1) == 1
        assert res1[0] == mock_emb
        assert mock_post.call_count == 1

        # Second identical query call (cache hit -> 0ms, no network call)
        res2 = embedder.get_embeddings(["What is retention?"], is_query=True)
        assert len(res2) == 1
        assert res2[0] == mock_emb
        assert mock_post.call_count == 1  # Not called again!


@pytest.mark.anyio
async def test_stream_response_insufficient_evidence_fast():
    """Verify that unsupported questions immediately yield refusal without invoking Ollama."""
    provider = OllamaProvider()

    chunks = []
    async for chunk in provider.stream_response(
        prompt="How do I bake sourdough croissants?",
        history=[],
        context_text="",
        citations=[],
        has_sufficient_context=False,
    ):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert "delta" in chunks[0]
    assert "insufficient evidence" in chunks[0]["delta"].lower()
    assert chunks[1].get("done") is True
    assert chunks[1].get("has_sufficient_context") is False
    assert chunks[1].get("citations") == []


@pytest.mark.anyio
async def test_stream_response_tokens_and_metadata():
    """Verify that Ollama stream_response yields tokens and ends with metadata."""
    provider = OllamaProvider()

    mock_lines = [
        json.dumps({"message": {"content": "Dan "}, "done": False}),
        json.dumps({"message": {"content": "Hockenmaier "}, "done": False}),
        json.dumps({"message": {"content": "advises "}, "done": False}),
        json.dumps({
            "message": {"content": "early focus."},
            "done": True,
            "eval_count": 5,
            "total_duration": 500000000,
            "model": "qwen2.5:1.5b",
        }),
    ]

    class MockStreamResponse:
        status_code = 200
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def aiter_lines(self):
            for l in mock_lines:
                yield l

    class MockAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def stream(self, method, url, json=None):
            assert json.get("stream") is True
            assert json.get("keep_alive") == "30m"
            assert json.get("options", {}).get("num_predict") == 384
            return MockStreamResponse()

    with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
        chunks = []
        async for chunk in provider.stream_response(
            prompt="Tell me about retention",
            history=[],
            context_text="Transcript evidence",
            citations=[Citation(guest="Dan Hockenmaier", episode_title="Growth", excerpt="Retention...", relevance_score=0.82)],
            has_sufficient_context=True,
            max_tokens=384,
        ):
            chunks.append(chunk)

    tokens = [c["delta"] for c in chunks if "delta" in c]
    assert "".join(tokens) == "Dan Hockenmaier advises early focus."
    done_chunk = [c for c in chunks if c.get("done")][0]
    assert done_chunk["eval_count"] == 5
    assert done_chunk["model"] == "qwen2.5:1.5b"
    assert done_chunk["metadata"]["ttft_sec"] is not None


def test_api_chat_stream_insufficient_evidence_endpoint(client):
    """Verify SSE streaming for out-of-domain question."""
    with patch("main.retriever.retrieve") as mock_retrieve:
        mock_retrieve.return_value = RetrievalResult(
            has_sufficient_context=False,
            context_text="",
            citations=[],
            raw_chunks=[],
        )

        response = client.post("/api/chat/stream", json={"message": "How do I bake sourdough croissants?"})
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        lines = response.text.split("\n")
        events = [l for l in lines if l.startswith("event:")]
        data_lines = [json.loads(l.replace("data:", "").strip()) for l in lines if l.startswith("data:")]

        assert any("token" in e for e in events)
        assert any("done" in e for e in events)
        done_data = data_lines[-1]
        assert done_data["has_sufficient_context"] is False
        assert done_data["citations"] == []
        assert "insufficient evidence" in done_data["response"].lower()


@pytest.mark.anyio
async def test_stream_response_tps_excludes_ttft():
    """Verify that TPS calculation in stream_response divides by (elapsed_sec - ttft)."""
    provider = OllamaProvider()

    mock_lines = [
        json.dumps({"message": {"content": "First token "}, "done": False}),
        json.dumps({"message": {"content": "second token."}, "done": False}),
        json.dumps({
            "message": {"content": ""},
            "done": True,
            "eval_count": 20,
            "total_duration": 1000000000,
            "model": "qwen2.5:1.5b",
        }),
    ]

    class MockStreamResponse:
        status_code = 200
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def aiter_lines(self):
            for l in mock_lines:
                yield l

    class MockAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def stream(self, method, url, json=None):
            return MockStreamResponse()

    # Mock time.perf_counter sequence:
    # Call 1: start_time = 0.0
    # Call 2 (first token): first_token_time = 4.0 - 0.0 = 4.0 (TTFT = 4.0s)
    # Call 3 (stream end): elapsed_sec = 10.0 - 0.0 = 10.0 (Total elapsed = 10.0s)
    # Generation duration = 10.0 - 4.0 = 6.0s
    # Expected TPS = 20 tokens / 6.0s = 3.33 tokens/s (NOT 20 / 10 = 2.0)
    fake_times = [0.0, 4.0, 10.0]
    fake_iter = iter(fake_times)

    with patch("time.perf_counter", side_effect=lambda: next(fake_iter, 10.0)):
        with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
            chunks = []
            async for chunk in provider.stream_response(
                prompt="Explain retention",
                history=[],
                context_text="Evidence context",
                citations=[],
                has_sufficient_context=True,
                max_tokens=384,
            ):
                chunks.append(chunk)

    done_chunk = [c for c in chunks if c.get("done")][0]
    meta = done_chunk["metadata"]
    assert meta["elapsed_sec"] == 10.0
    assert meta["ttft_sec"] == 4.0
    assert meta["gen_duration_sec"] == 6.0
    assert meta["eval_count"] == 20
    # TPS must be 20 / 6.0 = 3.33 tokens/s (excluding TTFT)
    assert meta["tps"] == pytest.approx(3.33, rel=1e-2)
    # All existing metadata keys are preserved
    for required_key in ["total_duration", "elapsed_sec", "ttft_sec", "eval_count", "tps"]:
        assert required_key in meta


@pytest.mark.anyio
async def test_stream_response_tps_zero_and_negative_duration_safe():
    """Verify that zero or negative generation durations safely produce tps=0.0 without errors."""
    provider = OllamaProvider()

    mock_lines = [
        json.dumps({"message": {"content": "Immediate token"}, "done": False}),
        json.dumps({
            "message": {"content": ""},
            "done": True,
            "eval_count": 5,
            "total_duration": 100000000,
            "model": "qwen2.5:1.5b",
        }),
    ]

    class MockStreamResponse:
        status_code = 200
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def aiter_lines(self):
            for l in mock_lines:
                yield l

    class MockAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def stream(self, method, url, json=None):
            return MockStreamResponse()

    # first_token_time = 5.0, elapsed_sec = 5.0 -> gen_duration = 0.0
    fake_times = [0.0, 5.0, 5.0, 5.0, 5.0]
    fake_iter = iter(fake_times)

    with patch("time.perf_counter", side_effect=lambda: next(fake_iter, 5.0)):
        with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
            chunks = []
            async for chunk in provider.stream_response(
                prompt="Zero duration test",
                history=[],
                context_text="Evidence context",
                citations=[],
                has_sufficient_context=True,
            ):
                chunks.append(chunk)

    done_chunk = [c for c in chunks if c.get("done")][0]
    assert done_chunk["metadata"]["gen_duration_sec"] == 0.0
    assert done_chunk["metadata"]["tps"] == 0.0


def test_api_chat_stream_retrieval_top_k_two(client):
    """Verify that /api/chat/stream passes top_k=2 to retriever.retrieve."""
    with patch("main.retriever.retrieve") as mock_retrieve:
        mock_retrieve.return_value = RetrievalResult(
            has_sufficient_context=False,
            context_text="",
            citations=[],
            raw_chunks=[],
        )

        response = client.post("/api/chat/stream", json={"message": "How do early startups improve retention?"})
        assert response.status_code == 200
        mock_retrieve.assert_called_once_with(query="How do early startups improve retention?", top_k=2)


def test_api_chat_standard_retrieval_top_k_two(client):
    """Verify that /api/chat standard endpoint passes top_k=2 to retriever.retrieve."""
    with patch("main.retriever.retrieve") as mock_retrieve:
        mock_retrieve.return_value = RetrievalResult(
            has_sufficient_context=False,
            context_text="",
            citations=[],
            raw_chunks=[],
        )

        response = client.post("/api/chat", json={"message": "How do early startups improve retention?"})
        assert response.status_code == 200
        mock_retrieve.assert_called_once_with(query="How do early startups improve retention?", top_k=2)


@pytest.mark.anyio
async def test_stream_response_captures_native_ollama_metrics():
    """Verify that Ollama stream_response captures and extracts native duration & count metrics."""
    provider = OllamaProvider()

    mock_lines = [
        json.dumps({"message": {"content": "Token1 "}, "done": False}),
        json.dumps({
            "message": {"content": ""},
            "done": True,
            "load_duration": 1500000000,          # 1.5s
            "prompt_eval_count": 512,
            "prompt_eval_duration": 20000000000,   # 20.0s
            "eval_count": 80,
            "eval_duration": 10000000000,          # 10.0s
            "total_duration": 31500000000,         # 31.5s
            "model": "qwen2.5:1.5b",
        }),
    ]

    class MockStreamResponse:
        status_code = 200
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def aiter_lines(self):
            for l in mock_lines:
                yield l

    class MockAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def stream(self, method, url, json=None):
            return MockStreamResponse()

    with patch("httpx.AsyncClient", return_value=MockAsyncClient()):
        chunks = []
        async for chunk in provider.stream_response(
            prompt="Test query",
            history=[],
            context_text="Evidence",
            citations=[],
            has_sufficient_context=True,
        ):
            chunks.append(chunk)

    done_chunk = [c for c in chunks if c.get("done")][0]

    # Verify native metrics captured on done chunk
    assert done_chunk["load_duration"] == 1500000000
    assert done_chunk["prompt_eval_count"] == 512
    assert done_chunk["prompt_eval_duration"] == 20000000000
    assert done_chunk["eval_count"] == 80
    assert done_chunk["eval_duration"] == 10000000000
    assert done_chunk["total_duration"] == 31500000000

    # Verify readable seconds in metadata
    meta = done_chunk["metadata"]
    assert meta["load_sec"] == 1.5
    assert meta["prompt_eval_count"] == 512
    assert meta["prompt_eval_sec"] == 20.0
    assert meta["eval_sec"] == 10.0
    assert meta["total_duration"] == 31500000000
    assert meta["eval_count"] == 80
    # Existing fields remain intact
    assert "elapsed_sec" in meta
    assert "ttft_sec" in meta
    assert "tps" in meta


# ==============================================================================
# Conversation-history truncation tests
# ==============================================================================

from main import _truncate_history, _HISTORY_MAX_MESSAGES


class TestTruncateHistory:
    """Unit tests for the _truncate_history helper."""

    def test_short_history_returned_unchanged(self):
        """History with <= max_messages items is returned as-is (same object)."""
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = _truncate_history(history)
        assert result is history  # no copy when not truncated

    def test_empty_history_returned_unchanged(self):
        result = _truncate_history([])
        assert result == []

    def test_exactly_max_messages_returned_unchanged(self):
        history = [{"role": "user", "content": str(i)} for i in range(_HISTORY_MAX_MESSAGES)]
        result = _truncate_history(history)
        assert result is history

    def test_long_history_truncated_to_last_max_messages(self):
        """History longer than max_messages keeps only the LATEST items."""
        history = [{"role": "user", "content": str(i)} for i in range(10)]
        result = _truncate_history(history)
        assert len(result) == _HISTORY_MAX_MESSAGES
        # Must be the LAST 4 items (indices 6..9)
        assert result == history[-_HISTORY_MAX_MESSAGES:]

    def test_custom_max_messages_respected(self):
        history = [{"role": "user", "content": str(i)} for i in range(8)]
        result = _truncate_history(history, max_messages=2)
        assert len(result) == 2
        assert result == history[-2:]

    def test_order_preserved_after_truncation(self):
        """Chronological order is maintained after truncation."""
        history = [{"role": "user", "content": f"msg{i}"} for i in range(6)]
        result = _truncate_history(history, max_messages=4)
        assert result[0]["content"] == "msg2"
        assert result[-1]["content"] == "msg5"


def _make_long_history(n: int):
    """Create n alternating user/assistant messages."""
    msgs = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": f"message {i}"})
    return msgs


def test_stream_endpoint_truncates_long_history_to_four(client):
    """
    /api/chat/stream must pass only the last 4 history messages to the LLM,
    even if the client sends 10 history items.
    """
    long_history = _make_long_history(10)
    expected_bounded = long_history[-4:]

    captured_history = {}

    with patch("main.retriever.retrieve") as mock_retrieve, \
         patch("main.get_llm_provider") as mock_factory:

        mock_retrieve.return_value = RetrievalResult(
            has_sufficient_context=True,
            context_text="Some context",
            citations=[],
            raw_chunks=[{}],
        )

        async def fake_stream(prompt, history, context_text, citations,
                              has_sufficient_context, max_tokens=384):
            captured_history["history"] = history
            yield {"delta": "ok"}
            yield {
                "done": True,
                "response": "ok",
                "model": "qwen2.5:3b",
                "provider": "ollama",
                "citations": [],
                "has_sufficient_context": True,
                "eval_count": 1,
                "total_duration": None,
                "load_duration": None,
                "prompt_eval_count": None,
                "prompt_eval_duration": None,
                "eval_duration": None,
                "metadata": {"ttft_sec": 0.1, "elapsed_sec": 0.2, "eval_count": 1, "tps": 5.0},
            }

        mock_provider = MagicMock()
        mock_provider.model_name = "qwen2.5:3b"
        mock_provider._model_name = "qwen2.5:3b"
        mock_provider.stream_response = fake_stream
        mock_factory.return_value = mock_provider

        response = client.post(
            "/api/chat/stream",
            json={"message": "What is retention?", "history": long_history},
        )

    assert response.status_code == 200
    assert captured_history.get("history") == expected_bounded


def test_stream_endpoint_short_history_unchanged(client):
    """
    /api/chat/stream must forward short history (<=4 items) without modification.
    """
    short_history = _make_long_history(2)

    captured_history = {}

    with patch("main.retriever.retrieve") as mock_retrieve, \
         patch("main.get_llm_provider") as mock_factory:

        mock_retrieve.return_value = RetrievalResult(
            has_sufficient_context=True,
            context_text="Some context",
            citations=[],
            raw_chunks=[{}],
        )

        async def fake_stream(prompt, history, context_text, citations,
                              has_sufficient_context, max_tokens=384):
            captured_history["history"] = history
            yield {"delta": "ok"}
            yield {
                "done": True,
                "response": "ok",
                "model": "qwen2.5:3b",
                "provider": "ollama",
                "citations": [],
                "has_sufficient_context": True,
                "eval_count": 1,
                "total_duration": None,
                "load_duration": None,
                "prompt_eval_count": None,
                "prompt_eval_duration": None,
                "eval_duration": None,
                "metadata": {"ttft_sec": 0.1, "elapsed_sec": 0.2, "eval_count": 1, "tps": 5.0},
            }

        mock_provider = MagicMock()
        mock_provider.model_name = "qwen2.5:3b"
        mock_provider._model_name = "qwen2.5:3b"
        mock_provider.stream_response = fake_stream
        mock_factory.return_value = mock_provider

        response = client.post(
            "/api/chat/stream",
            json={"message": "What is retention?", "history": short_history},
        )

    assert response.status_code == 200
    assert captured_history.get("history") == short_history


def test_chat_endpoint_truncates_long_history_to_four(client):
    """
    /api/chat must pass only the last 4 history messages to the LLM,
    even if the client sends 10 history items.
    """
    long_history = _make_long_history(10)
    expected_bounded = long_history[-4:]

    captured_history = {}

    with patch("main.retriever.retrieve") as mock_retrieve, \
         patch("main.get_llm_provider") as mock_factory:

        mock_retrieve.return_value = RetrievalResult(
            has_sufficient_context=True,
            context_text="Some context",
            citations=[],
            raw_chunks=[{}],
        )

        async def fake_generate(prompt, history, context_text, citations,
                                has_sufficient_context, max_tokens=384, **kwargs):
            captured_history["history"] = history
            from llm.base import ProviderResponse
            return ProviderResponse(
                content="Test response from Dan Hockenmaier about retention",
                model="qwen2.5:3b",
                provider="ollama",
                citations=[],
                has_sufficient_context=True,
            )

        mock_provider = MagicMock()
        mock_provider.model_name = "qwen2.5:3b"
        mock_provider._model_name = "qwen2.5:3b"
        mock_provider.generate_response = AsyncMock(side_effect=fake_generate)
        mock_factory.return_value = mock_provider

        response = client.post(
            "/api/chat",
            json={"message": "What is retention?", "history": long_history},
        )

    assert response.status_code == 200
    assert captured_history.get("history") == expected_bounded


def test_chat_endpoint_short_history_unchanged(client):
    """
    /api/chat must forward short history (<=4 items) without modification.
    """
    short_history = _make_long_history(3)

    captured_history = {}

    with patch("main.retriever.retrieve") as mock_retrieve, \
         patch("main.get_llm_provider") as mock_factory:

        mock_retrieve.return_value = RetrievalResult(
            has_sufficient_context=True,
            context_text="Some context",
            citations=[],
            raw_chunks=[{}],
        )

        async def fake_generate(prompt, history, context_text, citations,
                                has_sufficient_context, max_tokens=384, **kwargs):
            captured_history["history"] = history
            from llm.base import ProviderResponse
            return ProviderResponse(
                content="Answer grounded in transcript",
                model="qwen2.5:3b",
                provider="ollama",
                citations=[],
                has_sufficient_context=True,
            )

        mock_provider = MagicMock()
        mock_provider.model_name = "qwen2.5:3b"
        mock_provider._model_name = "qwen2.5:3b"
        mock_provider.generate_response = AsyncMock(side_effect=fake_generate)
        mock_factory.return_value = mock_provider

        response = client.post(
            "/api/chat",
            json={"message": "What is retention?", "history": short_history},
        )

    assert response.status_code == 200
    assert captured_history.get("history") == short_history
