import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from .parser import parse_transcript_file
from .chunker import chunk_transcript
from .vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("lenny-growth-backend.ingest")

DEFAULT_TRANSCRIPTS_DIR = Path(__file__).parent.parent / "data" / "raw_transcripts" / "episodes"

# Curated list of high-affinity growth episodes prioritized for fast baseline indexing
PRIORITY_SLUGS = [
    "pete-kazanjy",
    "elena-verna",
    "rahul-vohra",
    "patrick-campbell",
    "sean-ellis",
    "dan-hockenmaier",
    "casey-winters",
    "brian-balfour",
    "hila-qu",
    "brian-chesky",
    "april-dunford",
    "nikita-bier",
    "shreyas-doshi",
    "marty-cagan",
    "gina-gotthilf",
    "darius-contractor",
    "pat-campbell",
]


PINNED_UPSTREAM_COMMIT = "be8ab89a890a833cbba2c892178f823fff178c65"
PINNED_UPSTREAM_REPO = "https://github.com/ChatPRD/lennys-podcast-transcripts"
PINNED_TARBALL_URL = f"https://github.com/ChatPRD/lennys-podcast-transcripts/archive/{PINNED_UPSTREAM_COMMIT}.tar.gz"


def ensure_transcripts_available(transcripts_dir: Optional[Path] = None) -> Path:
    """
    Ensures that the episodes transcript directory exists. If local files are present,
    returns target_dir immediately with zero network overhead. If absent in an ultra-sparse
    clone, securely fetches and unpacks the pinned upstream release archive from GitHub.
    """
    target_dir = Path(transcripts_dir or DEFAULT_TRANSCRIPTS_DIR)
    if target_dir.exists() and any(target_dir.glob("**/transcript.md")):
        return target_dir

    logger.info("Local transcripts missing at %s. Attempting download from pinned upstream release: %s", target_dir, PINNED_TARBALL_URL)
    raw_dir = target_dir.parent  # backend/data/raw_transcripts
    raw_dir.mkdir(parents=True, exist_ok=True)

    import urllib.request
    import tarfile
    import tempfile
    import shutil

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
    try:
        urllib.request.urlretrieve(PINNED_TARBALL_URL, tmp_path)
        with tarfile.open(tmp_path, "r:gz") as tar:
            extract_dir = raw_dir / "temp_extract"
            if hasattr(tarfile, "data_filter"):
                tar.extractall(path=extract_dir, filter="data")
            else:
                tar.extractall(path=extract_dir)
            extracted_roots = list(extract_dir.glob("lennys-podcast-transcripts-*"))
            if extracted_roots:
                src_root = extracted_roots[0]
                for item in src_root.iterdir():
                    dest = raw_dir / item.name
                    if not dest.exists():
                        shutil.move(str(item), str(dest))
            shutil.rmtree(extract_dir, ignore_errors=True)
    except Exception as exc:
        logger.warning("Failed to fetch pinned upstream transcripts archive: %s", exc)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return target_dir


def run_ingestion(
    transcripts_dir: Optional[Path] = None,
    limit: Optional[int] = 15,
    prioritize: bool = True,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    batch_size: int = 30,
) -> Dict[str, Any]:
    """
    Ingests transcript markdown files into ChromaDB.
    Avoids duplicate chunks by relying on deterministic chunk IDs.
    """
    data_dir = ensure_transcripts_available(transcripts_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Transcripts directory not found: {data_dir}")

    logger.info("Scanning for transcript files in: %s", data_dir)
    vector_store = VectorStore()

    # Collect all transcript.md files
    all_files: List[Path] = []
    for root, _, files in os.walk(data_dir):
        for f in files:
            if f.lower() == "transcript.md":
                all_files.append(Path(root) / f)

    if not all_files:
        logger.warning("No transcript.md files discovered in %s", data_dir)
        return {
            "status": "empty",
            "processed_files": 0,
            "skipped_files": 0,
            "total_chunks": 0,
            "failed_files": [],
        }

    # Sort files, putting priority episodes first if requested
    if prioritize:
        priority_files = []
        other_files = []
        for p in all_files:
            slug = p.parent.name.lower()
            if any(pref in slug for pref in PRIORITY_SLUGS):
                priority_files.append(p)
            else:
                other_files.append(p)
        sorted_files = priority_files + other_files
    else:
        sorted_files = sorted(all_files, key=lambda p: p.parent.name)

    # Apply limit if specified
    target_files = sorted_files[:limit] if (limit and limit > 0) else sorted_files
    logger.info("Selected %d transcript files for ingestion (out of %d discovered)", len(target_files), len(all_files))

    processed_count = 0
    skipped_count = 0
    total_chunks = 0
    failed_files = []

    for file_path in target_files:
        try:
            doc = parse_transcript_file(file_path)
            if not doc:
                skipped_count += 1
                logger.debug("Skipped non-transcript or empty file: %s", file_path)
                continue

            chunks = chunk_transcript(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            if not chunks:
                skipped_count += 1
                continue

            upserted = vector_store.upsert_chunks(chunks, batch_size=batch_size)
            total_chunks += upserted
            processed_count += 1
            logger.info("Ingested '%s' (%s) -> %d chunks", doc.title, doc.guest, upserted)

        except Exception as exc:
            logger.error("Failed ingesting %s: %s", file_path, exc)
            failed_files.append({"file": str(file_path), "error": str(exc)})

    stats = vector_store.get_stats()
    result = {
        "status": "completed",
        "processed_files": processed_count,
        "skipped_files": skipped_count,
        "total_chunks_indexed": total_chunks,
        "failed_files": failed_files,
        "vector_store_stats": stats,
    }
    logger.info("Ingestion finished: %s", result)
    return result


def main():
    parser = argparse.ArgumentParser(description="Ingest Lenny's Podcast transcripts into ChromaDB")
    parser.add_argument("--dir", type=str, default=str(DEFAULT_TRANSCRIPTS_DIR), help="Path to episodes directory")
    parser.add_argument("--limit", type=int, default=15, help="Number of episodes to index (0 for all)")
    parser.add_argument("--all", action="store_true", help="Index all episodes without limit")
    args = parser.parse_args()

    limit = None if args.all else (args.limit if args.limit > 0 else None)
    res = run_ingestion(transcripts_dir=Path(args.dir), limit=limit)
    print("\n=== Ingestion Summary ===")
    print(f"Processed Episodes: {res['processed_files']}")
    print(f"Chunks Indexed:     {res['total_chunks_indexed']}")
    print(f"Total in Store:     {res['vector_store_stats'].get('total_chunks', 0)}")
    print(f"Embedding Model:    {res['vector_store_stats'].get('embedding_model')}")
    print(f"Chroma Directory:   {res['vector_store_stats'].get('storage_path')}")


if __name__ == "__main__":
    main()
