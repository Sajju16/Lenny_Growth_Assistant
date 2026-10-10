import os
import logging
from typing import List, Dict, Any, Optional
import httpx
from fastapi import HTTPException, status

from rag.retriever import Citation
from .base import BaseLLMProvider, ProviderResponse, GROUNDED_SYSTEM_PROMPT

logger = logging.getLogger("lenny-growth-backend.llm.ollama")

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("DEFAULT_MODEL", "qwen2.5:3b")


class OllamaProvider(BaseLLMProvider):
    """
    Local Ollama LLM provider executing inference on the user's workstation.
    Default model: qwen2.5:3b.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: float = 120.0,
    ):
        self._base_url = base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)
        self._model_name = model_name or os.getenv("DEFAULT_MODEL", DEFAULT_OLLAMA_MODEL)
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_cloud(self) -> bool:
        return False

    async def generate_response(
        self,
        prompt: str,
        history: List[Dict[str, str]],
        context_text: str = "",
        citations: Optional[List[Citation]] = None,
        has_sufficient_context: bool = True,
    ) -> ProviderResponse:
        citations = citations or []

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
                provider="ollama",
                citations=[],
                has_sufficient_context=False,
            )

        # Build prompt messages
        system_instruction = GROUNDED_SYSTEM_PROMPT
        if context_text:
            system_instruction += f"\n\n--- RELEVANT TRANSCRIPT EVIDENCE ---\n{context_text}\n--- END OF EVIDENCE ---"

        messages = [{"role": "system", "content": system_instruction}]
        for item in history:
            messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model_name,
            "messages": messages,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )

            if response.status_code != 200:
                logger.error("Ollama HTTP %d error: %s", response.status_code, response.text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Ollama error (HTTP {response.status_code}): {response.text}",
                )

            resp_data = response.json()
            message_obj = resp_data.get("message", {})
            content = message_obj.get("content", "").strip()

            if not content:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Ollama returned an empty response.",
                )

            return ProviderResponse(
                content=content,
                model=resp_data.get("model", self._model_name),
                provider="ollama",
                citations=citations,
                has_sufficient_context=True,
                eval_count=resp_data.get("eval_count"),
                total_duration=resp_data.get("total_duration"),
                metadata={"total_duration": resp_data.get("total_duration")},
            )

        except httpx.ConnectError:
            logger.error("Failed connecting to Ollama at %s", self._base_url)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to connect to Ollama at {self._base_url}. Ensure Ollama is running.",
            )
        except httpx.TimeoutException:
            logger.error("Ollama timed out after %ss", self._timeout)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Ollama request timed out while generating grounded response.",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in OllamaProvider: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ollama provider execution failed: {str(exc)}",
            )

    async def check_health(self) -> Dict[str, Any]:
        """
        Verify Ollama connectivity and model availability.
        """
        health = {
            "provider": "ollama",
            "connected": False,
            "url": self._base_url,
            "model": self._model_name,
            "model_available": False,
            "available_models": [],
            "error": None,
        }
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    health["connected"] = True
                    health["available_models"] = models
                    health["model_available"] = any(self._model_name in m for m in models)
                else:
                    health["error"] = f"Ollama returned HTTP {resp.status_code}"
        except httpx.ConnectError:
            health["error"] = f"Could not connect to Ollama at {self._base_url}. Ensure Ollama is running."
        except Exception as exc:
            health["error"] = str(exc)

        return health
