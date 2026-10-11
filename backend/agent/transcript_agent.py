import os
import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

import claude_agent_sdk
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SdkMcpTool,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query as sdk_query,
)

from rag.retriever import KnowledgeRetriever, Citation
from llm.base import ProviderResponse
from llm.anthropic_provider import is_valid_anthropic_key
from .tools import (
    SEARCH_LENNY_TRANSCRIPTS_TOOL_SCHEMA,
    make_sdk_search_tool,
    execute_search_transcripts,
)

logger = logging.getLogger("lenny-growth-backend.agent")

AGENT_SYSTEM_PROMPT = (
    "You are Lenny Growth Assistant, an autonomous executive product intelligence agent. "
    "You provide verified strategic growth frameworks, retention analysis, and product insights.\n\n"
    "CRITICAL AGENT DIRECTIVES:\n"
    "1. When answering product or growth strategy questions, you MUST invoke the `search_lenny_transcripts` "
    "tool to retrieve verified podcast evidence before delivering your synthesis.\n"
    "2. Base your final conclusions SOLELY on the excerpts returned by the tool.\n"
    "3. If the tool reports insufficient evidence (`has_sufficient_context=False`), you MUST explicitly state: "
    "'Based on the verified podcast transcripts currently indexed in the knowledge base, there is insufficient evidence to answer this question.'\n"
    "4. Explicitly cite and attribute insights to the named podcast guest(s) in your response.\n"
    "5. Format your executive response with clear headings, bold takeaways, and structured bullet points."
)


class ClaudeTranscriptAgent:
    """
    Autonomous Anthropic Claude Agent built on the official Claude Agent SDK (`claude-agent-sdk`).
    Integrates in-process SDK MCP tools with strict tool boundaries (`search_lenny_transcripts`).
    """

    _latest_instance: Optional["ClaudeTranscriptAgent"] = None

    def __init__(
        self,
        retriever: KnowledgeRetriever,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.retriever = retriever
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model_name = model_name or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self._last_sdk_tool = None
        ClaudeTranscriptAgent._latest_instance = self

    def _ensure_api_key(self) -> str:
        key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not is_valid_anthropic_key(key):
            logger.error("Claude Agent requested but ANTHROPIC_API_KEY is not configured.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Anthropic API key is not configured for Claude Agent execution. "
                    "Set ANTHROPIC_API_KEY in your .env file, or select LLM_PROVIDER=ollama for local inference."
                ),
            )
        return key.strip()

    def build_sdk_tool(self, citation_collector: Optional[List[Citation]] = None) -> SdkMcpTool[Any]:
        """
        Creates an official Claude Agent SDK tool (@claude_agent_sdk.tool)
        bound to the transcript knowledge retriever.
        """
        return make_sdk_search_tool(self.retriever, citation_collector=citation_collector)

    def build_sdk_options(self, collected_citations: List[Citation]) -> ClaudeAgentOptions:
        """
        Constructs ClaudeAgentOptions with in-process SDK MCP server configuration.
        """
        sdk_tool_obj = self.build_sdk_tool(citation_collector=collected_citations)
        self._last_sdk_tool = sdk_tool_obj
        server_config = create_sdk_mcp_server(name="lenny-tools", tools=[sdk_tool_obj])

        key = self.api_key or os.getenv("ANTHROPIC_API_KEY", "")
        env_vars = {"ANTHROPIC_API_KEY": key.strip()} if key else {}

        return ClaudeAgentOptions(
            model=self.model_name,
            system_prompt=AGENT_SYSTEM_PROMPT,
            mcp_servers={"lenny-tools": server_config},
            allowed_tools=["search_lenny_transcripts"],
            permission_mode="bypassPermissions",
            env=env_vars,
        )

    async def run(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        max_tool_turns: int = 3,
    ) -> ProviderResponse:
        """
        Executes the agent reasoning cycle using the official Claude Agent SDK (`claude_agent_sdk.query`).
        """
        key = self._ensure_api_key()
        history = history or []

        collected_citations: List[Citation] = []
        options = self.build_sdk_options(collected_citations)

        # Build prompt with conversational context if history is present
        full_prompt = prompt
        if history:
            history_lines = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in history[-4:]]
            full_prompt = "Previous conversation context:\n" + "\n".join(history_lines) + f"\n\nCurrent user request:\n{prompt}"

        final_text = ""
        total_eval_tokens = 0
        has_sufficient_context = True

        try:
            async for msg in sdk_query(prompt=full_prompt, options=options):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            final_text += block.text
                    if msg.usage:
                        total_eval_tokens += msg.usage.get("output_tokens", 0)
                    if msg.error:
                        if msg.error == "authentication_failed":
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Claude Agent SDK authentication failed. Verify ANTHROPIC_API_KEY.",
                            )
                        elif msg.error == "rate_limit":
                            raise HTTPException(
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="Claude Agent SDK rate limit exceeded.",
                            )
                elif isinstance(msg, ResultMessage):
                    if msg.result and not final_text:
                        final_text = msg.result
                    if msg.is_error and not final_text:
                        logger.warning("Claude Agent SDK ResultMessage indicated error: %s", msg.result)
        except HTTPException:
            raise
        except Exception as exc:
            exc_str = str(exc)
            if "Not logged in" in exc_str or "login" in exc_str or "authentication" in exc_str.lower():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Claude Agent SDK authentication error: {exc_str}",
                )
            elif "rate limit" in exc_str.lower():
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Claude Agent SDK rate limit exceeded: {exc_str}",
                )
            else:
                logger.error("Claude Agent SDK execution error: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Claude Agent SDK error: {exc_str}",
                )

        if not collected_citations:
            if "insufficient evidence" in final_text.lower():
                has_sufficient_context = False

        return ProviderResponse(
            content=final_text.strip(),
            model=self.model_name,
            provider="anthropic-agent",
            citations=collected_citations,
            has_sufficient_context=has_sufficient_context,
            eval_count=total_eval_tokens,
            metadata={"agent_mode": True, "sdk": "claude-agent-sdk"},
        )
