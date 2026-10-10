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
