import os
import time
import logging
from typing import List, Dict, Any, Optional
import httpx
from fastapi import HTTPException, status

from rag.retriever import Citation
from .base import BaseLLMProvider, ProviderResponse, GROUNDED_SYSTEM_PROMPT

logger = logging.getLogger("lenny-growth-backend.llm.ollama")

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("DEFAULT_MODEL", "qwen2.5:3b")
DEFAULT_CHAT_TIMEOUT = float(os.getenv("OLLAMA_CHAT_TIMEOUT", "180.0"))
DEFAULT_ESSAY_TIMEOUT = float(os.getenv("OLLAMA_ESSAY_TIMEOUT", "420.0"))


class OllamaProvider(BaseLLMProvider):
    """
    Local Ollama LLM provider executing inference on the user's workstation.
    Default model: qwen2.5:3b.
    Timeouts are explicitly bounded:
    - Default chat timeout: 180s (configurable via OLLAMA_CHAT_TIMEOUT)
    - Default essay timeout: 420s (configurable via OLLAMA_ESSAY_TIMEOUT)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._base_url = base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)
        self._model_name = model_name or os.getenv("DEFAULT_MODEL", DEFAULT_OLLAMA_MODEL)
        self._timeout = timeout if timeout is not None else float(os.getenv("OLLAMA_CHAT_TIMEOUT", "180.0"))

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
        timeout: Optional[float] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        citations = citations or []
        effective_timeout = timeout if timeout is not None else self._timeout

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
        system_instruction = system_prompt or GROUNDED_SYSTEM_PROMPT
        if context_text:
            system_instruction += f"\n\n--- RELEVANT TRANSCRIPT EVIDENCE ---\n{context_text}\n--- END OF EVIDENCE ---"

        messages = [{"role": "system", "content": system_instruction}]
        for item in history:
            messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})
        messages.append({"role": "user", "content": prompt})

        num_predict = max_tokens if max_tokens is not None else 2048
        options: Dict[str, Any] = {
            "num_predict": num_predict,
            "temperature": 0.7,
        }
        if repeat_penalty is not None:
            options["repeat_penalty"] = repeat_penalty

        payload = {
            "model": self._model_name,
            "messages": messages,
            "stream": False,
            "keep_alive": "30m",
            "options": options,
        }

        start_time = time.perf_counter()
        logger.info(
            "Invoking Ollama /api/chat [model=%s, timeout=%.1fs, prompt_chars=%d, context_chars=%d]",
            self._model_name,
            effective_timeout,
            len(prompt),
            len(context_text),
        )

        try:
            async with httpx.AsyncClient(timeout=effective_timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )

            elapsed_sec = time.perf_counter() - start_time

            if response.status_code != 200:
                logger.error("Ollama HTTP %d error after %.1fs: %s", response.status_code, elapsed_sec, response.text)
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

            eval_cnt = resp_data.get("eval_count") or len(content.split())
            speed_tps = (eval_cnt / elapsed_sec) if elapsed_sec > 0 else 0.0
            logger.info(
                "Ollama completed in %.1fs (%d tokens, %.2f tokens/s) [done_reason=%s]",
                elapsed_sec,
                eval_cnt,
                speed_tps,
                resp_data.get("done_reason", "stop"),
            )

            return ProviderResponse(
                content=content,
                model=resp_data.get("model", self._model_name),
                provider="ollama",
                citations=citations,
                has_sufficient_context=True,
                eval_count=resp_data.get("eval_count"),
                total_duration=resp_data.get("total_duration"),
                metadata={"total_duration": resp_data.get("total_duration"), "elapsed_sec": elapsed_sec},
            )

        except httpx.ConnectError:
            logger.error("Failed connecting to Ollama at %s", self._base_url)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to connect to Ollama at {self._base_url}. Ensure Ollama is running.",
            )
        except httpx.TimeoutException:
            logger.error("Ollama timed out after %.1fs (effective_timeout=%.1fs)", effective_timeout, effective_timeout)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=(
                    f"Ollama request timed out after {effective_timeout:.0f}s while generating response. "
                    "Local CPU inference on 2-core hardware requires significant time for long generations. "
                    "You can retry with a more focused query, configure OLLAMA_CHAT_TIMEOUT / OLLAMA_ESSAY_TIMEOUT, "
                    "or switch to the Anthropic Claude cloud provider for instant response times."
                ),
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in OllamaProvider: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ollama provider execution failed: {str(exc)}",
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
        Streams Ollama tokens in realtime. Enables immediate Time-To-First-Token
        for rapid user feedback instead of blocking for the full response duration.
        """
        citations = citations or []
        effective_timeout = timeout if timeout is not None else self._timeout

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
                "provider": "ollama",
                "citations": [],
                "has_sufficient_context": False,
                "eval_count": len(refusal_response.split()),
                "metadata": {"ttft_sec": 0.0, "elapsed_sec": 0.0},
            }
            return

        # Build prompt messages
        system_instruction = system_prompt or GROUNDED_SYSTEM_PROMPT
        if context_text:
            system_instruction += f"\n\n--- RELEVANT TRANSCRIPT EVIDENCE ---\n{context_text}\n--- END OF EVIDENCE ---"

        messages = [{"role": "system", "content": system_instruction}]
        for item in history:
            messages.append({"role": item.get("role", "user"), "content": item.get("content", "")})
        messages.append({"role": "user", "content": prompt})

        # Sensible token bound for streaming normal chat
        num_predict = max_tokens if max_tokens is not None else 384
        payload = {
            "model": self._model_name,
            "messages": messages,
            "stream": True,
            "keep_alive": "30m",
            "options": {
                "num_predict": num_predict,
                "temperature": 0.7,
            },
        }

        start_time = time.perf_counter()
        first_token_time = None
        chunks = []
        load_duration = None
        prompt_eval_count = None
        prompt_eval_duration = None
        eval_count = None
        eval_duration = None
        total_duration = None
        resp_model = self._model_name

        logger.info(
            "Streaming Ollama /api/chat [model=%s, timeout=%.1fs, num_predict=%d, context_chars=%d]",
            self._model_name,
            effective_timeout,
            num_predict,
            len(context_text),
        )

        try:
            import json
            async with httpx.AsyncClient(timeout=effective_timeout) as client:
                async with client.stream("POST", f"{self._base_url}/api/chat", json=payload) as response:
                    if response.status_code != 200:
                        body_err = await response.aread()
                        logger.error("Ollama HTTP %d error during stream: %s", response.status_code, body_err.decode())
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Ollama stream error (HTTP {response.status_code}): {body_err.decode()}",
                        )

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except Exception:
                            continue

                        token = data.get("message", {}).get("content", "")
                        if token:
                            if first_token_time is None:
                                first_token_time = time.perf_counter() - start_time
                            chunks.append(token)
                            yield {"delta": token}

                        if data.get("done"):
                            load_duration = data.get("load_duration")
                            prompt_eval_count = data.get("prompt_eval_count")
                            prompt_eval_duration = data.get("prompt_eval_duration")
                            eval_count = data.get("eval_count")
                            eval_duration = data.get("eval_duration")
                            total_duration = data.get("total_duration")
                            resp_model = data.get("model", resp_model)

            elapsed_sec = time.perf_counter() - start_time
            full_content = "".join(chunks).strip()
            if not full_content:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Ollama returned an empty response.",
                )

            eval_count = eval_count or len(full_content.split())
            ttft = first_token_time if first_token_time is not None else elapsed_sec
            gen_duration_sec = max(0.0, elapsed_sec - ttft) if first_token_time is not None else 0.0
            speed_tps = (eval_count / gen_duration_sec) if gen_duration_sec > 0.0 else 0.0

            # Convert nanoseconds to readable seconds safely
            def _ns_to_sec(ns):
                return round(ns / 1e9, 3) if isinstance(ns, (int, float)) and ns >= 0 else None

            load_sec = _ns_to_sec(load_duration)
            prompt_eval_sec = _ns_to_sec(prompt_eval_duration)
            eval_sec = _ns_to_sec(eval_duration)
            total_sec = _ns_to_sec(total_duration)

            logger.info(
                "Ollama stream completed in %.2fs (TTFT=%.2fs, gen=%.2fs, %d tokens, %.2f tokens/s) | "
                "Native metrics: load=%s, prompt_eval=%s (%s tokens), eval=%s (%s tokens), total=%s",
                elapsed_sec,
                ttft,
                gen_duration_sec,
                eval_count,
                speed_tps,
                f"{load_sec:.3f}s" if load_sec is not None else "N/A",
                f"{prompt_eval_sec:.3f}s" if prompt_eval_sec is not None else "N/A",
                prompt_eval_count if prompt_eval_count is not None else "N/A",
                f"{eval_sec:.3f}s" if eval_sec is not None else "N/A",
                eval_count if eval_count is not None else "N/A",
                f"{total_sec:.3f}s" if total_sec is not None else "N/A",
            )

            metadata_dict = {
                "total_duration": total_duration,
                "elapsed_sec": round(elapsed_sec, 2),
                "ttft_sec": round(ttft, 3),
                "gen_duration_sec": round(gen_duration_sec, 2),
                "eval_count": eval_count,
                "tps": round(speed_tps, 2),
            }
            if load_duration is not None:
                metadata_dict["load_duration"] = load_duration
                metadata_dict["load_sec"] = load_sec
            if prompt_eval_count is not None:
                metadata_dict["prompt_eval_count"] = prompt_eval_count
            if prompt_eval_duration is not None:
                metadata_dict["prompt_eval_duration"] = prompt_eval_duration
                metadata_dict["prompt_eval_sec"] = prompt_eval_sec
            if eval_duration is not None:
                metadata_dict["eval_duration"] = eval_duration
                metadata_dict["eval_sec"] = eval_sec

            yield {
                "done": True,
                "response": full_content,
                "model": resp_model,
                "provider": "ollama",
                "citations": citations,
                "has_sufficient_context": True,
                "eval_count": eval_count,
                "total_duration": total_duration,
                "load_duration": load_duration,
                "prompt_eval_count": prompt_eval_count,
                "prompt_eval_duration": prompt_eval_duration,
                "eval_duration": eval_duration,
                "metadata": metadata_dict,
            }

        except httpx.ConnectError:
            logger.error("Failed connecting to Ollama at %s", self._base_url)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to connect to Ollama at {self._base_url}. Ensure Ollama is running.",
            )
        except httpx.TimeoutException:
            logger.error("Ollama streaming timed out after %.1fs", effective_timeout)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=(
                    f"Ollama request timed out after {effective_timeout:.0f}s while generating response. "
                    "Local CPU inference on 2-core hardware requires significant time for long generations."
                ),
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in Ollama streaming: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ollama stream execution failed: {str(exc)}",
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
