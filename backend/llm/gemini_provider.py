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
import random
import asyncio
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

# Bounded retry configuration for transient 503/429 errors
DEFAULT_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
DEFAULT_RETRY_DELAY = float(os.getenv("GEMINI_RETRY_DELAY", "1.0"))
MAX_RETRY_DELAY = float(os.getenv("GEMINI_MAX_RETRY_DELAY", "8.0"))


def parse_retry_after(header_val: Optional[str], default_delay: float, max_delay: float = MAX_RETRY_DELAY) -> float:
    """
    Parses Retry-After header value in seconds, bounded by max_delay.
    """
    if not header_val:
        return default_delay
    try:
        val = float(header_val.strip())
        return min(max(val, 0.5), max_delay)
    except (ValueError, TypeError):
        return default_delay


def extract_gemini_error_message(response_text: str) -> str:
    """
    Safely extracts a clean error message from Gemini JSON or returns truncated text.
    """
    if not response_text:
        return "Unknown error"
    try:
        data = json.loads(response_text)
        if isinstance(data, dict):
            err = data.get("error", {})
            if isinstance(err, dict) and "message" in err:
                return str(err["message"])
    except Exception:
        pass
    return response_text[:500]

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
    """
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
        self._api_key = api_key
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
        key = self._api_key if self._api_key is not None else os.getenv("GEMINI_API_KEY")
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

        eff_max_tokens = max_tokens if max_tokens is not None else 3500
        effective_timeout = timeout if timeout is not None else 120.0

        url = f"{GEMINI_API_BASE}/models/{self._model_name}:generateContent"

        generation_config: Dict[str, Any] = {
            "maxOutputTokens": eff_max_tokens,
            "temperature": 0.7,
        }
        if "2.5" in self._model_name.lower() or "thinking" in self._model_name.lower():
            # For Gemini 2.5 models, thinking tokens consume maxOutputTokens budget by default.
            # Setting thinkingBudget=0 ensures 100% of the token allowance is allocated
            # to user-facing response content without early truncation.
            generation_config["thinkingConfig"] = {"thinkingBudget": 0}

        payload: Dict[str, Any] = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_instruction}],
            },
            "generationConfig": generation_config,
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

        attempt = 0
        while attempt <= DEFAULT_MAX_RETRIES:
            try:
                start_time = time.perf_counter()
                async with httpx.AsyncClient(timeout=effective_timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)

                elapsed_sec = time.perf_counter() - start_time

                # 1. Detect billing-required errors immediately (non-retryable)
                if response.status_code != 200:
                    error_body = response.text
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

                # 2. Handle retryable transient errors: HTTP 503, 429, or 5xx
                if response.status_code in (503, 429) or (response.status_code >= 500 and response.status_code != 501):
                    clean_msg = extract_gemini_error_message(response.text)
                    if attempt < DEFAULT_MAX_RETRIES:
                        retry_after_header = response.headers.get("Retry-After") or response.headers.get("retry-after")
                        calc_delay = min(DEFAULT_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                        delay = parse_retry_after(retry_after_header, calc_delay)
                        jitter = random.uniform(0.1, 0.4)
                        actual_delay = min(delay + jitter, MAX_RETRY_DELAY)

                        logger.warning(
                            "Gemini API returned HTTP %d (%s). Retrying in %.2fs (attempt %d/%d)...",
                            response.status_code,
                            clean_msg[:120],
                            actual_delay,
                            attempt + 1,
                            DEFAULT_MAX_RETRIES,
                        )
                        await asyncio.sleep(actual_delay)
                        attempt += 1
                        continue
                    else:
                        logger.error(
                            "Gemini HTTP %d retries exhausted after %d attempts: %s",
                            response.status_code,
                            DEFAULT_MAX_RETRIES + 1,
                            clean_msg,
                        )
                        if response.status_code == 429:
                            raise HTTPException(
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Gemini API rate limit exceeded (HTTP 429): {clean_msg}. Please try again shortly.",
                            )
                        elif response.status_code == 503:
                            raise HTTPException(
                                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail=f"Gemini API error (HTTP 503): {clean_msg}. Spikes in demand are usually temporary. Please try again later.",
                            )
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=f"Gemini API error (HTTP {response.status_code}): {clean_msg}",
                            )

                # 3. Handle non-retryable client errors
                if response.status_code in (401, 403):
                    logger.error("Gemini authentication failed (HTTP %d): %s", response.status_code, response.text)
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Gemini authentication error: Invalid or expired API key (HTTP {response.status_code}).",
                    )
                elif response.status_code != 200:
                    clean_msg = extract_gemini_error_message(response.text)
                    logger.error("Gemini HTTP %d error after %.1fs: %s", response.status_code, elapsed_sec, response.text)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Gemini API error (HTTP {response.status_code}): {clean_msg}",
                    )

                # 4. Successful 200 OK response processing
                resp_data = response.json()
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
                if attempt < DEFAULT_MAX_RETRIES:
                    calc_delay = min(DEFAULT_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                    logger.warning(
                        "Failed connecting to Gemini API. Retrying in %.2fs (attempt %d/%d)...",
                        calc_delay,
                        attempt + 1,
                        DEFAULT_MAX_RETRIES,
                    )
                    await asyncio.sleep(calc_delay)
                    attempt += 1
                    continue
                logger.error("Failed connecting to Gemini API at %s after %d attempts", GEMINI_API_BASE, DEFAULT_MAX_RETRIES + 1)
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

        generation_config: Dict[str, Any] = {
            "maxOutputTokens": eff_max_tokens,
            "temperature": 0.7,
        }
        if "2.5" in self._model_name.lower() or "thinking" in self._model_name.lower():
            generation_config["thinkingConfig"] = {"thinkingBudget": 0}

        payload: Dict[str, Any] = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_instruction}],
            },
            "generationConfig": generation_config,
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

        attempt = 0
        while attempt <= DEFAULT_MAX_RETRIES:
            try:
                async with httpx.AsyncClient(timeout=effective_timeout) as client:
                    async with client.stream("POST", url, headers=headers, json=payload) as response:
                        if response.status_code != 200:
                            body_err = await response.aread()
                            error_text = body_err.decode(errors="replace")
                            if "billing" in error_text.lower() or "BILLING" in error_text:
                                raise HTTPException(
                                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                                    detail="Gemini API requires billing for this request.",
                                )

                            clean_msg = extract_gemini_error_message(error_text)

                            if response.status_code in (503, 429) or (response.status_code >= 500 and response.status_code != 501):
                                if attempt < DEFAULT_MAX_RETRIES:
                                    retry_after_header = response.headers.get("Retry-After") or response.headers.get("retry-after")
                                    calc_delay = min(DEFAULT_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                                    delay = parse_retry_after(retry_after_header, calc_delay)
                                    actual_delay = min(delay + random.uniform(0.1, 0.4), MAX_RETRY_DELAY)

                                    logger.warning(
                                        "Gemini stream returned HTTP %d (%s). Retrying in %.2fs (attempt %d/%d)...",
                                        response.status_code,
                                        clean_msg[:120],
                                        actual_delay,
                                        attempt + 1,
                                        DEFAULT_MAX_RETRIES,
                                    )
                                    await asyncio.sleep(actual_delay)
                                    attempt += 1
                                    continue
                                else:
                                    if response.status_code == 429:
                                        raise HTTPException(
                                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                            detail=f"Gemini API rate limit exceeded: {clean_msg}",
                                        )
                                    elif response.status_code == 503:
                                        raise HTTPException(
                                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                            detail=f"Gemini API error (HTTP 503): {clean_msg}. Spikes in demand are usually temporary. Please try again later.",
                                        )
                                    else:
                                        raise HTTPException(
                                            status_code=status.HTTP_502_BAD_GATEWAY,
                                            detail=f"Gemini stream error (HTTP {response.status_code}): {clean_msg}",
                                        )

                            if response.status_code in (401, 403):
                                raise HTTPException(
                                    status_code=status.HTTP_401_UNAUTHORIZED,
                                    detail=f"Gemini authentication error (HTTP {response.status_code}).",
                                )
                            raise HTTPException(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=f"Gemini stream error (HTTP {response.status_code}): {clean_msg}",
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

                    break  # Stream succeeded, exit retry loop

            except httpx.ConnectError:
                if attempt < DEFAULT_MAX_RETRIES:
                    calc_delay = min(DEFAULT_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                    logger.warning(
                        "Failed connecting to Gemini stream. Retrying in %.2fs (attempt %d/%d)...",
                        calc_delay,
                        attempt + 1,
                        DEFAULT_MAX_RETRIES,
                    )
                    await asyncio.sleep(calc_delay)
                    attempt += 1
                    continue
                logger.error("Failed connecting to Gemini API during streaming after %d attempts", DEFAULT_MAX_RETRIES + 1)
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

    async def check_health(self) -> Dict[str, Any]:
        """
        Verify Gemini provider configuration status without making costly API calls.
        """
        key = self._api_key if self._api_key is not None else os.getenv("GEMINI_API_KEY")
        configured = is_valid_gemini_key(key)
        return {
            "provider": "gemini",
            "connected": configured,
            "model": self._model_name,
            "is_cloud": True,
            "api_key_configured": configured,
            "error": None if configured else "GEMINI_API_KEY is not configured.",
        }
