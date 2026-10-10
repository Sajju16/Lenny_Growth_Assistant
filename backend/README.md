# Lenny Growth Assistant — Backend & Knowledge Base

This service powers the intelligence, conversation persistence, skill execution, and agent reasoning layer for the **Lenny Growth Assistant**. It couples a high-performance **FastAPI** gateway with **PostgreSQL** conversation and artifact persistence, pluggable **LLM Provider switching** (local **Ollama** and cloud **Anthropic Claude**), an autonomous **Claude Agent SDK** integration, a dedicated **"Ship 30 for 30" Essay Skill**, and a **Sandboxed HTML Artifact Generator**.

---

## Architecture Overview

```
                      ┌───────────────────────────────────────────────┐
                      │          React + Vite Frontend (3000)          │
                      └───────────────────────┬───────────────────────┘
                                              │ HTTP JSON
                                              ▼
                      ┌───────────────────────────────────────────────┐
                      │             FastAPI Backend (8000)            │
                      │  • GET /health (Postgres, Ollama, Anthropic)  │
                      │  • GET/POST/PATCH/DELETE /api/conversations   │
                      │  • GET/POST/DELETE /api/artifacts             │
                      │  • POST /api/skills/essay (Ship 30 for 30)    │
                      │  • GET /api/knowledge/status                  │
                      │  • POST /api/chat (Provider / Agent + RAG)    │
                      └───────┬───────────────┬───────────────┬───────┘
                              │               │               │
        Conversations/Messages│               │Semantic Search│
                              ▼               ▼               ▼
           ┌─────────────────────┐ ┌────────────────────┐ ┌───────────────────────────┐
           │     PostgreSQL      │ │  ChromaDB Store    │ │   LLM Provider Layer      │
           │  (lenny_growth_db)  │ │ (backend/data/     │ │ • OllamaProvider (Local)  │
           │  • conversations    │ │  chroma_db)        │ │ • AnthropicProvider (Cloud│
           │  • messages (JSON)  │ │ • Cosine Sim>=0.35 │ │ • ClaudeTranscriptAgent   │
           │  • artifacts (table)│ └────────────────────┘ └───────────────────────────┘
           └─────────────────────┘
```

---

## 1. "Ship 30 for 30" Essay Skill (Phase 4)

Located in `backend/skills/essay_skill.py`:
- **Function:** `generate_ship30_essay(topic, provider, retriever, conversation_id, db)`
- **Structure:**
  - Atomic headline promising clear transformation.
  - Compelling opening hook exposing common startup failures.
  - 3–5 logical narrative sections with H2/H3 headers.
  - Skimmable paragraphs with bold terms.
  - Concrete "Monday Morning Action Plan" takeaways.
  - Approximately 1,250 words target length.
- **Strict Evidence Grounding:** All claims and advice are grounded in retrieved Lenny's Podcast transcript chunks. If evidence is insufficient, explicitly discloses limitations instead of inventing citations.
- **Dual Persistence:** Automatically saved as a message in the conversation session and as a dynamic Markdown artifact in PostgreSQL.
- **Dedicated Endpoint:** `POST /api/skills/essay`

---

## 2. Dynamic Artifact Architecture & Endpoints (Phase 4)

Located in `backend/artifacts/` and `backend/database/models.py`:
- **Model:** `Artifact` table linked via foreign key to `Conversation`.
- **Supported Types:** Explicit `'markdown'` and `'html'`.
- **Endpoints:**
  - `POST /api/artifacts`: Create a new dynamic artifact.
  - `GET /api/artifacts/{id}`: Retrieve a specific artifact.
  - `GET /api/conversations/{id}/artifacts`: List all artifacts created in a conversation.
  - `DELETE /api/artifacts/{id}`: Delete an artifact.
- **Chat Separation:** Standard chat responses do **not** create artifacts. Artifacts are only created when `create_artifact=true` or `skill="essay"`.

---

## 3. Secure HTML Sanitization & Sandboxing (Phase 4)

Located in `backend/artifacts/sanitizer.py`:
- **Threat Neutralization:**
  - Strips `<script>` tags, `<object>`, `<embed>`, `<iframe>`.
  - Neutralizes inline event handlers (`onclick`, `onerror`, `onload`, `onmouseover`, etc.).
  - Strips `javascript:` URIs.
- **Document Encapsulation:** Wraps snippets into self-contained HTML documents with isolated typography and styles.
- **Security Flagging:** Returns `(is_safe, sanitized_html, warnings)`. Unsafe inputs have `is_safe=False` and trigger UI security warnings.
- **Client Sandboxing:** Rendered exclusively in `<iframe sandbox="allow-popups">` with no script execution and opaque origin.

---

## 4. Configurable LLM Providers (Phase 3B)

The LLM layer is decoupled via `llm.base.BaseLLMProvider`:
- **`OllamaProvider` (Default Local Runtime):** Uses local Ollama at `http://localhost:11434` with `qwen2.5:3b`.
- **`AnthropicProvider` (Cloud Frontier LLM):** Uses official `anthropic` SDK with `claude-3-5-sonnet-20241022`. Requires `ANTHROPIC_API_KEY`.
- **`ClaudeTranscriptAgent` (Autonomous Agent):** Agent executing `search_lenny_transcripts` tool over ChromaDB.

Set `LLM_PROVIDER` in `backend/.env`:
```ini
LLM_PROVIDER=ollama
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

---

## 5. PostgreSQL Persistence (Phase 3A)

Ensure PostgreSQL is running locally on port 5432:
```powershell
psql -U postgres -h 127.0.0.1 -c "CREATE DATABASE lenny_growth_db;"
```

Configure `DATABASE_URL` in `.env`:
```ini
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/lenny_growth_db
```

---

## 6. Running & Ingestion

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Ingest podcast transcripts into ChromaDB
python -m rag.ingest --limit 10

# Start FastAPI server
$env:PYTHONPATH=".;.venv\Lib\site-packages"; python -m uvicorn main:app --reload --port 8000 --host 127.0.0.1
```

---

## 7. Automated Tests (55 Tests Passing)

Run the automated test suite:
```powershell
$env:PYTHONPATH=".;.venv\Lib\site-packages"; python -m pytest tests/ -v
```

All 55 tests pass:
- **`test_essay_skill.py` (4 tests):** Title extraction, essay generation with citations, insufficient evidence handling, `/api/skills/essay` endpoint.
- **`test_artifacts.py` (8 tests):** HTML sanitization, script removal, inline handler neutralization, Markdown/HTML artifact CRUD, chat artifact boundary.
- **`test_providers.py` (8 tests):** Provider factory, key validation, health checks, mock Anthropic generation, fallback prevention.
- **`test_agent.py` (5 tests):** Agent tool schema, execution boundaries, multi-turn loop, missing key handling.
- **`test_provider_persistence.py` (1 test):** Session isolation, message and citation persistence in PostgreSQL.
- **`test_database.py` (6 tests):** CRUD operations, cascade deletion, JSON citations.
- **`test_conversations_api.py` (6 tests):** FastAPI conversation REST endpoints.
- **`test_postgres_real.py` (1 test):** Live PostgreSQL connection verification.
- **`test_parser.py`, `test_chunker.py`, `test_retriever.py`, `test_api.py` (16 tests):** RAG parsing, chunking, retrieval, and health.
