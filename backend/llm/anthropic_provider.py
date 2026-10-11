import os
import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from rag.retriever import Citation
from .base import BaseLLMProvider, ProviderResponse, GROUNDED_SYSTEM_PROMPT

logger = logging.getLogger("lenny-growth-backend.llm.anthropic")

DEFAULT_ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")


def is_valid_anthropic_key(api_key: Optional[str]) -> bool:
    """
    Checks whether a non-empty, non-placeholder Anthropic API key is configured.
    """
    if not api_key:
        return False
    key = api_key.strip()
    if not key:
        return False
    # Check for placeholder values
    placeholders = [
        "your_anthropic_api_key_here",
        "placeholder",
        "none",
        "your-api-key",
        "sk-ant-api03-xxx",
    ]
    if key.lower() in placeholders or key.startswith("your_"):
        return False
    return True


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude cloud LLM provider using the official Anthropic Python SDK.
    Requires ANTHROPIC_API_KEY environment variable.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._model_name = model_name or os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_cloud(self) -> bool:
        return True

    def _ensure_api_key(self) -> str:
        """
        Validates API key existence. Raises actionable HTTP 400 if missing or invalid.
        Explicitly does NOT silently fall back to another provider.
        """
        key = self._api_key or os.getenv("ANTHROPIC_API_KEY")
        if not is_valid_anthropic_key(key):
            logger.error("Anthropic Claude requested but ANTHROPIC_API_KEY is not configured.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Anthropic API key is not configured. Set ANTHROPIC_API_KEY in your .env file "
                    "or environment variables, or switch back to local inference with LLM_PROVIDER=ollama."
                ),
            )
        return key.strip()

    async def generate_response(
        self,
        prompt: str,
        history: List[Dict[str, str]],
        context_text: str = "",
        citations: Optional[List[Citation]] = None,
        has_sufficient_context: bool = True,
        timeout: Optional[float] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        citations = citations or []
        api_key = self._ensure_api_key()

        # If RAG determined evidence is insufficient, return grounded refusal immediately
        if not has_sufficient_context:
            refusal_response = (
                "Based on the verified podcast transcripts currently indexed in the knowledge base, "
                "there is insufficient evidence to answer this question. Please ask about topics covered "
                "in the indexed episodes (e.g. founder-led sales, positioning, PMF benchmarks, pricing architecture, or PLG loops)."
            )
            return ProviderResponse(
                content=refusal_response,
                model=self._model_name,
                provider="anthropic",
                citations=[],
                has_sufficient_context=False,
            )

        # Import anthropic SDK
        try:
            import anthropic
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The 'anthropic' Python SDK is not installed. Run 'pip install anthropic'.",
            )

        # Build prompt instructions and messages
        system_instruction = system_prompt or GROUNDED_SYSTEM_PROMPT
        if context_text:
            system_instruction += f"\n\n--- RELEVANT TRANSCRIPT EVIDENCE ---\n{context_text}\n--- END OF EVIDENCE ---"

        messages = []
        for item in history:
            role = item.get("role")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": item.get("content", "")})

        messages.append({"role": "user", "content": prompt})

        try:
            client = anthropic.AsyncAnthropic(api_key=api_key)
            eff_max_tokens = max_tokens if max_tokens is not None else 2500
            response = await client.messages.create(
                model=self._model_name,
                max_tokens=eff_max_tokens,
                system=system_instruction,
                messages=messages,
            )

            # Extract generated content
            text_blocks = [b.text for b in response.content if getattr(b, "type", None) == "text"]
            content = "\n".join(text_blocks).strip()

            if not content:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Anthropic Claude returned an empty response.",
                )

            usage = getattr(response, "usage", None)
            eval_count = getattr(usage, "output_tokens", None) if usage else None

            return ProviderResponse(
                content=content,
                model=response.model or self._model_name,
                provider="anthropic",
                citations=citations,
                has_sufficient_context=True,
                eval_count=eval_count,
                metadata={
                    "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
                    "output_tokens": eval_count,
                    "stop_reason": getattr(response, "stop_reason", None),
                },
            )

        except anthropic.AuthenticationError as auth_err:
            logger.error("Anthropic authentication failed: %s", auth_err)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Anthropic authentication error: Invalid API key provided ({str(auth_err)}).",
            )
        except anthropic.RateLimitError as rate_err:
            logger.error("Anthropic rate limit exceeded: %s", rate_err)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Anthropic rate limit exceeded. Please try again shortly.",
            )
        except anthropic.APIStatusError as status_err:
            logger.error("Anthropic API returned error %s: %s", status_err.status_code, status_err.message)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Anthropic API error (HTTP {status_err.status_code}): {status_err.message}",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unexpected error communicating with Anthropic: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Anthropic provider execution error: {str(exc)}",
            )

    async def check_health(self) -> Dict[str, Any]:
        """
        Verify Anthropic provider configuration status without making costly API calls.
        """
        key = self._api_key or os.getenv("ANTHROPIC_API_KEY")
        configured = is_valid_anthropic_key(key)
        return {
            "provider": "anthropic",
            "connected": configured,
            "model": self._model_name,
            "is_cloud": True,
            "api_key_configured": configured,
            "error": None if configured else "ANTHROPIC_API_KEY is not configured.",
        }
