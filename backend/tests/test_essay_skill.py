import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base, get_db
from main import app
from skills.essay_skill import generate_ship30_essay, extract_title_from_markdown
from rag.retriever import Citation, RetrievalResult
from llm.base import ProviderResponse

SAMPLE_ESSAY_TEXT = """# The Contrarian Blueprint: Why Most Positioning Fails Before Launch

Most founders believe great products sell themselves. They spend eighteen months perfecting code in isolation, only to launch to deafening silence. As April Dunford pointed out, positioning isn't just marketing copy—it is the context that enables customers to understand your value.

## The Mental Trap of Category Creation

When startups launch, their instinctive impulse is to invent a brand new category. They want to be the "Uber for dog walking" or the "AI-native productivity operating system." But category creation is the most expensive and precarious strategy in technology.

Instead, Dunford advocates for identifying your competitive alternatives first. What would customers do if you did not exist? Often, the answer is not a direct rival, but a messy Excel spreadsheet or a clunky legacy process.

## Mapping Unique Attributes to Real Value

Once you understand what you are replacing, you can isolate your truly unique attributes. But features alone do not win markets. Every feature must map directly to demonstrable business value.

Consider the classic positioning canvas:
- **Competitive Alternative:** What do they use today? (e.g., manual spreadsheets).
- **Unique Capability:** What can only your product deliver? (e.g., automated real-time reconciliation).
- **Customer Value:** Why does that difference matter to their bottom line?

## Monday Morning Takeaways

To immediately apply this framework to your product:
1. Interview five recent churned or won customers to ask what alternative they evaluated.
2. List your three differentiating attributes and cross out any feature that competitors also claim.
3. Align your sales pitch around the specific problem context before showing a single screen.

Positioning is not a slogan; it is the strategic foundation of your entire go-to-market engine.
"""

@pytest.fixture
def client_with_test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_extract_title_from_markdown():
    title = extract_title_from_markdown(SAMPLE_ESSAY_TEXT, "Default Title")
    assert title == "The Contrarian Blueprint: Why Most Positioning Fails Before Launch"


@pytest.mark.anyio
async def test_essay_skill_direct_generation_with_citations():
    mock_retriever = MagicMock()
    mock_citation = Citation(
        guest="April Dunford",
        episode_title="How to Nail Product Positioning",
        youtube_url="https://youtube.com/watch?v=sample1",
        excerpt="Positioning is the context you provide to help customers understand your value.",
        relevance_score=0.92,
    )
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="Positioning is context.",
        citations=[mock_citation],
        raw_chunks=[{"text": "Positioning is context."}],
    )

    mock_provider = MagicMock()
    mock_provider.model_name = "test-model"
    mock_provider.provider_name = "mock"
    mock_provider.generate_response = AsyncMock(return_value=ProviderResponse(
        content=SAMPLE_ESSAY_TEXT,
        model="test-model",
        provider="mock",
        citations=[mock_citation],
        has_sufficient_context=True,
        eval_count=200,
        total_duration=1000000,
    ))

    result = await generate_ship30_essay(
        topic="Product positioning for startups",
        provider=mock_provider,
        retriever=mock_retriever,
        conversation_id=None,
        db=None,
    )

    assert "The Contrarian Blueprint" in result.title
    assert len(result.citations) == 1
    assert result.citations[0].guest == "April Dunford"
    assert result.has_sufficient_context is True
    assert result.word_count > 100
    assert "Monday Morning Takeaways" in result.essay_content


@pytest.mark.anyio
async def test_essay_skill_insufficient_evidence():
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=False,
        context_text="",
        citations=[],
        raw_chunks=[],
    )

    mock_provider = MagicMock()
    mock_provider.model_name = "test-model"
    mock_provider.provider_name = "mock"
    mock_provider.generate_response = AsyncMock()

    result = await generate_ship30_essay(
        topic="Quantum physics lithography",
        provider=mock_provider,
        retriever=mock_retriever,
        conversation_id=None,
        db=None,
    )

    assert result.has_sufficient_context is False
    assert "insufficient evidence" in result.essay_content.lower()
    assert len(result.citations) == 0
    mock_provider.generate_response.assert_not_called()


def test_api_skills_essay_endpoint(client_with_test_db):
    conv_resp = client_with_test_db.post("/api/conversations", json={"title": "Essay Skill Test"})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    mock_citation = Citation(
        guest="April Dunford",
        episode_title="How to Nail Product Positioning",
        youtube_url="https://youtube.com/watch?v=dunford",
        excerpt="Positioning defines how you are best in the world.",
        relevance_score=0.95,
    )

    with patch("main.retriever") as mock_retriever, \
         patch("main.get_llm_provider") as mock_get_provider:

        mock_retriever.retrieve.return_value = RetrievalResult(
            has_sufficient_context=True,
            context_text="Positioning context",
            citations=[mock_citation],
            raw_chunks=[{"text": "Positioning context"}],
        )

        mock_provider = MagicMock()
        mock_provider.model_name = "test-model"
        mock_provider.provider_name = "mock"
        mock_provider.generate_response = AsyncMock(return_value=ProviderResponse(
            content=SAMPLE_ESSAY_TEXT,
            model="test-model",
            provider="mock",
            citations=[mock_citation],
            has_sufficient_context=True,
        ))
        mock_get_provider.return_value = mock_provider

        payload = {
            "conversation_id": conv_id,
            "topic": "Product positioning frameworks for B2B SaaS",
        }
        resp = client_with_test_db.post("/api/skills/essay", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert "essay" in data
        assert "artifact" in data
        assert data["artifact"]["artifact_type"] == "markdown"
        assert data["artifact"]["conversation_id"] == conv_id
        assert len(data["artifact"]["citations"]) == 1
        assert data["artifact"]["citations"][0]["guest"] == "April Dunford"

        # Verify conversation in db reflects the generated artifact
        conv_check = client_with_test_db.get(f"/api/conversations/{conv_id}")
        assert conv_check.status_code == 200
        conv_data = conv_check.json()
        assert len(conv_data["artifacts"]) == 1
        assert conv_data["active_artifact"]["id"] == data["artifact"]["id"]


@pytest.mark.anyio
async def test_essay_skill_forwards_system_prompt():
    """Verify generate_ship30_essay forwards SHIP30_SYSTEM_PROMPT to provider."""
    from skills.essay_skill import SHIP30_SYSTEM_PROMPT

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="Positioning context",
        citations=[Citation(guest="April Dunford", episode_title="Positioning", excerpt="Context is king.", relevance_score=0.92)],
        raw_chunks=[{"text": "Positioning context"}],
    )

    full_draft = ("Word " * 700) # >= 600 words to avoid bounded enrichment pass
    mock_provider = MagicMock()
    mock_provider.model_name = "qwen2.5:3b"
    mock_provider.provider_name = "ollama"
    mock_provider.generate_response = AsyncMock(return_value=ProviderResponse(
        content=full_draft,
        model="qwen2.5:3b",
        provider="ollama",
    ))

    await generate_ship30_essay(
        topic="Positioning strategy",
        provider=mock_provider,
        retriever=mock_retriever,
        timeout=420.0,
    )

    mock_provider.generate_response.assert_called_once()
    _, kwargs = mock_provider.generate_response.call_args
    assert kwargs.get("system_prompt") == SHIP30_SYSTEM_PROMPT
    assert kwargs.get("timeout") == 420.0


@pytest.mark.anyio
async def test_essay_skill_bounded_enrichment_when_under_word_threshold():
    """Verify bounded enrichment triggers at most once if draft < 600 words and remaining budget >= 90s."""
    short_draft = "# Short Draft\n\nThis is a short strategic essay about positioning." # ~9 words

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="Positioning context",
        citations=[Citation(guest="April Dunford", episode_title="Positioning", excerpt="Context is king.", relevance_score=0.92)],
        raw_chunks=[{"text": "Positioning context"}],
    )

    enrichment_section = "## Extended Playbook\n\nHere is a comprehensive tactical breakdown of sales pitches."

    mock_provider = MagicMock()
    mock_provider.model_name = "qwen2.5:3b"
    mock_provider.provider_name = "ollama"
    mock_provider.generate_response = AsyncMock(side_effect=[
        ProviderResponse(content=short_draft, model="qwen2.5:3b", provider="ollama", eval_count=30, total_duration=1000),
        ProviderResponse(content=enrichment_section, model="qwen2.5:3b", provider="ollama", eval_count=50, total_duration=2000),
    ])

    res = await generate_ship30_essay(
        topic="Positioning strategy",
        provider=mock_provider,
        retriever=mock_retriever,
        timeout=420.0,
    )

    # Must have called generate_response exactly twice (1 base + 1 bounded enrichment)
    assert mock_provider.generate_response.call_count == 2
    assert "Short Draft" in res.essay_content
    assert "Extended Playbook" in res.essay_content


@pytest.mark.anyio
async def test_essay_skill_skips_enrichment_when_over_threshold():
    """Verify bounded enrichment does NOT trigger if draft is already >= 600 words."""
    long_draft = ("Word " * 650) # 650 words

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="Positioning context",
        citations=[],
        raw_chunks=[],
    )

    mock_provider = MagicMock()
    mock_provider.model_name = "qwen2.5:3b"
    mock_provider.provider_name = "ollama"
    mock_provider.generate_response = AsyncMock(return_value=ProviderResponse(
        content=long_draft,
        model="qwen2.5:3b",
        provider="ollama",
    ))

    res = await generate_ship30_essay(
        topic="Positioning strategy",
        provider=mock_provider,
        retriever=mock_retriever,
        timeout=420.0,
    )

    # Exactly one call
    assert mock_provider.generate_response.call_count == 1
    assert res.word_count >= 600


@pytest.mark.anyio
async def test_ollama_provider_payload_includes_num_predict():
    """Verify OllamaProvider includes options: {'num_predict': 2048} in request payload."""
    from llm.ollama_provider import OllamaProvider
    import httpx

    provider = OllamaProvider()
    captured_payload = {}

    async def mock_post(url, json=None, headers=None, timeout=None):
        nonlocal captured_payload
        captured_payload = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "Test response"},
            "model": "qwen2.5:3b",
            "eval_count": 100,
            "total_duration": 1000000000,
        }
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        await provider.generate_response(
            prompt="Test prompt",
            history=[],
            context_text="",
            has_sufficient_context=True,
        )

    assert "options" in captured_payload
    assert captured_payload["options"]["num_predict"] == 2048


def test_chat_endpoint_auto_routes_essay_intent_keywords(client_with_test_db):
    """Verify /api/chat auto-routes 'Write an essay on...' to essay skill."""
    conv_resp = client_with_test_db.post("/api/conversations", json={"title": "Intent Routing Test"})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    with patch("main.retriever") as mock_retriever, \
         patch("main.get_llm_provider") as mock_get_provider:

        mock_retriever.retrieve.return_value = RetrievalResult(
            has_sufficient_context=True,
            context_text="Positioning context",
            citations=[Citation(guest="April Dunford", episode_title="Positioning", excerpt="Context matters.", relevance_score=0.92)],
            raw_chunks=[{"text": "Positioning context"}],
        )

        full_essay = ("Word " * 650)
        mock_provider = MagicMock()
        mock_provider.model_name = "qwen2.5:3b"
        mock_provider.provider_name = "ollama"
        mock_provider.generate_response = AsyncMock(return_value=ProviderResponse(
            content=f"# The Positioning Blueprint\n\n{full_essay}",
            model="qwen2.5:3b",
            provider="ollama",
        ))
        mock_get_provider.return_value = mock_provider

        resp = client_with_test_db.post("/api/chat", json={
            "conversation_id": conv_id,
            "message": "Write an essay on How to find product-market fit for an early-stage startup",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "Positioning Blueprint" in data["response"]
        assert data.get("artifact_id") is not None
        assert data.get("artifact") is not None
        assert data["artifact"]["badge"] == "Ship 30 for 30 Essay"


def test_chat_endpoint_auto_routes_slash_essay_command(client_with_test_db):
    """Verify /api/chat auto-routes '/essay PMF framework' to essay skill."""
    conv_resp = client_with_test_db.post("/api/conversations", json={"title": "Slash Routing Test"})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    with patch("main.retriever") as mock_retriever, \
         patch("main.get_llm_provider") as mock_get_provider:

        mock_retriever.retrieve.return_value = RetrievalResult(
            has_sufficient_context=True,
            context_text="PMF context",
            citations=[Citation(guest="Rahul Vohra", episode_title="Superhuman PMF", excerpt="40% very disappointed.", relevance_score=0.94)],
            raw_chunks=[{"text": "PMF context"}],
        )

        full_essay = ("Word " * 650)
        mock_provider = MagicMock()
        mock_provider.model_name = "qwen2.5:3b"
        mock_provider.provider_name = "ollama"
        mock_provider.generate_response = AsyncMock(return_value=ProviderResponse(
            content=f"# Superhuman Engine\n\n{full_essay}",
            model="qwen2.5:3b",
            provider="ollama",
        ))
        mock_get_provider.return_value = mock_provider

        resp = client_with_test_db.post("/api/chat", json={
            "conversation_id": conv_id,
            "message": "/essay Rahul Vohra Superhuman PMF engine",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("artifact_id") is not None
        assert data["artifact"]["badge"] == "Ship 30 for 30 Essay"


@pytest.mark.anyio
async def test_essay_skill_timeout_persists_actionable_guidance():
    """Verify that a 504 timeout during essay generation writes actionable explanation to PostgreSQL."""
    from fastapi import HTTPException
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.connection import Base
    import database.crud as crud
    from database.schemas import ConversationCreate

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()

    conv = crud.create_conversation(db, ConversationCreate(id="conv-timeout-test", title="Timeout Test"))

    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="PMF context",
        citations=[Citation(guest="Rahul Vohra", episode_title="Superhuman PMF", excerpt="40% PMF engine.", relevance_score=0.9)],
        raw_chunks=[{"text": "PMF context"}],
    )

    mock_provider = MagicMock()
    mock_provider.model_name = "qwen2.5:3b"
    mock_provider.provider_name = "ollama"
    mock_provider.generate_response = AsyncMock(side_effect=HTTPException(status_code=504, detail="Ollama timed out"))

    with pytest.raises(HTTPException) as exc_info:
        await generate_ship30_essay(
            topic="How to find product-market fit for an early-stage startup",
            provider=mock_provider,
            retriever=mock_retriever,
            conversation_id=conv.id,
            db=db,
            timeout=420.0,
        )

    assert exc_info.value.status_code == 504
    assert "2.3–2.7 tokens/second" in exc_info.value.detail or "tokens/second" in exc_info.value.detail
    assert "ANTHROPIC_API_KEY" in exc_info.value.detail

    # Verify message was persisted into database so conversation is preserved upon refresh
    messages = crud.get_conversation_messages(db, conv.id)
    assert len(messages) == 1
    assert messages[0].role == "assistant"
    assert "Local Inference Timeout Reached" in messages[0].content
    assert "Claude 3.5 Sonnet" in messages[0].content


def test_chat_endpoint_timeout_persists_actionable_guidance(client_with_test_db):
    """Verify that a 504 timeout via /api/chat leaves the conversation preserved in PostgreSQL."""
    from fastapi import HTTPException

    conv_resp = client_with_test_db.post("/api/conversations", json={"title": "Chat Timeout Test"})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    with patch("main.retriever") as mock_retriever, \
         patch("main.get_llm_provider") as mock_get_provider:

        mock_retriever.retrieve.return_value = RetrievalResult(
            has_sufficient_context=True,
            context_text="Positioning context",
            citations=[Citation(guest="April Dunford", episode_title="Positioning", excerpt="Context is king.", relevance_score=0.9)],
            raw_chunks=[{"text": "Positioning context"}],
        )

        mock_provider = MagicMock()
        mock_provider.model_name = "qwen2.5:3b"
        mock_provider.provider_name = "ollama"
        mock_provider.generate_response = AsyncMock(side_effect=HTTPException(status_code=504, detail="Ollama timed out after 180s"))
        mock_get_provider.return_value = mock_provider

        resp = client_with_test_db.post("/api/chat", json={
            "conversation_id": conv_id,
            "message": "Write an essay on B2B positioning",
        })
        assert resp.status_code == 504

        # Upon page refresh, conversation details must include the assistant timeout explanation
        conv_check = client_with_test_db.get(f"/api/conversations/{conv_id}")
        assert conv_check.status_code == 200
        conv_data = conv_check.json()
        assert len(conv_data["messages"]) == 2
        assert conv_data["messages"][0]["role"] == "user"
        assert conv_data["messages"][1]["role"] == "assistant"
        assert "Local Inference Timeout Reached" in conv_data["messages"][1]["content"]
