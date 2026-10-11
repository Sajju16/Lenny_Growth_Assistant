import logging
import re
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


def extract_best_segment(text: str, guest: str = "", max_chars: int = 240) -> str:
    """
    Extracts the most informative, substantive passage from a chunk, prioritizing
    the guest's direct dialogue and avoiding conversational filler or question preambles.
    Preserves exact transcript wording without fabricating quotations.
    """
    clean = " ".join(text.split()).strip()
    if not clean:
        return ""

    # 1. Prioritize guest speaker turn if present (e.g. "Dan Hockenmaier (00:24:30):")
    if guest:
        pattern = re.compile(rf"{re.escape(guest)}\s*(?:\([^)]*\))?\s*:\s*", re.IGNORECASE)
        m = pattern.search(clean)
        if m:
            clean = clean[m.end():].strip()

    # 2. If the segment ends with Lenny asking another question, trim trailing question
    clean = re.sub(r"\s*Lenny\s*(?:\([^)]*\))?\s*:.*$", "", clean, flags=re.IGNORECASE).strip()

    # 3. If clean starts with a broken word or lower-case fragment before a sentence boundary
    if clean and clean[0].islower():
        dot_idx = clean.find(". ")
        if 0 < dot_idx < 60:
            clean = clean[dot_idx + 2:].strip()

    if len(clean) <= max_chars:
        return clean

    cutoff = clean[:max_chars].rfind(" ")
    if cutoff > 60:
        return clean[:cutoff] + "..."
    return clean[:max_chars] + "..."


def build_episode_excerpt(ep_chunks: List[Dict[str, Any]], guest: str = "") -> str:
    """
    Constructs a faithful, genuine excerpt from the retrieved chunks of a single episode.
    If multiple chunks from the episode were retrieved, extracts the key supporting segments
    and connects them with ' [...] ' without fabricating any wording.
    """
    if not ep_chunks:
        return ""

    if len(ep_chunks) == 1:
        seg = extract_best_segment(ep_chunks[0].get("text", ""), guest=guest, max_chars=280)
        return seg or build_excerpt(ep_chunks[0].get("text", ""), max_chars=280)

    # Sort chunks chronologically by chunk_id or chunk_index if present
    sorted_chunks = sorted(ep_chunks, key=lambda c: (c.get("chunk_id") or "", c.get("chunk_index") or 0))
    per_chunk_chars = 180 if len(sorted_chunks) >= 3 else 220

    segments = []
    seen_texts = set()
    for c in sorted_chunks:
        seg = extract_best_segment(c.get("text", ""), guest=guest, max_chars=per_chunk_chars)
        if not seg:
            seg = build_excerpt(c.get("text", ""), max_chars=per_chunk_chars)
        if seg:
            if any(seg in existing or existing in seg for existing in segments):
                continue
            seen_texts.add(seg)
            segments.append(seg)

    if not segments:
        return build_excerpt(ep_chunks[0].get("text", ""), max_chars=280)

    return " [...] ".join(segments)


# Expanded stop words and domain acronyms for conservative query grounding
STOPWORDS = {
    "how", "what", "when", "where", "which", "who", "whom", "whose", "why",
    "can", "could", "should", "would", "will", "shall", "may", "might", "must",
    "the", "and", "for", "with", "from", "into", "during", "including", "until",
    "against", "among", "throughout", "despite", "towards", "upon", "concerning",
    "about", "above", "below", "over", "under", "again", "further", "then", "once",
    "here", "there", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "just", "don", "now", "are", "was", "were", "been", "being", "have",
    "has", "had", "having", "does", "did", "doing", "tell", "give", "explain",
    "best", "good", "make", "take", "like", "know", "think", "come", "want",
    "month", "months", "year", "years", "time", "times", "day", "days", "week", "weeks",
    "place", "places", "visit", "people", "thing", "things", "step", "steps", "way", "ways",
    "detail", "details", "help", "need", "start", "stop", "many", "much", "find",
}

DOMAIN_ACRONYMS = {
    "nrr": ["nrr", "retention", "net revenue"],
    "ndr": ["ndr", "retention", "dollar retention"],
    "plg": ["plg", "product-led", "product led", "freemium"],
    "pmf": ["pmf", "product-market fit", "product market fit"],
    "cac": ["cac", "acquisition cost", "customer acquisition"],
    "ltv": ["ltv", "lifetime value"],
    "gtm": ["gtm", "go-to-market", "go to market"],
    "icp": ["icp", "ideal customer profile"],
    "slg": ["slg", "sales-led", "sales led"],
}


def extract_query_concepts(query: str) -> set:
    """
    Extracts substantive conceptual terms from a user query, expanding common
    growth/product domain acronyms and filtering conversational stopwords.
    """
    words = re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", query.lower())
    concepts = set()
    for w in words:
        if w in DOMAIN_ACRONYMS:
            concepts.add(w)
            concepts.update(DOMAIN_ACRONYMS[w])
        elif len(w) >= 3 and w not in STOPWORDS:
            concepts.add(w)
    return concepts


def stem_or_prefix(word: str) -> str:
    w = word.lower()
    for suffix in ("ing", "tion", "tions", "ies", "es", "s", "ed", "ment", "al"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[:-len(suffix)]
    return w


def normalize_guest_name(guest: str) -> str:
    """
    Normalizes guest names by stripping version suffixes like ' 2.0', ' (2)', etc.
    """
    cleaned = re.sub(r"\s+(?:2\.0|\d+(\.\d+)?)$", "", guest.strip(), flags=re.IGNORECASE)
    return cleaned.strip()


def evaluate_evidence_sufficiency(query: str, raw_chunks: List[Dict[str, Any]]) -> bool:
    """
    Determines whether retrieved chunks contain genuine, sufficient evidence for the query.
    Prevents out-of-domain queries (e.g. baking recipes, general trivia) from passing based on
    embedding baseline scores alone.
    """
    if not raw_chunks:
        return False

    top_chunk = raw_chunks[0]
    top_score = top_chunk.get("similarity_score", 0.0)

    # 1. Floor check: if top score is below 0.42, evidence is universally too weak
    if top_score < 0.42:
        return False

    query_concepts = extract_query_concepts(query)
    if not query_concepts:
        # If query has no substantive concepts (e.g. "Hi", "Hello"), fail closed
        return False

    # Extract all text from retrieved chunks
    combined_text = " ".join([c.get("text", "") for c in raw_chunks]).lower()

    # Count how many query concepts match the retrieved text
    matched_concepts = set()
    for concept in query_concepts:
        if " " in concept:
            if concept in combined_text:
                matched_concepts.add(concept)
        else:
            stem = stem_or_prefix(concept)
            pattern = re.compile(rf"\b{re.escape(stem)}[a-z]*\b", re.IGNORECASE)
            if pattern.search(combined_text):
                matched_concepts.add(concept)

    # 2. Strict Grounding Gate:
    # If ZERO core concepts matched the retrieved transcripts, the query is unsupported out-of-domain!
    if not matched_concepts:
        logger.info(
            "Evidence gate: out-of-domain query detected (concepts=%s, matched=0, top_score=%.4f)",
            query_concepts, top_score
        )
        return False

    # 3. For moderate similarity (top_score < 0.50):
    # Require at least two distinct matched concepts (prevents accidental single-word collision)
    if top_score < 0.50:
        if len(matched_concepts) < 2:
            logger.info(
                "Evidence gate: weak evidence (top_score=%.4f < 0.50 with only 1 match: %s)",
                top_score, matched_concepts
            )
            return False

    return True


def filter_citations_by_relevance(
    citations: List[Citation],
    query: str,
    margin_threshold: float = 0.08,
) -> List[Citation]:
    """
    Filters citations to prioritize directly relevant evidence over weakly related citations.
    Cosine similarity measures distance in semantic embedding space, not logical or factual support.
    When a top primary episode provides dominant evidence, secondary episodes with significant
    similarity drop-offs that lack substantive query concept coverage are filtered out.
    """
    if not citations:
        return []

    top_score = max(c.relevance_score for c in citations)

    query_words = extract_query_concepts(query)

    filtered: List[Citation] = []
    for c in citations:
        # Highest scoring citation is always preserved
        if c.relevance_score == top_score:
            filtered.append(c)
            continue

        score_gap = top_score - c.relevance_score

        # If score is very close (within 0.05 margin), retain it
        if score_gap <= 0.05:
            filtered.append(c)
            continue

        # If score gap > 0.05, check concept overlap with query
        excerpt_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", c.excerpt.lower()))
        matched_terms = query_words.intersection(excerpt_words)

        # If score gap exceeds margin_threshold (e.g. > 0.08) and excerpt matches fewer than 2 distinct query concepts,
        # reject as weakly related
        if score_gap > margin_threshold and len(matched_terms) < 2:
            logger.info(
                "Pruning weakly related citation: guest='%s', score=%.4f (gap=%.4f vs top=%.4f, query_matches=%s)",
                c.guest, c.relevance_score, score_gap, top_score, matched_terms
            )
            continue

        filtered.append(c)

    return filtered


def align_citations_with_response(
    citations: List[Citation],
    response_text: str,
) -> List[Citation]:
    """
    Aligns displayed citations with the claims in the generated assistant response.
    If the response declares insufficient evidence, returns empty citations.
    If the response explicitly attributes advice to specific guests (e.g. 'Dan Hockenmaier explains...'),
    it filters citations to only those guests actually referenced in the response.
    Never restores unmentioned citations if the response made no reference to them.
    """
    if not citations or not response_text:
        return []

    lower_resp = response_text.lower()

    # If the response explicitly declares insufficient evidence, do not display citations
    if (
        "insufficient evidence" in lower_resp
        or "not enough information" in lower_resp
        or "no relevant podcast transcripts" in lower_resp
    ):
        return []

    # Check which citation guests are explicitly named/attributed in the generated answer
    mentioned = [
        c for c in citations
        if c.guest.lower() in lower_resp
    ]

    if mentioned:
        return mentioned

    # If no guest names are mentioned, check if substantive phrases from the citation excerpt appear in response
    substantiated = []
    for c in citations:
        excerpt_words = c.excerpt.lower().split()
        is_substantiated = False
        for i in range(len(excerpt_words) - 3):
            trigram = " ".join(excerpt_words[i:i+4])
            if len(trigram) > 15 and trigram in lower_resp:
                is_substantiated = True
                break
        if is_substantiated:
            substantiated.append(c)

    return substantiated if substantiated else citations


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
        Retrieves top_k transcript chunks from ChromaDB, constructs episode-deduplicated
        citations with synthesized multi-chunk excerpts, and determines if evidence threshold is met.
        All relevant chunks are preserved in raw_chunks and context_text for the LLM.
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

        # Evaluate conservative evidence sufficiency gate
        has_sufficient = evaluate_evidence_sufficiency(query=query, raw_chunks=raw_chunks)
        if not has_sufficient:
            logger.info("Conservative evidence gate: query '%s' deemed unsupported by indexed transcripts", query)
            return RetrievalResult(
                has_sufficient_context=False,
                context_text="",
                citations=[],
                raw_chunks=[]
            )

        # Filter chunks that meet minimum relevance
        relevant_chunks = [c for c in raw_chunks if c.get("similarity_score", 0.0) >= MIN_SIMILARITY_THRESHOLD]

        if not relevant_chunks:
            return RetrievalResult(
                has_sufficient_context=False,
                context_text="",
                citations=[],
                raw_chunks=[]
            )

        # Deduplicate citations by canonical guest & episode title, avoiding duplicate episode content
        grouped_by_episode: Dict[tuple, List[Dict[str, Any]]] = {}
        for chunk in relevant_chunks:
            guest_raw = chunk.get("guest", "Unknown")
            canonical_guest = normalize_guest_name(guest_raw)
            title = chunk.get("title", "Lenny's Podcast")
            key = (canonical_guest, title)
            if key not in grouped_by_episode:
                grouped_by_episode[key] = []
            grouped_by_episode[key].append(chunk)

        citations: List[Citation] = []
        seen_canonical_guests = set()
        seen_excerpt_hashes = set()

        for (canonical_guest, title), ep_chunks in grouped_by_episode.items():
            best_chunk = max(ep_chunks, key=lambda c: c.get("similarity_score", 0.0))
            youtube_url = next((c.get("youtube_url") for c in ep_chunks if c.get("youtube_url")), None)
            publish_date = next((c.get("publish_date") for c in ep_chunks if c.get("publish_date")), None)
            excerpt = build_episode_excerpt(ep_chunks, guest=canonical_guest)

            # Deduplicate duplicate content from same guest with identical excerpt text
            excerpt_key = " ".join(excerpt.split()[:20]).lower()
            if canonical_guest in seen_canonical_guests and excerpt_key in seen_excerpt_hashes:
                logger.info("Deduplicating duplicate episode citation for guest: %s", canonical_guest)
                continue

            seen_canonical_guests.add(canonical_guest)
            if excerpt_key:
                seen_excerpt_hashes.add(excerpt_key)

            citations.append(
                Citation(
                    guest=canonical_guest,
                    episode_title=title,
                    youtube_url=youtube_url or best_chunk.get("youtube_url") or None,
                    publish_date=publish_date or best_chunk.get("publish_date") or None,
                    excerpt=excerpt,
                    relevance_score=best_chunk.get("similarity_score", 0.0),
                )
            )

        # Sort citations by relevance_score descending
        citations.sort(key=lambda c: c.relevance_score, reverse=True)

        # Prioritize directly relevant evidence over weakly related citations
        citations = filter_citations_by_relevance(citations, query=query)

        context_text = format_context_prompt(relevant_chunks)

        return RetrievalResult(
            has_sufficient_context=True,
            context_text=context_text,
            citations=citations,
            raw_chunks=relevant_chunks
        )
