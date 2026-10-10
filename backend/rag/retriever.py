import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from .vector_store import VectorStore

logger = logging.getLogger("lenny-growth-backend.rag")

MIN_SIMILARITY_THRESHOLD = 0.35  # Threshold below which evidence is considered too weak

class Citation(BaseModel):
    guest: str
    episode_title: str
    youtube_url: Optional[str] = None
    publish_date: Optional[str] = None
    excerpt: str
    relevance_score: float


class RetrievalResult(BaseModel):
    has_sufficient_context: bool
    context_text: str
    citations: List[Citation]
    raw_chunks: List[Dict[str, Any]]


def build_excerpt(text: str, max_chars: int = 280) -> str:
    """
    Trims chunk text cleanly for use as a citation excerpt.
    """
    clean = " ".join(text.split()).strip()
    if len(clean) <= max_chars:
        return clean
    # Cut at last complete word
    cutoff = clean[:max_chars].rfind(" ")
    if cutoff > 100:
        return clean[:cutoff] + "..."
    return clean[:max_chars] + "..."


def format_context_prompt(chunks: List[Dict[str, Any]]) -> str:
    """
    Formats retrieved chunks into an unambiguous context block for the LLM.
    """
    if not chunks:
        return "No relevant podcast transcripts were found in the knowledge base."

    sections = []
    for idx, c in enumerate(chunks, 1):
        url_line = f"URL: {c['youtube_url']}" if c.get('youtube_url') else ""
        date_line = f"Date: {c['publish_date']}" if c.get('publish_date') else ""
        header_parts = [f"Episode: {c['title']}", f"Guest: {c['guest']}"]
        if date_line:
            header_parts.append(date_line)
        if url_line:
            header_parts.append(url_line)

        sections.append(
            f"--- EVIDENCE EXCERPT {idx} ---\n"
            + "\n".join(header_parts) + "\n\n"
            + c["text"]
        )

    return "\n\n".join(sections)


class KnowledgeRetriever:
    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or VectorStore()

    def retrieve(self, query: str, top_k: int = 4) -> RetrievalResult:
        """
        Retrieves top_k transcript chunks from ChromaDB, constructs citations,
        and determines if evidence threshold is met.
        """
        try:
            raw_chunks = self.vector_store.query(query_text=query, top_k=top_k)
        except Exception as exc:
            logger.error("Vector store retrieval error: %s", exc)
            return RetrievalResult(
                has_sufficient_context=False,
                context_text="",
                citations=[],
                raw_chunks=[]
            )

        if not raw_chunks:
            return RetrievalResult(
                has_sufficient_context=False,
                context_text="",
                citations=[],
                raw_chunks=[]
            )

        # Filter chunks that meet minimum relevance
        relevant_chunks = [c for c in raw_chunks if c.get("similarity_score", 0.0) >= MIN_SIMILARITY_THRESHOLD]

        # Deduplicate citations by episode title
        seen_episodes = set()
        citations: List[Citation] = []

        for chunk in relevant_chunks:
            key = (chunk.get("guest"), chunk.get("title"))
            if key not in seen_episodes:
                seen_episodes.add(key)
                citations.append(
                    Citation(
                        guest=chunk.get("guest", "Unknown"),
                        episode_title=chunk.get("title", "Lenny's Podcast"),
                        youtube_url=chunk.get("youtube_url") or None,
                        publish_date=chunk.get("publish_date") or None,
                        excerpt=build_excerpt(chunk.get("text", "")),
                        relevance_score=chunk.get("similarity_score", 0.0)
                    )
                )

        has_sufficient = len(relevant_chunks) > 0
        context_text = format_context_prompt(relevant_chunks)

        return RetrievalResult(
            has_sufficient_context=has_sufficient,
            context_text=context_text,
            citations=citations,
            raw_chunks=relevant_chunks
        )
