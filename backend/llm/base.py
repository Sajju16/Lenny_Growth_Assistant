from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from rag.retriever import Citation


GROUNDED_SYSTEM_PROMPT = (
    "You are Lenny Growth Assistant, an executive product intelligence advisor. "
    "Your objective is to answer the user's question strictly and accurately based on the "
    "verified transcript excerpts provided from Lenny's Podcast archives.\n\n"
    "CRITICAL GROUNDING INSTRUCTIONS:\n"
    "1. Base your response SOLELY on the transcript excerpts provided below. Do not guess or invent facts.\n"
    "2. If the provided excerpts do not contain enough relevant information to answer with confidence, "
    "you MUST explicitly state: 'Based on the verified podcast transcripts currently indexed, there is insufficient evidence to answer this question.'\n"
    "3. Directly cite and attribute advice, playbooks, and frameworks to the specific guest(s) named in the excerpts.\n"
    "4. Format your advice with crisp executive structure, bold key concepts, and numbered points."
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
    ) -> ProviderResponse:
        """
        Generates a grounded response based on user prompt, history, and retrieved context.
        """
        pass

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """
        Checks connectivity, model availability, and configuration status.
        """
        pass
