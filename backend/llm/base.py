from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from rag.retriever import Citation


GROUNDED_SYSTEM_PROMPT = (
    "You are Lenny Growth Assistant, an executive product advisor answering strictly from "
    "verified Lenny's Podcast transcript excerpts.\n\n"
    "CRITICAL GROUNDING RULES:\n"
    "1. Support every claim with direct evidence from the supplied transcript excerpts. Do not fabricate quotations, guest advice, episode details, or citations.\n"
    "2. Distinguish direct guest recommendations from general inference. Clearly attribute specific insights to the named guest(s).\n"
    "3. If the excerpts do not contain sufficient evidence to support a requested claim, explicitly state: 'Based on the verified podcast transcripts currently indexed, there is insufficient evidence to answer this question.'\n"
    "4. Format your response with crisp executive structure, bold key concepts, and numbered takeaways."
)


class ProviderResponse(BaseModel):
    content: str
    model: str
    provider: str
    citations: List[Citation] = Field(default_factory=list)
    has_sufficient_context: bool = True
    eval_count: Optional[int] = None
    total_duration: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseLLMProvider(ABC):
    """
    Abstract base interface for LLM providers (Ollama, Anthropic Claude, Agent).
    Decouples generation logic from FastAPI routing.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the identifier of the provider (e.g. 'ollama', 'anthropic')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the active model name."""
        pass

    @property
    @abstractmethod
    def is_cloud(self) -> bool:
        """Returns True if the provider connects to a cloud API."""
        pass

    @abstractmethod
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
    ) -> ProviderResponse:
        """
        Generates a grounded response based on user prompt, history, and retrieved context.
        """
        pass

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
        Asynchronously streams tokens as they are generated.
        Yields chunk dictionaries:
        - {"delta": str} during token generation
        - {"done": True, "response": str, "citations": list, ...} upon completion.
        """
        resp = await self.generate_response(
            prompt=prompt,
            history=history,
            context_text=context_text,
            citations=citations,
            has_sufficient_context=has_sufficient_context,
            timeout=timeout,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
        yield {"delta": resp.content}
        yield {
            "done": True,
            "response": resp.content,
            "citations": resp.citations,
            "has_sufficient_context": resp.has_sufficient_context,
            "eval_count": resp.eval_count,
            "total_duration": resp.total_duration,
            "model": resp.model,
            "provider": resp.provider,
            "metadata": resp.metadata,
        }

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """
        Checks connectivity, model availability, and configuration status.
        """
        pass
