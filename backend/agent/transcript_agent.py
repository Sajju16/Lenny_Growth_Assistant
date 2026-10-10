import os
import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from rag.retriever import KnowledgeRetriever, Citation
from llm.base import ProviderResponse, GROUNDED_SYSTEM_PROMPT
from llm.anthropic_provider import is_valid_anthropic_key
from .tools import SEARCH_LENNY_TRANSCRIPTS_TOOL_SCHEMA, execute_search_transcripts

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
    Autonomous Anthropic Claude Agent equipped with the strict `search_lenny_transcripts` retrieval tool.
    Executes multi-step reasoning: User Query -> Tool Call -> Transcript Retrieval -> Grounded Synthesis.
    """

    def __init__(
        self,
        retriever: KnowledgeRetriever,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.retriever = retriever
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model_name = model_name or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

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

    async def run(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        max_tool_turns: int = 3,
    ) -> ProviderResponse:
        """
        Executes the agentic loop with tool calls against the Lenny transcript retriever.
        """
        key = self._ensure_api_key()
        history = history or []

        try:
            import anthropic
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Anthropic SDK is not installed.",
            )

        client = anthropic.AsyncAnthropic(api_key=key)

        messages = []
        for item in history:
            role = item.get("role")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": item.get("content", "")})

        messages.append({"role": "user", "content": prompt})

        collected_citations: List[Citation] = []
        has_sufficient_context = True
        total_eval_tokens = 0

        current_turn = 0
        while current_turn < max_tool_turns:
            current_turn += 1

            try:
                response = await client.messages.create(
                    model=self.model_name,
                    max_tokens=1500,
                    system=AGENT_SYSTEM_PROMPT,
                    messages=messages,
                    tools=[SEARCH_LENNY_TRANSCRIPTS_TOOL_SCHEMA],
                )
            except anthropic.AuthenticationError as auth_err:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Anthropic authentication error: {str(auth_err)}",
                )
            except anthropic.RateLimitError:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Anthropic rate limit exceeded.",
                )
            except anthropic.APIStatusError as status_err:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Anthropic API error (HTTP {status_err.status_code}): {status_err.message}",
                )

            usage = getattr(response, "usage", None)
            if usage:
                total_eval_tokens += getattr(usage, "output_tokens", 0)

            # Check if Claude decided to invoke a tool
            tool_calls = [b for b in response.content if getattr(b, "type", None) == "tool_use"]

            if not tool_calls:
                # Agent completed generation without requesting further tools
                text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
                final_content = "\n".join(text_blocks).strip()
                return ProviderResponse(
                    content=final_content,
                    model=response.model or self.model_name,
                    provider="anthropic-agent",
                    citations=collected_citations,
                    has_sufficient_context=has_sufficient_context,
                    eval_count=total_eval_tokens,
                    metadata={"agent_mode": True, "turns": current_turn},
                )

            # Process tool calls
            # 1. Append assistant response containing tool_use blocks
            messages.append({"role": "assistant", "content": response.content})

            # 2. Execute each tool call within strict boundaries
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.name
                tool_id = tool_call.id
                tool_input = tool_call.input or {}

                if tool_name == "search_lenny_transcripts":
                    search_query = tool_input.get("query", prompt)
                    top_k = tool_input.get("top_k", 4)
                    result_data = execute_search_transcripts(self.retriever, query=search_query, top_k=top_k)

                    # Accumulate citations
                    for c_dict in result_data.get("citations", []):
                        citation_obj = Citation(**c_dict)
                        if not any(c.excerpt == citation_obj.excerpt for c in collected_citations):
                            collected_citations.append(citation_obj)

                    if not result_data.get("has_sufficient_context", True):
                        has_sufficient_context = False

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(result_data),
                    })
                else:
                    # Boundary enforcement: Reject unauthorized tool requests
                    logger.warning("Agent attempted unauthorized tool execution: %s", tool_name)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps({
                            "error": f"Tool '{tool_name}' is not authorized. Only 'search_lenny_transcripts' is permitted."
                        }),
                        "is_error": True,
                    })

            messages.append({"role": "user", "content": tool_results})

        # Fallback if loop exceeded max turns
        return ProviderResponse(
            content="Agent reasoning cycle limit reached.",
            model=self.model_name,
            provider="anthropic-agent",
            citations=collected_citations,
            has_sufficient_context=has_sufficient_context,
            eval_count=total_eval_tokens,
        )
