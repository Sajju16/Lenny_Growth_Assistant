import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from rag.retriever import KnowledgeRetriever, Citation

logger = logging.getLogger("lenny-growth-backend.agent.tools")

# Strict JSON Schema definition for Claude tool-calling
SEARCH_LENNY_TRANSCRIPTS_TOOL_SCHEMA = {
    "name": "search_lenny_transcripts",
    "description": (
        "Search the Lenny's Podcast archives for verified expert growth strategies, "
        "product frameworks, positioning playbooks, PMF benchmarks, pricing advice, and guest quotes. "
        "Returns verified excerpts from podcast episodes with guest attributions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query or growth topic to look up in the podcast transcripts.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of relevant transcript excerpts to retrieve (default: 4, min: 1, max: 8).",
                "default": 4,
            },
        },
        "required": ["query"],
    },
}


class SearchToolInput(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    top_k: int = Field(default=4, ge=1, le=8, description="Number of results")


def execute_search_transcripts(
    retriever: KnowledgeRetriever,
    query: str,
    top_k: int = 4,
) -> Dict[str, Any]:
    """
    Executes the strict transcript search tool against the ChromaDB vector store.
    
    TOOL BOUNDARIES:
    - Pure read-only semantic retrieval over pre-indexed Lenny podcast transcripts.
    - NO arbitrary shell execution.
    - NO filesystem modification or unrestricted file reads.
    - NO network crawling or external outbound requests.
    """
    safe_top_k = max(1, min(int(top_k), 8))
    logger.info("Agent invoked search_lenny_transcripts: query='%s', top_k=%d", query, safe_top_k)

    try:
        result = retriever.retrieve(query=query, top_k=safe_top_k)
        citations_data = [c.model_dump() if hasattr(c, "model_dump") else c.dict() for c in result.citations]

        return {
            "status": "success",
            "has_sufficient_context": result.has_sufficient_context,
            "context_text": result.context_text,
            "citations": citations_data,
            "raw_citations_count": len(result.citations),
        }
    except Exception as exc:
        logger.error("Error executing search_lenny_transcripts tool: %s", exc)
        return {
            "status": "error",
            "has_sufficient_context": False,
            "context_text": f"Error searching transcripts: {str(exc)}",
            "citations": [],
            "raw_citations_count": 0,
        }
