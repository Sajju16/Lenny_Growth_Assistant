"""
Google Gemini cloud LLM provider for Lenny Growth Assistant.

Uses the Google Generative Language REST API (generativelanguage.googleapis.com)
via httpx for async HTTP requests. Supports both single-shot generation and
true SSE streaming without requiring the google-genai SDK.

Authentication: GEMINI_API_KEY environment variable (Google AI Studio API key).
Free tier: No billing or payment method required.
"""

import os
import json
import time
import logging
from typing import List, Dict, Any, Optional

import httpx
from fastapi import HTTPException, status

from rag.retriever import Citation
from .base import BaseLLMProvider, ProviderResponse, GROUNDED_SYSTEM_PROMPT

logger = logging.getLogger("lenny-growth-backend.llm.gemini")

# Default model: Gemini 2.5 Flash is broadly available on the free tier.
# Configurable via GEMINI_MODEL environment variable.
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Placeholder values that should not be treated as valid API keys
_PLACEHOLDER_KEYS = frozenset({
    "your_gemini_api_key_here",
    "placeholder",
    "none",
    "your-api-key",
    "aistudio-xxx",
})


def is_valid_gemini_key(api_key: Optional[str] = None) -> bool:
    """
    Checks whether a non-empty, non-placeholder Gemini API key is configured.
    If api_key is None, inspects the GEMINI_API_KEY environment variable.
    """
    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return False
    key = api_key.strip()
    if not key:
        return False
    if key.lower() in _PLACEHOLDER_KEYS or key.startswith("your_"):
        return False
    return True


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini cloud LLM provider using the Generative Language REST API.
    Requires GEMINI_API_KEY environment variable (from Google AI Studio).
    No billing or payment method required for free-tier usage.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._model_name = model_name or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_cloud(self) -> bool:
        return True

    def _ensure_api_key(self) -> str:
        """
        Validates API key existence. Raises actionable HTTP 400 if missing or invalid.
        """
        key = self._api_key or os.getenv("GEMINI_API_KEY")
        if not is_valid_gemini_key(key):
            logger.error("Gemini requested but GEMINI_API_KEY is not configured.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Gemini API key is not configured. Set GEMINI_API_KEY in your .env file "
                    "(obtain a free key from https://aistudio.google.com/apikey), "
                    "or switch to local inference with LLM_PROVIDER=ollama."
                ),
            )
        return key.strip()

    def _build_contents(
        self,
        prompt: str,
        history: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        Converts the chat history + current prompt into the Gemini
        contents format: [{"role": "user"|"model", "parts": [{"text": ...}]}]
        """
        contents = []
        for item in history:
            role = item.get("role", "user")
            # Gemini uses "model" instead of "assistant"
            if role == "assistant":
                role = "model"
            if role in ("user", "model"):
                contents.append({
                    "role": role,
                    "parts": [{"text": item.get("content", "")}],
                })
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}],
        })
        return contents

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
                provider="gemini",
                citations=[],
                has_sufficient_context=False,
            )

        # Build system instruction and contents
        system_instruction = system_prompt or GROUNDED_SYSTEM_PROMPT
        if context_text:
            system_instruction += f"\n\n--- RELEVANT TRANSCRIPT EVIDENCE ---\n{context_text}\n--- END OF EVIDENCE ---"

        contents = self._build_contents(prompt, history)

        eff_max_tokens = max_tokens if max_tokens is not None else 2500
        effective_timeout = timeout if timeout is not None else 120.0

        url = f"{GEMINI_API_BASE}/models/{self._model_name}:generateContent"

        payload: Dict[str, Any] = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_instruction}],
            },
            "generationConfig": {
                "maxOutputTokens": eff_max_tokens,
                "temperature": 0.7,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        start_time = time.perf_counter()
        logger.info(
            "Invoking Gemini generateContent [model=%s, timeout=%.1fs, prompt_chars=%d]",
            self._model_name,
            effective_timeout,
            len(prompt),
        )

        try:
            async with httpx.AsyncClient(timeout=effective_timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

            elapsed_sec = time.perf_counter() - start_time

            # Handle specific HTTP error codes
            if response.status_code == 401 or response.status_code == 403:
                logger.error("Gemini authentication failed (HTTP %d): %s", response.status_code, response.text)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Gemini authentication error: Invalid or expired API key (HTTP {response.status_code}).",
                )
            elif response.status_code == 429:
                logger.error("Gemini rate limit exceeded: %s", response.text)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Gemini API rate limit exceeded. Please try again shortly.",
                )
            elif response.status_code != 200:
                error_body = response.text
                # Detect billing-required errors
                if "billing" in error_body.lower() or "BILLING" in error_body:
                    logger.error("Gemini billing required: %s", error_body)
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail=(
                            "Gemini API requires billing to be enabled for this request. "
                            "This project uses only the free tier. Switch to LLM_PROVIDER=ollama "
                            "or verify your Google AI Studio quota."
                        ),
                    )
                logger.error("Gemini HTTP %d error after %.1fs: %s", response.status_code, elapsed_sec, error_body)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Gemini API error (HTTP {response.status_code}): {error_body[:500]}",
                )

            resp_data = response.json()

            # Extract generated content from candidates
            candidates = resp_data.get("candidates", [])
            if not candidates:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Gemini returned no candidates in response.",
                )

            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts).strip()

            if not content:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Gemini returned an empty response.",
                )

            # Extract usage metadata
            usage = resp_data.get("usageMetadata", {})
            output_tokens = usage.get("candidatesTokenCount")
            input_tokens = usage.get("promptTokenCount")

            logger.info(
                "Gemini completed in %.1fs (input_tokens=%s, output_tokens=%s)",
                elapsed_sec,
                input_tokens,
                output_tokens,
            )

            return ProviderResponse(
                content=content,
                model=self._model_name,
                provider="gemini",
                citations=citations,
                has_sufficient_context=True,
                eval_count=output_tokens,
                metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "elapsed_sec": round(elapsed_sec, 2),
                    "finish_reason": candidates[0].get("finishReason"),
                },
            )

        except httpx.ConnectError:
            logger.error("Failed connecting to Gemini API at %s", GEMINI_API_BASE)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to connect to Google Gemini API. Check your network connection.",
            )
        except httpx.TimeoutException:
            logger.error("Gemini request timed out after %.1fs", effective_timeout)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Gemini API request timed out after {effective_timeout:.0f}s.",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unexpected error communicating with Gemini: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Gemini provider execution error: {str(exc)}",
            )

    async def stream_response(
        self,
        prompt: str,
        history: List[Dict[str, str]],
        context_text: str = "",
        citations: Optional[List[Citation]] = None,
        has_sufficient_context: bool = True,
        timeout: Optional[float] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        True SSE streaming via Gemini streamGenerateContent endpoint.
        Yields chunk dictionaries compatible with the existing streaming architecture.
        """
        citations = citations or []
        api_key = self._ensure_api_key()
        effective_timeout = timeout if timeout is not None else 120.0

        # If RAG determined evidence is insufficient, return grounded refusal immediately
        if not has_sufficient_context:
            refusal_response = (
                "Based on the verified podcast transcripts currently indexed in the knowledge base, "
                "there is insufficient evidence to answer this question. Please ask about topics covered "
                "in the indexed episodes (e.g. founder-led sales, positioning, PMF benchmarks, pricing architecture, or PLG loops)."
            )
            yield {"delta": refusal_response}
            yield {
                "done": True,
                "response": refusal_response,
                "model": self._model_name,
                "provider": "gemini",
                "citations": [],
                "has_sufficient_context": False,
                "eval_count": len(refusal_response.split()),
                "metadata": {"ttft_sec": 0.0, "elapsed_sec": 0.0},
            }
            return

        # Build system instruction and contents
        system_instruction = system_prompt or GROUNDED_SYSTEM_PROMPT
        if context_text:
            system_instruction += f"\n\n--- RELEVANT TRANSCRIPT EVIDENCE ---\n{context_text}\n--- END OF EVIDENCE ---"

        contents = self._build_contents(prompt, history)

        eff_max_tokens = max_tokens if max_tokens is not None else 384

        url = f"{GEMINI_API_BASE}/models/{self._model_name}:streamGenerateContent?alt=sse"

        payload: Dict[str, Any] = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_instruction}],
            },
            "generationConfig": {
                "maxOutputTokens": eff_max_tokens,
                "temperature": 0.7,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        start_time = time.perf_counter()
        first_token_time = None
        chunks: List[str] = []
        output_tokens = None
        input_tokens = None
        finish_reason = None

        logger.info(
            "Streaming Gemini streamGenerateContent [model=%s, timeout=%.1fs, max_tokens=%d]",
            self._model_name,
            effective_timeout,
            eff_max_tokens,
        )

        try:
            async with httpx.AsyncClient(timeout=effective_timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code == 401 or response.status_code == 403:
                        body_err = await response.aread()
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Gemini authentication error (HTTP {response.status_code}).",
                        )
                    elif response.status_code == 429:
                        body_err = await response.aread()
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Gemini API rate limit exceeded.",
                        )
                    elif response.status_code != 200:
                        body_err = await response.aread()
                        error_text = body_err.decode(errors="replace")
                        if "billing" in error_text.lower():
                            raise HTTPException(
                                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                                detail="Gemini API requires billing for this request.",
                            )
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Gemini stream error (HTTP {response.status_code}): {error_text[:500]}",
                        )

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        raw_json = line[6:]  # Strip "data: " prefix
                        if not raw_json.strip():
                            continue
                        try:
                            data = json.loads(raw_json)
                        except json.JSONDecodeError:
                            continue

                        # Extract text from candidates
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            token = "".join(p.get("text", "") for p in parts)
                            if token:
                                if first_token_time is None:
                                    first_token_time = time.perf_counter() - start_time
                                chunks.append(token)
                                yield {"delta": token}

                            # Check for finish reason
                            fr = candidates[0].get("finishReason")
                            if fr:
                                finish_reason = fr

                        # Extract usage metadata from the final chunk
                        usage = data.get("usageMetadata", {})
                        if usage:
                            output_tokens = usage.get("candidatesTokenCount", output_tokens)
                            input_tokens = usage.get("promptTokenCount", input_tokens)

            elapsed_sec = time.perf_counter() - start_time
            full_content = "".join(chunks).strip()

            if not full_content:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Gemini returned an empty streaming response.",
                )

            eval_count = output_tokens or len(full_content.split())
            ttft = first_token_time if first_token_time is not None else elapsed_sec

            logger.info(
                "Gemini stream completed in %.2fs (TTFT=%.2fs, tokens=%s)",
                elapsed_sec,
                ttft,
                eval_count,
            )

            yield {
                "done": True,
                "response": full_content,
                "model": self._model_name,
                "provider": "gemini",
                "citations": citations,
                "has_sufficient_context": True,
                "eval_count": eval_count,
                "metadata": {
                    "elapsed_sec": round(elapsed_sec, 2),
                    "ttft_sec": round(ttft, 3),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "finish_reason": finish_reason,
                },
            }

        except httpx.ConnectError:
            logger.error("Failed connecting to Gemini API during streaming")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to connect to Google Gemini API.",
            )
        except httpx.TimeoutException:
            logger.error("Gemini streaming timed out after %.1fs", effective_timeout)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Gemini streaming request timed out after {effective_timeout:.0f}s.",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in Gemini streaming: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Gemini stream execution failed: {str(exc)}",
            )

    async def check_health(self) -> Dict[str, Any]:
        """
        Verify Gemini provider configuration status without making costly API calls.
        """
        key = self._api_key or os.getenv("GEMINI_API_KEY")
        configured = is_valid_gemini_key(key)
        return {
            "provider": "gemini",
            "connected": configured,
            "model": self._model_name,
            "is_cloud": True,
            "api_key_configured": configured,
            "error": None if configured else "GEMINI_API_KEY is not configured.",
        }
