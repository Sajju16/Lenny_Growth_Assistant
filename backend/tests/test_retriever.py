import pytest
from rag.retriever import build_excerpt, format_context_prompt, KnowledgeRetriever, Citation

def test_build_excerpt():
    text = "Short string."
    assert build_excerpt(text) == "Short string."

    long_text = "Word " * 100
    excerpt = build_excerpt(long_text, max_chars=50)
    assert len(excerpt) <= 55
    assert excerpt.endswith("...")


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
