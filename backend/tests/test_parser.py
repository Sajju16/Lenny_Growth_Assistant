from pathlib import Path
import tempfile
import pytest
from rag.parser import parse_frontmatter, parse_transcript_file, TranscriptDoc

def test_parse_frontmatter_valid():
    text = """---
guest: Peter Kazanjy
title: Founder-Led Sales Playbook
youtube_url: https://www.youtube.com/watch?v=sample123
publish_date: 2023-01-15
---
# Transcript Body
Here is the actual content of the conversation.
"""
    meta, body = parse_frontmatter(text)
    assert meta["guest"] == "Peter Kazanjy"
    assert meta["title"] == "Founder-Led Sales Playbook"
    assert meta["youtube_url"] == "https://www.youtube.com/watch?v=sample123"
    assert "Here is the actual content" in body


def test_parse_frontmatter_missing():
    text = "Just plain text without frontmatter delimiters."
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_parse_frontmatter_malformed():
    text = """---
guest: [broken yaml : {
---
Body text goes here.
"""
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert "Body text goes here" in body


def test_parse_transcript_file_ignores_readme(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Lenny Transcripts Archive\nReadme information...", encoding="utf-8")
    doc = parse_transcript_file(readme)
    assert doc is None


def test_parse_transcript_file_success(tmp_path):
    ep_dir = tmp_path / "elena-verna"
    ep_dir.mkdir()
    trans_file = ep_dir / "transcript.md"
    trans_file.write_text("""---
guest: Elena Verna
title: B2B PLG Loops
video_id: abcXYZ123
publish_date: 2023-05-10
---
Elena Verna discusses product-led growth loops and self-serve mechanics in high-velocity SaaS businesses.
""", encoding="utf-8")

    doc = parse_transcript_file(trans_file)
    assert isinstance(doc, TranscriptDoc)
    assert doc.guest == "Elena Verna"
    assert doc.title == "B2B PLG Loops"
    assert doc.youtube_url == "https://www.youtube.com/watch?v=abcXYZ123"
    assert doc.publish_date == "2023-05-10"
    assert "Elena Verna discusses product-led growth" in doc.content
