import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
import chromadb
from chromadb.config import Settings
from .chunker import TranscriptChunk

logger = logging.getLogger("lenny-growth-backend.rag")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
CHROMA_DIR = os.getenv("CHROMA_DIR", str(Path(__file__).parent.parent / "data" / "chroma_db"))
COLLECTION_NAME = "lenny_podcast_transcripts"


class OllamaEmbeddingClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = EMBEDDING_MODEL):
        self.base_url = base_url
        self.model = model

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates 768-dim embeddings for a batch of strings using local Ollama nomic-embed-text.
        """
        if not texts:
            return []

        url = f"{self.base_url}/api/embed"
        payload = {
            "model": self.model,
            "input": texts,
        }

        try:
            with httpx.Client(timeout=90.0) as client:
                res = client.post(url, json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"Ollama embedding failed ({res.status_code}): {res.text}")
                data = res.json()
                embeddings = data.get("embeddings", [])
                if len(embeddings) != len(texts):
                    raise RuntimeError(f"Expected {len(texts)} embeddings, received {len(embeddings)}")
                return embeddings
        except httpx.ConnectError:
            raise RuntimeError(f"Cannot connect to Ollama at {self.base_url}. Ensure Ollama is running.")
        except Exception as exc:
            raise RuntimeError(f"Failed generating Ollama embeddings: {exc}")


class VectorStore:
    def __init__(self, persist_dir: str = CHROMA_DIR, collection_name: str = COLLECTION_NAME):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedder = OllamaEmbeddingClient()

        # Ensure storage directory exists
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def upsert_chunks(self, chunks: List[TranscriptChunk], batch_size: int = 30) -> int:
        """
        Generates embeddings in batches and upserts into ChromaDB.
        Avoids duplicates by using chunk_id.
        """
        if not chunks:
            return 0

        total_upserted = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.text for c in batch]
            ids = [c.chunk_id for c in batch]
            metadatas = [
                {
                    "episode_slug": c.episode_slug,
                    "guest": c.guest,
                    "title": c.title,
                    "youtube_url": c.youtube_url,
                    "publish_date": c.publish_date,
                    "source_file": c.source_file,
                    "chunk_index": c.chunk_index,
                }
                for c in batch
            ]

            embeddings = self.embedder.get_embeddings(texts)

            self.collection.upsert(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
                embeddings=embeddings,
            )
            total_upserted += len(batch)
            logger.info("Indexed batch of %d chunks (total: %d)", len(batch), total_upserted)

        return total_upserted

    def query(self, query_text: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Embeds the query text and retrieves top_k most similar chunks.
        """
        query_embedding = self.embedder.get_embeddings([query_text])[0]

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        output = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return output

        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results.get("distances", [[]])[0]

        for idx, chunk_id in enumerate(ids):
            meta = metas[idx] or {}
            dist = distances[idx] if idx < len(distances) else 1.0
            # For cosine distance in chromadb, score = 1.0 - distance
            similarity = max(0.0, 1.0 - dist)

            output.append({
                "chunk_id": chunk_id,
                "text": docs[idx],
                "guest": meta.get("guest", "Unknown"),
                "title": meta.get("title", "Untitled Episode"),
                "youtube_url": meta.get("youtube_url", ""),
                "publish_date": meta.get("publish_date", ""),
                "source_file": meta.get("source_file", ""),
                "distance": dist,
                "similarity_score": round(similarity, 4),
            })

        return output

    def get_stats(self) -> Dict[str, Any]:
        """
        Returns stats about the vector store.
        """
        try:
            total_count = self.collection.count()
            # Sample up to 1000 items to count unique episodes
            all_metas = self.collection.get(include=["metadatas"], limit=1000)
            episodes = set()
            if all_metas and all_metas.get("metadatas"):
                for m in all_metas["metadatas"]:
                    if m and m.get("episode_slug"):
                        episodes.add(m["episode_slug"])

            return {
                "collection_name": self.collection_name,
                "total_chunks": total_count,
                "indexed_episodes_count": len(episodes),
                "embedding_model": EMBEDDING_MODEL,
                "storage_path": self.persist_dir,
                "is_ready": total_count > 0,
            }
        except Exception as exc:
            return {
                "collection_name": self.collection_name,
                "total_chunks": 0,
                "indexed_episodes_count": 0,
                "embedding_model": EMBEDDING_MODEL,
                "storage_path": self.persist_dir,
                "is_ready": False,
                "error": str(exc),
            }
