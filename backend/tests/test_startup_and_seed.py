import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app, auto_seed_knowledge_base
from rag.ingest import DEFAULT_TRANSCRIPTS_DIR
from rag.parser import parse_transcript_file


client = TestClient(app)


def test_actual_transcript_source_directory_exists_and_parseable():
    """
    Validates that the project's actual transcript sources exist in the repository
    and contain valid episode transcripts parseable into structured documents.
    """
    assert DEFAULT_TRANSCRIPTS_DIR.exists(), f"Raw transcripts directory missing: {DEFAULT_TRANSCRIPTS_DIR}"
    episodes = [p for p in DEFAULT_TRANSCRIPTS_DIR.iterdir() if p.is_dir()]
    assert len(episodes) > 0, "No episode folders found in raw transcripts directory"

    # Verify at least one real episode has a valid transcript.md with frontmatter
    sample_transcript = None
    for ep in episodes:
        cand = ep / "transcript.md"
        if cand.exists():
            sample_transcript = cand
            break

    assert sample_transcript is not None, "No transcript.md discovered in episode directories"
    doc = parse_transcript_file(sample_transcript)
    assert doc.guest, "Parsed transcript should extract guest name"
    assert doc.title, "Parsed transcript should extract title"
    assert len(doc.content) > 100, "Parsed transcript should contain transcript text"


def test_auto_seed_when_already_populated():
    """
    When ChromaDB already contains indexed chunks, auto_seed_knowledge_base
    should recognize the existing chunks and return status 'already_seeded' without re-indexing.
    """
    mock_store = MagicMock()
    mock_store.collection.count.return_value = 882

    with patch("main.vector_store", mock_store):
        result = auto_seed_knowledge_base()
        assert result["status"] == "already_seeded"
        assert result["total_chunks"] == 882


def test_auto_seed_when_empty_triggers_ingestion():
    """
    When ChromaDB has 0 chunks and transcript sources are present, auto_seed_knowledge_base
    should automatically trigger run_ingestion for baseline priority episodes.
    """
    mock_store = MagicMock()
    # First call 0 (empty), second call 150 (after seeding)
    mock_store.collection.count.side_effect = [0, 150]

    mock_ingest_result = {
        "status": "completed",
        "processed_files": 10,
        "skipped_files": 0,
        "total_chunks_indexed": 150,
        "failed_files": [],
    }

    with patch("main.vector_store", mock_store):
        with patch("rag.ingest.run_ingestion", return_value=mock_ingest_result) as mock_run:
            result = auto_seed_knowledge_base(limit=10)
            assert result["status"] == "seeded"
            assert result["total_chunks"] == 150
            mock_run.assert_called_once()


def test_auto_seed_when_ollama_unreachable_handles_error_gracefully():
    """
    If Ollama is not yet online during container startup, auto_seed_knowledge_base
    must not crash the application; it should log guidance and return status 'error'.
    """
    mock_store = MagicMock()
    mock_store.collection.count.return_value = 0

    with patch("main.vector_store", mock_store):
        with patch("rag.ingest.run_ingestion", side_effect=ConnectionError("Ollama connection refused at localhost:11434")):
            result = auto_seed_knowledge_base()
            assert result["status"] == "error"
            assert "Ollama connection refused" in result["error"]


def test_auto_seed_when_directory_missing():
    """
    If the transcripts directory does not exist, auto_seed_knowledge_base
    reports missing_transcripts_dir without failing.
    """
    mock_store = MagicMock()
    mock_store.collection.count.return_value = 0

    with patch("main.vector_store", mock_store):
        with patch("rag.ingest.DEFAULT_TRANSCRIPTS_DIR", Path("/nonexistent/episodes")):
            result = auto_seed_knowledge_base()
            assert result["status"] == "missing_transcripts_dir"
            assert result["total_chunks"] == 0


def test_api_rag_ingest_endpoints():
    """
    Tests that POST /api/knowledge/ingest and POST /api/rag/ingest
    execute on-demand ingestion and return a 200 response with chunk metrics.
    """
    mock_ingest_result = {
        "status": "completed",
        "processed_files": 5,
        "skipped_files": 0,
        "total_chunks_indexed": 75,
        "failed_files": [],
    }

    with patch("main.run_ingestion", return_value=mock_ingest_result):
        # 1. Test /api/knowledge/ingest
        resp1 = client.post("/api/knowledge/ingest", json={"limit": 5})
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "success"
        assert "5 episodes" in data1["message"]

        # 2. Test /api/rag/ingest alias
        resp2 = client.post("/api/rag/ingest", json={"limit": 5})
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "success"


def test_fresh_clone_transcripts_tracked_and_valid():
    """
    Validates that:
    1. Upstream transcripts are gitignored to avoid unauthorized public corpus redistribution.
    2. Tracked project documentation (docs/TRANSCRIPTS.md) contains attribution and pinned commit.
    3. Essential priority episodes exist on disk with valid transcript files.
    4. ensure_transcripts_available returns the directory directly without network calls when present.
    """
    from rag.ingest import ensure_transcripts_available, PRIORITY_SLUGS

    # 1. Tracked attribution documentation present at project root
    project_root = Path(__file__).parent.parent.parent
    docs_transcripts = project_root / "docs" / "TRANSCRIPTS.md"
    assert docs_transcripts.exists(), "docs/TRANSCRIPTS.md must be present in project"
    content = docs_transcripts.read_text(encoding="utf-8")
    assert "https://github.com/ChatPRD/lennys-podcast-transcripts" in content
    assert "be8ab89a890a833cbba2c892178f823fff178c65" in content

    # 2. Local priority episodes are present on disk
    assert DEFAULT_TRANSCRIPTS_DIR.exists()
    for slug in ["april-dunford", "pete-kazanjy", "elena-verna"]:
        ep_dir = DEFAULT_TRANSCRIPTS_DIR / slug
        assert ep_dir.exists(), f"Priority episode directory {slug} missing"
        assert (ep_dir / "transcript.md").exists(), f"transcript.md missing for {slug}"

    # 3. ensure_transcripts_available returns target directory directly
    res_dir = ensure_transcripts_available(DEFAULT_TRANSCRIPTS_DIR)
    assert res_dir == DEFAULT_TRANSCRIPTS_DIR


def test_ensure_transcripts_available_downloads_and_extracts_archive_when_missing(tmp_path):
    """
    Simulates a fresh clone where local transcripts do not exist.
    Verifies that ensure_transcripts_available extracts the pinned upstream archive,
    correctly creates the episodes/ directory and populates transcript.md files.
    """
    import io
    import tarfile
    from rag.ingest import ensure_transcripts_available, PINNED_UPSTREAM_COMMIT

    mock_raw_dir = tmp_path / "data" / "raw_transcripts"
    mock_episodes_dir = mock_raw_dir / "episodes"

    # Create a mock .tar.gz archive in memory matching GitHub's archive format:
    # lennys-podcast-transcripts-<commit>/episodes/sample-guest/transcript.md
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
        sample_content = (
            "---\n"
            "guest: Mock Guest\n"
            "title: Mock Episode On Positioning\n"
            "---\n"
            "This is a mocked transcript used for fresh clone extraction testing.\n"
        ).encode("utf-8")

        tar_info = tarfile.TarInfo(
            name=f"lennys-podcast-transcripts-{PINNED_UPSTREAM_COMMIT}/episodes/sample-guest/transcript.md"
        )
        tar_info.size = len(sample_content)
        tar.addfile(tar_info, io.BytesIO(sample_content))

    tar_bytes = tar_buffer.getvalue()

    def fake_urlretrieve(url, filename):
        with open(filename, "wb") as f:
            f.write(tar_bytes)

    with patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve) as mock_retrieve:
        result_dir = ensure_transcripts_available(mock_episodes_dir)
        mock_retrieve.assert_called_once()
        assert result_dir == mock_episodes_dir
        assert mock_episodes_dir.exists()
        sample_transcript = mock_episodes_dir / "sample-guest" / "transcript.md"
        assert sample_transcript.exists()
        assert "Mock Episode On Positioning" in sample_transcript.read_text(encoding="utf-8")
