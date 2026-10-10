import os
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from llm.base import ProviderResponse
from rag.retriever import Citation, RetrievalResult


client = TestClient(app)


def test_cloud_provider_persists_messages_and_citations_to_session():
    """
    Verify that when chatting via a cloud provider, messages and verified citations
    are reliably stored in the PostgreSQL conversation session.
    """
    session_id = f"test-cloud-session-{uuid.uuid4().hex[:8]}"

    # Create conversation
    create_resp = client.post(
        "/api/conversations",
        json={"id": session_id, "title": "Cloud Provider Test", "category": "Product Strategy"},
    )
    assert create_resp.status_code == 201

    mock_response = ProviderResponse(
        content="Shreyas Doshi framework: LNO prioritizes leverage, neutral, overhead tasks.",
        model="claude-3-5-sonnet-20241022",
        provider="anthropic",
        citations=[
            Citation(
                guest="Shreyas Doshi",
                episode_title="Product Management Frameworks",
                excerpt="LNO helps leaders focus energy on leverage tasks.",
                relevance_score=0.96,
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
            mock_retrieval_res.context_text = "Shreyas Doshi LNO excerpt."
            mock_retrieve.return_value = mock_retrieval_res

            # Send chat message attached to session
            chat_resp = client.post(
                "/api/chat",
                json={
                    "message": "Explain Shreyas Doshi's LNO framework",
                    "conversation_id": session_id,
                    "provider": "anthropic",
                    "use_rag": True,
                },
            )
            assert chat_resp.status_code == 200
            data = chat_resp.json()
            assert data["conversation_id"] == session_id
            assert data["provider"] == "anthropic"

    # Retrieve conversation detail to verify database persistence
    detail_resp = client.get(f"/api/conversations/{session_id}")
    assert detail_resp.status_code == 200
    conv_data = detail_resp.json()

    messages = conv_data["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert "Shreyas Doshi's LNO" in messages[0]["content"]

    assert messages[1]["role"] == "assistant"
    assert "LNO prioritizes leverage" in messages[1]["content"]
    assert messages[1]["model"] == "claude-3-5-sonnet-20241022"
    assert len(messages[1]["citations"]) == 1
    assert messages[1]["citations"][0]["guest"] == "Shreyas Doshi"

    # Cleanup
    client.delete(f"/api/conversations/{session_id}")
