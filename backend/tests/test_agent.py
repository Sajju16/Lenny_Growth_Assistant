import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from agent.tools import (
    SEARCH_LENNY_TRANSCRIPTS_TOOL_SCHEMA,
    SearchToolInput,
    execute_search_transcripts,
)
from agent.transcript_agent import ClaudeTranscriptAgent
from rag.retriever import Citation, RetrievalResult


client = TestClient(app)


def test_agent_tool_schema_definition():
    schema = SEARCH_LENNY_TRANSCRIPTS_TOOL_SCHEMA
    assert schema["name"] == "search_lenny_transcripts"
    assert "query" in schema["input_schema"]["properties"]
    assert "top_k" in schema["input_schema"]["properties"]
    assert "query" in schema["input_schema"]["required"]


def test_agent_search_tool_execution():
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="Lenny excerpt on retention curves.",
        citations=[
            Citation(
                guest="Casey Winters",
                episode_title="Retention Strategies",
                excerpt="Retention is the single most important growth metric.",
                relevance_score=0.92,
            )
        ],
        raw_chunks=[{"text": "Retention chunk", "guest": "Casey Winters"}],
    )

    result = execute_search_transcripts(mock_retriever, query="retention curves", top_k=3)
    assert result["status"] == "success"
    assert result["has_sufficient_context"] is True
    assert len(result["citations"]) == 1
    assert result["citations"][0]["guest"] == "Casey Winters"
    mock_retriever.retrieve.assert_called_once_with(query="retention curves", top_k=3)


def test_agent_missing_key_raises_400():
    mock_retriever = MagicMock()
    agent = ClaudeTranscriptAgent(retriever=mock_retriever, api_key="")
    with pytest.raises(HTTPException) as exc_info:
        agent._ensure_api_key()
    assert exc_info.value.status_code == 400
    assert "Anthropic API key is not configured" in exc_info.value.detail


@pytest.mark.anyio
async def test_agent_tool_invocation_and_synthesis_loop():
    """
    Test the complete autonomous agent reasoning cycle:
    Turn 1: Claude decides to invoke tool 'search_lenny_transcripts'.
    Turn 2: Claude receives tool result and synthesizes grounded executive advice.
    """
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="April Dunford on positioning frameworks.",
        citations=[
            Citation(
                guest="April Dunford",
                episode_title="Positioning That Works",
                excerpt="Focus on your differentiated capability and customer value.",
                relevance_score=0.89,
            )
        ],
        raw_chunks=[],
    )

    agent = ClaudeTranscriptAgent(
        retriever=mock_retriever,
        api_key="sk-ant-mock-key-12345",
        model_name="claude-3-5-sonnet-20241022",
    )

    # Mock Claude responses
    # Turn 1: tool_use block
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "search_lenny_transcripts"
    tool_use_block.id = "tool_call_001"
    tool_use_block.input = {"query": "positioning frameworks", "top_k": 4}

    response_turn_1 = MagicMock()
    response_turn_1.content = [tool_use_block]
    response_turn_1.model = "claude-3-5-sonnet-20241022"
    response_turn_1.usage = MagicMock(output_tokens=30)

    # Turn 2: final synthesis text block
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = (
        "According to **April Dunford**, positioning starts with your differentiated capability.\n"
        "1. Map competitive alternatives.\n"
        "2. Identify unique attributes."
    )

    response_turn_2 = MagicMock()
    response_turn_2.content = [text_block]
    response_turn_2.model = "claude-3-5-sonnet-20241022"
    response_turn_2.usage = MagicMock(output_tokens=65)

    mock_anthropic_client = MagicMock()
    mock_anthropic_client.messages.create = AsyncMock(side_effect=[response_turn_1, response_turn_2])

    with patch("anthropic.AsyncAnthropic", return_value=mock_anthropic_client):
        agent_result = await agent.run(prompt="How should I position my product?")

        assert agent_result.provider == "anthropic-agent"
        assert "April Dunford" in agent_result.content
        assert len(agent_result.citations) == 1
        assert agent_result.citations[0].guest == "April Dunford"
        assert agent_result.has_sufficient_context is True
        assert mock_anthropic_client.messages.create.call_count == 2


def test_api_chat_with_agent_mode():
    """
    Test /api/chat with use_agent=True executes ClaudeTranscriptAgent and returns 200.
    """
    mock_retrieval_res = RetrievalResult(
        has_sufficient_context=True,
        context_text="Brian Balfour on growth loops.",
        citations=[
            Citation(
                guest="Brian Balfour",
                episode_title="Four Growth Fits",
                excerpt="Loops compound; funnels drop off.",
                relevance_score=0.95,
            )
        ],
        raw_chunks=[],
    )

    with patch("agent.transcript_agent.is_valid_anthropic_key", return_value=True):
        with patch.object(ClaudeTranscriptAgent, "_ensure_api_key", return_value="sk-ant-test"):
            # Turn 1
            tool_block = MagicMock(type="tool_use", id="tc1", input={"query": "growth loops", "top_k": 4})
            tool_block.name = "search_lenny_transcripts"
            r1 = MagicMock(content=[tool_block], model="claude-3-5-sonnet-20241022", usage=MagicMock(output_tokens=20))

            # Turn 2
            txt_block = MagicMock(type="text", text="Brian Balfour states that growth loops compound.")
            r2 = MagicMock(content=[txt_block], model="claude-3-5-sonnet-20241022", usage=MagicMock(output_tokens=40))

            mock_client = MagicMock()
            mock_client.messages.create = AsyncMock(side_effect=[r1, r2])

            with patch("anthropic.AsyncAnthropic", return_value=mock_client):
                with patch("main.retriever.retrieve", return_value=mock_retrieval_res):
                    resp = client.post(
                        "/api/chat",
                        json={
                            "message": "Explain growth loops versus funnels",
                            "use_agent": True,
                        },
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["provider"] == "anthropic-agent"
                    assert "Brian Balfour" in data["response"]
                    assert len(data["citations"]) == 1
                    assert data["citations"][0]["guest"] == "Brian Balfour"
