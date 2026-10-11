import os
import logging
from typing import Optional
from fastapi import HTTPException, status

from .base import BaseLLMProvider
from .ollama_provider import OllamaProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider

logger = logging.getLogger("lenny-growth-backend.llm.factory")

SUPPORTED_PROVIDERS = ("ollama", "anthropic", "gemini")


def get_llm_provider(
    provider_name: Optional[str] = None,
    timeout: Optional[float] = None,
) -> BaseLLMProvider:
    """
    Factory resolving the requested or configured LLM provider.
    Priority:
    1. Explicit provider_name parameter
    2. LLM_PROVIDER environment variable
    3. Default: 'ollama'
    """
    selected = (provider_name or os.getenv("LLM_PROVIDER", "ollama")).strip().lower()

    if selected == "ollama":
        return OllamaProvider(timeout=timeout)
    elif selected == "anthropic":
        return AnthropicProvider()
    elif selected == "gemini":
        return GeminiProvider()
    else:
        logger.error("Unknown LLM provider requested: '%s'", selected)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported LLM provider '{selected}'. "
                f"Supported providers are: {', '.join(SUPPORTED_PROVIDERS)}."
            ),
        )
