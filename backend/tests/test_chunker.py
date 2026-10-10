import pytest
from rag.parser import TranscriptDoc
from rag.chunker import split_text_into_chunks, chunk_transcript, TranscriptChunk

def test_split_text_small():
    text = "Short text fits in one chunk."
    chunks = split_text_into_chunks(text, chunk_size=500, chunk_overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_text_overlapping():
    para1 = "Paragraph one introduces founding sales and direct manual customer outreach."
    para2 = "Paragraph two describes why scalable marketing at phase zero is a fatal distraction."
    para3 = "Paragraph three outlines concierge onboarding to diagnose funnel leaks directly."
    full_text = f"{para1}\n\n{para2}\n\n{para3}"

    chunks = split_text_into_chunks(full_text, chunk_size=100, chunk_overlap=30)
    assert len(chunks) >= 2
    # Verify that content is covered
    assert any("founding sales" in c for c in chunks)
    assert any("concierge onboarding" in c for c in chunks)


def test_chunk_transcript_preserves_metadata():
    doc = TranscriptDoc(
        episode_slug="pete-kazanjy",
        guest="Pete Kazanjy",
        title="Founder-Led Sales",
        youtube_url="https://www.youtube.com/watch?v=sample",
        video_id="sample",
        publish_date="2022-12-15",
        content="Section A about sales.\n\nSection B about hiring.\n\nSection C about qualification.",
        source_file="episodes/pete-kazanjy/transcript.md",
    )

    chunks = chunk_transcript(doc, chunk_size=40, chunk_overlap=10)
    assert len(chunks) > 0

    for idx, chunk in enumerate(chunks):
        assert isinstance(chunk, TranscriptChunk)
        assert chunk.episode_slug == "pete-kazanjy"
        assert chunk.guest == "Pete Kazanjy"
        assert chunk.title == "Founder-Led Sales"
        assert chunk.youtube_url == "https://www.youtube.com/watch?v=sample"
        assert chunk.publish_date == "2022-12-15"
        assert chunk.chunk_id == f"pete-kazanjy_c{idx:04d}"
        assert chunk.chunk_index == idx
