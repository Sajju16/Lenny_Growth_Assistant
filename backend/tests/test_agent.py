import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

import claude_agent_sdk
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SdkMcpTool,
    TextBlock,
)

from main import app
from agent.tools import (
    SEARCH_LENNY_TRANSCRIPTS_TOOL_SCHEMA,
    SearchToolInput,
    execute_search_transcripts,
    make_sdk_search_tool,
)
from agent.transcript_agent import ClaudeTranscriptAgent, AGENT_SYSTEM_PROMPT
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


@pytest.mark.anyio
async def test_agent_sdk_tool_registration_and_handler():
    """
    Test that make_sdk_search_tool produces an official Claude Agent SDK SdkMcpTool
    with correct name, input schema, and functional handler.
    """
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=True,
        context_text="Elena Verna on B2B product-led growth loops.",
        citations=[
            Citation(
                guest="Elena Verna",
                episode_title="B2B Growth",
                excerpt="PLG is not a go-to-market strategy, it is a company strategy.",
                relevance_score=0.94,
            )
        ],
        raw_chunks=[],
    )

    collector = []
    sdk_tool = make_sdk_search_tool(mock_retriever, citation_collector=collector)

    assert isinstance(sdk_tool, SdkMcpTool)
    assert sdk_tool.name == "search_lenny_transcripts"
    assert "Search the Lenny's Podcast archives" in sdk_tool.description
    assert sdk_tool.input_schema == SearchToolInput

    # Execute tool handler directly
    handler_result = await sdk_tool.handler({"query": "product-led growth", "top_k": 3})
    assert "content" in handler_result
    assert handler_result["is_error"] is False
    assert len(collector) == 1
    assert collector[0].guest == "Elena Verna"

    parsed_payload = json.loads(handler_result["content"][0]["text"])
    assert parsed_payload["status"] == "success"
    assert parsed_payload["has_sufficient_context"] is True


def test_agent_build_sdk_options():
    """
    Test that ClaudeTranscriptAgent constructs valid ClaudeAgentOptions
    with the official SDK MCP server and tool bindings.
    """
    mock_retriever = MagicMock()
    agent = ClaudeTranscriptAgent(
        retriever=mock_retriever,
        api_key="sk-ant-test-key-12345",
        model_name="claude-3-5-sonnet-20241022",
    )

    citations = []
    options = agent.build_sdk_options(citations)

    assert isinstance(options, ClaudeAgentOptions)
    assert options.model == "claude-3-5-sonnet-20241022"
    assert options.system_prompt == AGENT_SYSTEM_PROMPT
    assert "lenny-tools" in options.mcp_servers
    assert options.allowed_tools == ["search_lenny_transcripts"]
    assert options.permission_mode == "bypassPermissions"
    assert options.env.get("ANTHROPIC_API_KEY") == "sk-ant-test-key-12345"


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
    Test the complete autonomous agent reasoning cycle using Claude Agent SDK:
    1. Agent invokes SDK search tool on podcast transcripts.
    2. SDK query streams grounded executive synthesis.
    3. Citations and provider metrics are accurately captured.
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

    async def mock_sdk_query(prompt, options):
        # Simulate Claude Agent invoking the in-process SDK MCP tool
        assert agent._last_sdk_tool is not None
        tool_res = await agent._last_sdk_tool.handler({"query": "positioning frameworks", "top_k": 4})
        assert "April Dunford" in tool_res["content"][0]["text"]

        yield AssistantMessage(
            content=[
                TextBlock(
                    text="According to **April Dunford**, positioning starts with your differentiated capability."
                )
            ],
            model="claude-3-5-sonnet-20241022",
            usage={"output_tokens": 50},
        )
        yield ResultMessage(
            subtype="success",
            duration_ms=450,
            duration_api_ms=400,
            is_error=False,
            num_turns=1,
            session_id="test-session-001",
            result="According to **April Dunford**, positioning starts with your differentiated capability.",
        )

    with patch("agent.transcript_agent.sdk_query", side_effect=mock_sdk_query):
        agent_result = await agent.run(prompt="How should I position my product?")

        assert agent_result.provider == "anthropic-agent"
        assert "April Dunford" in agent_result.content
        assert len(agent_result.citations) == 1
        assert agent_result.citations[0].guest == "April Dunford"
        assert agent_result.has_sufficient_context is True
        assert agent_result.eval_count == 50


@pytest.mark.anyio
async def test_agent_refusal_when_insufficient_context():
    """
    Test that when podcast transcripts contain insufficient context,
    the agent returns has_sufficient_context=False and provides the required refusal.
    """
    mock_retriever = MagicMock()
    mock_retriever.retrieve.return_value = RetrievalResult(
        has_sufficient_context=False,
        context_text="",
        citations=[],
        raw_chunks=[],
    )

    agent = ClaudeTranscriptAgent(
        retriever=mock_retriever,
        api_key="sk-ant-mock-key-12345",
        model_name="claude-3-5-sonnet-20241022",
    )

    refusal_text = (
        "Based on the verified podcast transcripts currently indexed in the knowledge base, "
        "there is insufficient evidence to answer this question."
    )

    async def mock_sdk_query(prompt, options):
        assert agent._last_sdk_tool is not None
        await agent._last_sdk_tool.handler({"query": "quantum gravity", "top_k": 4})
        yield AssistantMessage(
            content=[TextBlock(text=refusal_text)],
            model="claude-3-5-sonnet-20241022",
            usage={"output_tokens": 25},
        )
        yield ResultMessage(
            subtype="success",
            duration_ms=300,
            duration_api_ms=280,
            is_error=False,
            num_turns=1,
            session_id="test-session-002",
            result=refusal_text,
        )

    with patch("agent.transcript_agent.sdk_query", side_effect=mock_sdk_query):
        agent_result = await agent.run(prompt="Explain quantum gravity in detail.")

        assert agent_result.provider == "anthropic-agent"
        assert agent_result.has_sufficient_context is False
        assert len(agent_result.citations) == 0
        assert "insufficient evidence" in agent_result.content.lower()


@pytest.mark.anyio
async def test_agent_sdk_auth_error_raises_401():
    """
    Test that runtime authentication errors from Claude Agent SDK
    are mapped to HTTP 401 Unauthorized.
    """
    mock_retriever = MagicMock()
    agent = ClaudeTranscriptAgent(
        retriever=mock_retriever,
        api_key="sk-ant-mock-key-12345",
        model_name="claude-3-5-sonnet-20241022",
    )

    async def mock_auth_fail(prompt, options):
        raise claude_agent_sdk.ResultError(
            "Claude Code returned an error result: Not logged in • Please run /login"
        )
        yield  # Make it an async generator

    with patch("agent.transcript_agent.sdk_query", side_effect=mock_auth_fail):
        with pytest.raises(HTTPException) as exc_info:
            await agent.run(prompt="How do I calculate churn?")
        assert exc_info.value.status_code == 401
        assert "authentication error" in exc_info.value.detail.lower()


def test_api_chat_with_agent_mode():
    """
    Test /api/chat with use_agent=True executes ClaudeTranscriptAgent via Claude Agent SDK and returns 200.
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

    async def mock_sdk_query(prompt, options):
        # Trigger tool handler to accumulate citations
        if ClaudeTranscriptAgent._latest_instance and ClaudeTranscriptAgent._latest_instance._last_sdk_tool:
            await ClaudeTranscriptAgent._latest_instance._last_sdk_tool.handler({"query": "growth loops", "top_k": 4})
        yield AssistantMessage(
            content=[
                TextBlock(
                    text="Brian Balfour explains that growth loops compound, whereas traditional funnels drop off."
                )
            ],
            model="claude-3-5-sonnet-20241022",
            usage={"output_tokens": 35},
        )
        yield ResultMessage(
            subtype="success",
            duration_ms=400,
            duration_api_ms=350,
            is_error=False,
            num_turns=1,
            session_id="test-chat-session",
            result="Brian Balfour explains that growth loops compound.",
        )

    with patch("agent.transcript_agent.is_valid_anthropic_key", return_value=True):
        with patch.object(ClaudeTranscriptAgent, "_ensure_api_key", return_value="sk-ant-test"):
            with patch("agent.transcript_agent.sdk_query", side_effect=mock_sdk_query):
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
