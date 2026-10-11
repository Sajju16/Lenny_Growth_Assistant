import pytest
from rag.retriever import (
    build_excerpt,
    extract_best_segment,
    build_episode_excerpt,
    format_context_prompt,
    KnowledgeRetriever,
    Citation,
)
from llm.base import GROUNDED_SYSTEM_PROMPT


def test_build_excerpt():
    text = "Short string."
    assert build_excerpt(text) == "Short string."

    long_text = "Word " * 100
    excerpt = build_excerpt(long_text, max_chars=50)
    assert len(excerpt) <= 55
    assert excerpt.endswith("...")


def test_extract_best_segment_prioritizes_guest():
    dialogue = (
        "Lenny (00:24:12): Awesome. And it's interesting that onboarding comes up a lot. "
        "Dan Hockenmaier (00:24:30): Working on early user experience is highly impactful. "
        "Typically you want to wait to spin up resurrection efforts."
    )
    seg = extract_best_segment(dialogue, guest="Dan Hockenmaier", max_chars=200)
    assert "Working on early user experience" in seg
    assert "Lenny (00:24:12)" not in seg


def test_format_context_prompt_empty():
    assert "No relevant" in format_context_prompt([])


def test_format_context_prompt_with_chunks():
    chunks = [
        {
            "title": "Finding First 100 Customers",
            "guest": "Pete Kazanjy",
            "publish_date": "2022-12-15",
            "youtube_url": "https://www.youtube.com/watch?v=123",
            "text": "Founders must do sales manually at first.",
        }
    ]
    prompt = format_context_prompt(chunks)
    assert "EVIDENCE EXCERPT 1" in prompt
    assert "Guest: Pete Kazanjy" in prompt
    assert "Founders must do sales manually" in prompt


class MockVectorStore:
    def __init__(self, return_chunks):
        self.return_chunks = return_chunks

    def query(self, query_text: str, top_k: int = 4):
        return self.return_chunks


def test_retriever_insufficient_evidence():
    # Return chunks below MIN_SIMILARITY_THRESHOLD (0.35)
    weak_chunks = [
        {
            "chunk_id": "weak_1",
            "text": "Completely unrelated content about baking cookies.",
            "guest": "Unknown",
            "title": "Irrelevant",
            "youtube_url": "",
            "publish_date": "",
            "similarity_score": 0.15,
        }
    ]
    retriever = KnowledgeRetriever(vector_store=MockVectorStore(weak_chunks))
    result = retriever.retrieve("How do I calculate net retention?")
    assert result.has_sufficient_context is False
    assert len(result.citations) == 0
    assert len(result.raw_chunks) == 0
    assert result.context_text == ""


def test_retriever_sufficient_evidence():
    strong_chunks = [
        {
            "chunk_id": "strong_1",
            "text": "Net revenue retention should exceed 120% for top-tier enterprise SaaS companies.",
            "guest": "Patrick Campbell",
            "title": "Pricing & Retention Dynamics",
            "youtube_url": "https://www.youtube.com/watch?v=pc123",
            "publish_date": "2023-08-10",
            "similarity_score": 0.78,
        }
    ]
    retriever = KnowledgeRetriever(vector_store=MockVectorStore(strong_chunks))
    result = retriever.retrieve("What is a good NRR benchmark?")
    assert result.has_sufficient_context is True
    assert len(result.citations) == 1
    assert result.citations[0].guest == "Patrick Campbell"
    assert result.citations[0].relevance_score == 0.78


def test_retriever_multiple_chunks_same_episode():
    """
    When multiple chunks from the same episode are retrieved (e.g. Dan Hockenmaier on retention):
    1. Produces exactly 1 citation for that episode (episode-level deduplication).
    2. Relevance score reflects the highest similarity chunk.
    3. Excerpt synthesizes verbatim evidence from all relevant chunks separated by ' [...] '.
    4. Model context (raw_chunks and context_text) retains ALL chunks without dropping them.
    """
    dan_chunks = [
        {
            "chunk_id": "dan-hockenmaier_c0037",
            "guest": "Dan Hockenmaier",
            "title": "Developing a growth model | Dan Hockenmaier",
            "youtube_url": "https://www.youtube.com/watch?v=dan123",
            "publish_date": "2023-05-15",
            "similarity_score": 0.85,
            "text": "Dan Hockenmaier (00:21:04): Retention is a tough measure to work on. You should be working more on core product levers than growth levers.",
        },
        {
            "chunk_id": "dan-hockenmaier_c0038",
            "guest": "Dan Hockenmaier",
            "title": "Developing a growth model | Dan Hockenmaier",
            "youtube_url": "https://www.youtube.com/watch?v=dan123",
            "publish_date": "2023-05-15",
            "similarity_score": 0.84,
            "text": "Dan Hockenmaier (00:21:49): Very often the biggest wins in retention come from inflecting the early user experience.",
        },
        {
            "chunk_id": "dan-hockenmaier_c0042",
            "guest": "Dan Hockenmaier",
            "title": "Developing a growth model | Dan Hockenmaier",
            "youtube_url": "https://www.youtube.com/watch?v=dan123",
            "publish_date": "2023-05-15",
            "similarity_score": 0.81,
            "text": "Dan Hockenmaier (00:24:30): You want to wait to spin up resurrection efforts until you've exhausted early funnel efforts.",
        },
    ]

    retriever = KnowledgeRetriever(vector_store=MockVectorStore(dan_chunks))
    result = retriever.retrieve("How should I think about retention and resurrection?", top_k=3)

    assert result.has_sufficient_context is True
    # 1 episode citation
    assert len(result.citations) == 1
    citation = result.citations[0]
    assert citation.guest == "Dan Hockenmaier"
    assert citation.episode_title == "Developing a growth model | Dan Hockenmaier"
    assert citation.relevance_score == 0.85

    # Excerpt contains advice from all 3 chunks
    assert "core product levers" in citation.excerpt
    assert "early user experience" in citation.excerpt
    assert "resurrection efforts" in citation.excerpt
    assert " [...] " in citation.excerpt

    # Model context retains ALL 3 chunks
    assert len(result.raw_chunks) == 3
    assert "EVIDENCE EXCERPT 1" in result.context_text
    assert "EVIDENCE EXCERPT 2" in result.context_text
    assert "EVIDENCE EXCERPT 3" in result.context_text


def test_retriever_different_episodes_distinct_citations():
    """
    When chunks from multiple distinct episodes are retrieved, each episode receives
    its own distinct citation, sorted by highest similarity score.
    """
    multi_episode_chunks = [
        {
            "chunk_id": "dan_c1",
            "guest": "Dan Hockenmaier",
            "title": "Developing a growth model",
            "youtube_url": "https://www.youtube.com/watch?v=dan",
            "publish_date": "2023-05-15",
            "similarity_score": 0.85,
            "text": "Dan Hockenmaier (00:10:00): Focus on retention early.",
        },
        {
            "chunk_id": "dan_c2",
            "guest": "Dan Hockenmaier",
            "title": "Developing a growth model",
            "youtube_url": "https://www.youtube.com/watch?v=dan",
            "publish_date": "2023-05-15",
            "similarity_score": 0.83,
            "text": "Dan Hockenmaier (00:15:00): Build loops not funnels.",
        },
        {
            "chunk_id": "patrick_c1",
            "guest": "Patrick Campbell",
            "title": "Pricing & Retention Dynamics",
            "youtube_url": "https://www.youtube.com/watch?v=patrick",
            "publish_date": "2023-08-10",
            "similarity_score": 0.79,
            "text": "Patrick Campbell (00:08:00): Pricing is your fastest monetization lever.",
        },
    ]

    retriever = KnowledgeRetriever(vector_store=MockVectorStore(multi_episode_chunks))
    result = retriever.retrieve("Retention and pricing growth levers", top_k=3)

    assert result.has_sufficient_context is True
    assert len(result.citations) == 2
    assert result.citations[0].guest == "Dan Hockenmaier"
    assert result.citations[0].relevance_score == 0.85
    assert result.citations[1].guest == "Patrick Campbell"
    assert result.citations[1].relevance_score == 0.79

    # Model context retains all 3 chunks
    assert len(result.raw_chunks) == 3


def test_citation_excerpt_verbatim_transcript_words():
    """
    Verifies that the citation excerpt consists strictly of verbatim text from
    the indexed chunks without inventing or hallucinating words.
    """
    chunk_text = "Dan Hockenmaier (00:21:04): Retention is a tough measure to work on because it is the culmination of the entire product experience."
    chunk = {
        "chunk_id": "dan_test_1",
        "guest": "Dan Hockenmaier",
        "title": "Growth Models",
        "youtube_url": "https://www.youtube.com/watch?v=test",
        "publish_date": "2023-05-15",
        "similarity_score": 0.82,
        "text": chunk_text,
    }
    retriever = KnowledgeRetriever(vector_store=MockVectorStore([chunk]))
    result = retriever.retrieve("retention", top_k=1)

    assert len(result.citations) == 1
    excerpt_clean = result.citations[0].excerpt.replace("...", "").strip()
    # The excerpt text must appear verbatim within the original chunk text
    assert excerpt_clean in chunk_text


def test_grounding_system_prompt_rules():
    """
    Verifies that the system prompt strictly enforces direct evidence grounding,
    distinguishes inference, and mandates stating insufficient evidence.
    """
    prompt = GROUNDED_SYSTEM_PROMPT.lower()
    assert "direct evidence" in prompt
    assert "distinguish direct" in prompt or "inference" in prompt
    assert "insufficient evidence" in prompt
    assert "fabricate" in prompt


def test_retention_question_prunes_weakly_related_citation():
    """
    Regression test for retention & early UX vs resurrection query:
    1. Dan Hockenmaier has 3 chunks (scores: 0.8201, 0.7564, 0.6947) directly answering the query.
    2. Elena Verna has 1 chunk (score: 0.7009) with a 0.1192 score gap and only peripheral word overlap.
    3. LLM model context retains ALL 4 chunks (len(result.raw_chunks) == 4).
    4. Citations list retains ONLY the directly relevant source (Dan Hockenmaier), pruning the weakly related citation.
    """
    chunks = [
        {
            "chunk_id": "dan_c0042",
            "guest": "Dan Hockenmaier",
            "title": "Developing a growth model | Dan Hockenmaier",
            "youtube_url": "https://www.youtube.com/watch?v=dan",
            "publish_date": "2023-05-15",
            "similarity_score": 0.8201,
            "text": "Working on early user experience is highly impactful. You often see product teams say we should work on resurrection... typically you want to wait to spin up resurrection efforts until you've exhausted earlier funnel efforts.",
        },
        {
            "chunk_id": "dan_c0038",
            "guest": "Dan Hockenmaier",
            "title": "Developing a growth model | Dan Hockenmaier",
            "youtube_url": "https://www.youtube.com/watch?v=dan",
            "publish_date": "2023-05-15",
            "similarity_score": 0.7564,
            "text": "Very often I think the biggest wins in retention come from inflecting the early user experience. In that very first experience, you have a lot of opportunity.",
        },
        {
            "chunk_id": "elena_c0013",
            "guest": "Elena Verna",
            "title": "PLG & Growth Teams | Elena Verna",
            "youtube_url": "https://www.youtube.com/watch?v=elena",
            "publish_date": "2023-06-20",
            "similarity_score": 0.7009,
            "text": "a shiny resume can come over and all of a sudden wave a magic wand and you have viral campaigns and everybody's paying and retaining. That just doesn't happen.",
        },
        {
            "chunk_id": "dan_c0037",
            "guest": "Dan Hockenmaier",
            "title": "Developing a growth model | Dan Hockenmaier",
            "youtube_url": "https://www.youtube.com/watch?v=dan",
            "publish_date": "2023-05-15",
            "similarity_score": 0.6947,
            "text": "Retention is a tough measure to work on because it is the culmination of the entire product experience. You actually should be working more on core product levers than growth product levers.",
        },
    ]

    retriever = KnowledgeRetriever(vector_store=MockVectorStore(chunks))
    query = "How should an early-stage startup improve retention, and should we focus on early user experience or resurrection campaigns?"
    result = retriever.retrieve(query=query, top_k=4)

    assert result.has_sufficient_context is True
    # All 4 chunks preserved in LLM context
    assert len(result.raw_chunks) == 4
    assert "EVIDENCE EXCERPT 1" in result.context_text
    assert "EVIDENCE EXCERPT 4" in result.context_text

    # Weakly related citation pruned from UI citations
    assert len(result.citations) == 1
    assert result.citations[0].guest == "Dan Hockenmaier"
    assert result.citations[0].relevance_score == 0.8201
    assert "early user experience" in result.citations[0].excerpt
    assert "resurrection efforts" in result.citations[0].excerpt


def test_align_citations_with_response_claims():
    from rag.retriever import align_citations_with_response

    c_dan = Citation(
        guest="Dan Hockenmaier",
        episode_title="Growth Models",
        excerpt="Focus on early user experience.",
        relevance_score=0.82,
    )
    c_elena = Citation(
        guest="Elena Verna",
        episode_title="Growth Teams",
        excerpt="Viral campaigns do not appear by magic.",
        relevance_score=0.70,
    )

    # When generated response mentions only Dan Hockenmaier
    resp_dan_only = "Based on the transcripts, Dan Hockenmaier advises prioritizing early user experience over resurrection campaigns."
    aligned = align_citations_with_response([c_dan, c_elena], resp_dan_only)
    assert len(aligned) == 1
    assert aligned[0].guest == "Dan Hockenmaier"

    # When generated response mentions both Dan and Elena
    resp_both = "Dan Hockenmaier emphasizes early retention while Elena Verna cautions against premature growth hires."
    aligned_both = align_citations_with_response([c_dan, c_elena], resp_both)
    assert len(aligned_both) == 2

    # When generated response mentions neither explicitly
    resp_neither = "Prioritize core product levers before launching resurrection efforts."
    aligned_neither = align_citations_with_response([c_dan, c_elena], resp_neither)
    assert len(aligned_neither) == 2


def test_unsupported_question_no_fabricated_citations():
    """
    Verifies that unsupported questions return has_sufficient_context = False,
    empty citations, and no fabricated evidence.
    """
    unrelated_chunks = [
        {
            "chunk_id": "weak_1",
            "text": "Completely unrelated discussion about baking sourdough croissants.",
            "guest": "Unknown",
            "title": "Cooking Show",
            "youtube_url": "",
            "publish_date": "",
            "similarity_score": 0.18,
        }
    ]
    retriever = KnowledgeRetriever(vector_store=MockVectorStore(unrelated_chunks))
    result = retriever.retrieve("What is the recipe for baking sourdough croissants?", top_k=4)

    assert result.has_sufficient_context is False
    assert len(result.citations) == 0
    assert len(result.raw_chunks) == 0
    assert result.context_text == ""


def test_sourdough_croissants_unsupported_gate_with_moderate_raw_similarity():
    """
    Regression test for 'How do I bake sourdough croissants?':
    Even when ChromaDB returns chunks in the 0.45-0.48 similarity range (Brian Chesky, April Dunford),
    the conservative evidence gate recognizes that zero baking/croissant concepts exist in the transcripts
    and returns has_sufficient_context = False with zero citations.
    """
    croissant_chunks = [
        {
            "chunk_id": "brian-chesky_c0081",
            "guest": "Brian Chesky",
            "title": "Brian Chesky's new playbook",
            "youtube_url": "https://www.youtube.com/watch?v=bc1",
            "publish_date": "2023-10-15",
            "similarity_score": 0.4766,
            "text": "What do we do with powder? Turns out powder can be used for paint, but the way you sell gunpowder and paint are different sales channels.",
        },
        {
            "chunk_id": "april-dunford_c0088",
            "guest": "April Dunford",
            "title": "A step-by-step guide to crafting a sales pitch that wins",
            "youtube_url": "https://www.youtube.com/watch?v=ad1",
            "publish_date": "2023-10-22",
            "similarity_score": 0.4536,
            "text": "there's usually a step called proof, which is, I showed you the value, now here's the proof that I can actually deliver on that value.",
        },
        {
            "chunk_id": "april-dunford-20_c0088",
            "guest": "April Dunford 2.0",
            "title": "How to nail your product positioning",
            "youtube_url": "https://www.youtube.com/watch?v=ad2",
            "publish_date": "2023-01-22",
            "similarity_score": 0.4536,
            "text": "there's usually a step called proof, which is, I showed you the value, now here's the proof that I can actually deliver on that value.",
        },
    ]
    retriever = KnowledgeRetriever(vector_store=MockVectorStore(croissant_chunks))
    result = retriever.retrieve("How do I bake sourdough croissants?", top_k=4)

    assert result.has_sufficient_context is False
    assert len(result.citations) == 0
    assert len(result.raw_chunks) == 0
    assert result.context_text == ""


def test_duplicate_episode_citations_deduplicated():
    """
    When multiple chunks from the same underlying speaker/episode exist with duplicate or
    versioned guest tags ('April Dunford' vs 'April Dunford 2.0') and identical excerpt content,
    the retriever consolidates them into a single canonical citation.
    """
    duplicate_chunks = [
        {
            "chunk_id": "april_c1",
            "guest": "April Dunford",
            "title": "Sales Pitch Playbook",
            "youtube_url": "https://www.youtube.com/watch?v=ad1",
            "publish_date": "2023-10-22",
            "similarity_score": 0.78,
            "text": "April Dunford (00:10:00): A sales pitch must lead with a macro change in the world before talking about features.",
        },
        {
            "chunk_id": "april_c2",
            "guest": "April Dunford 2.0",
            "title": "Positioning Guide",
            "youtube_url": "https://www.youtube.com/watch?v=ad2",
            "publish_date": "2023-01-22",
            "similarity_score": 0.77,
            "text": "April Dunford (00:10:00): A sales pitch must lead with a macro change in the world before talking about features.",
        },
    ]
    retriever = KnowledgeRetriever(vector_store=MockVectorStore(duplicate_chunks))
    result = retriever.retrieve("How do I craft a sales pitch?", top_k=2)

    assert result.has_sufficient_context is True
    # Deduplicated to 1 canonical citation
    assert len(result.citations) == 1
    assert result.citations[0].guest == "April Dunford"
    assert result.citations[0].relevance_score == 0.78


def test_align_citations_insufficient_evidence_returns_empty():
    from rag.retriever import align_citations_with_response, Citation

    c = Citation(
        guest="Brian Chesky",
        episode_title="Playbook",
        excerpt="Sales channels and divisional structures.",
        relevance_score=0.48,
    )

    resp = (
        "Based on the verified podcast transcripts currently indexed, there is "
        "insufficient evidence to answer this question."
    )
    aligned = align_citations_with_response([c], resp)
    assert aligned == []
