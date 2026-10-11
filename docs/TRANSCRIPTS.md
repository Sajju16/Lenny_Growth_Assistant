# Lenny's Podcast Transcripts — Attribution & Source Data

## Upstream Source & Attribution
The transcripts used by Lenny Growth Assistant are sourced from the open-source community archive:
- **Upstream Repository:** [https://github.com/ChatPRD/lennys-podcast-transcripts](https://github.com/ChatPRD/lennys-podcast-transcripts)
- **Pinned Upstream Commit:** `be8ab89a890a833cbba2c892178f823fff178c65`
- **Archive Tarball:** `https://github.com/ChatPRD/lennys-podcast-transcripts/archive/be8ab89a890a833cbba2c892178f823fff178c65.tar.gz`
- **Original Content Creator:** [Lenny's Podcast](https://www.youtube.com/@LennysPodcast) hosted by Lenny Rachitsky
- **License / Terms:** Personal and educational use. All copyright and content ownership belongs to Lenny's Podcast and the interviewed guests.

## Fresh-Clone & Docker Ingestion Workflow
To respect upstream rights and avoid checking large third-party media corpora into public git history:
1. **Source Transcripts Are Ignored by Git:** The `backend/data/raw_transcripts/` directory is gitignored and is never committed to the public repository.
2. **Deterministic On-Demand Download:** The ingestion module (`backend/rag/ingest.py`) implements `ensure_transcripts_available()`.
   - On a fresh clone where `backend/data/raw_transcripts/` is absent, running `auto_seed_knowledge_base()` on backend startup, calling `POST /api/rag/ingest`, or running `python -m rag.ingest` automatically downloads and unpacks the pinned release archive (`be8ab89a890a833cbba2c892178f823fff178c65`) from GitHub into `backend/data/raw_transcripts/`.
   - Once present locally, ingestion reads directly from local disk with zero network overhead.
   - Vector embeddings are then computed locally via `nomic-embed-text` and stored in ChromaDB.
