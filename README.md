# Lenny Growth Assistant — Executive Product Intelligence, Essay Skill & Dynamic Artifacts

An executive-tier growth advisory workstation combining high-density product strategy workflows with a **local-first RAG knowledge base** indexed on *Lenny's Podcast* transcripts, **PostgreSQL persistent conversation sessions**, **pluggable Cloud LLM provider switching (Ollama, Anthropic Claude & Google Gemini)**, an **autonomous Claude Agent**, a dedicated **"Ship 30 for 30" Essay Skill**, and **Real Dynamic Artifact Generation with a Sandboxed HTML Preview**.

Powered by **React + Vite**, **FastAPI**, **PostgreSQL**, **Ollama (`qwen2.5:3b`)**, **Anthropic Claude (`claude-3-5-sonnet-20241022`)**, **Google Gemini (`gemini-2.5-flash`)**, **Claude Agent SDK**, and **ChromaDB**.

---

## Key Features

- **"Ship 30 for 30" Essay Skill (Phase 4):** Dedicated, reusable long-form essay module that generates structured, approximately 1,250-word executive essays. Features an atomic headline, opening hook exposing common startup pitfalls, coherent narrative arc with skimmable H2/H3 headers, bold conceptual emphasis, strict podcast guest attribution, and a concrete "Monday Morning Action Plan". Discloses limitations if evidence is insufficient.
- **Real Dynamic Artifact Generation (Phase 4):** Full replacement of static mock artifacts with real model-synthesized Markdown and HTML documents. Artifacts are automatically persisted in PostgreSQL (`artifacts` table), linked to conversations, and restored across browser sessions or conversation switches. Normal chat responses never accidentally become artifacts.
- **Secure Sandboxed HTML Preview (Phase 4):** Model-generated HTML is treated as untrusted input. Rendered exclusively in an isolated `iframe` with `sandbox="allow-popups"` (strictly **no** `allow-scripts`, **no** `allow-same-origin`). Automatically sanitizes `<script>` tags, inline event handlers (`onclick=`, `onerror=`), and `javascript:` URIs. If unsafe markup is detected, displays a security alert banner and defaults to the source code view.
- **Configurable LLM Providers (Phase 3B+):** Clean provider abstraction decoupling generation from FastAPI routing. Seamlessly switch between local offline inference (`OllamaProvider` with `qwen2.5:3b`), cloud frontier intelligence (`AnthropicProvider` with `claude-3-5-sonnet-20241022`), and **Google Gemini** (`GeminiProvider` with `gemini-2.5-flash`, free tier — no billing required) via `LLM_PROVIDER=ollama|anthropic|gemini`.
- **Assignment-Required Agent Layer (Phase 3B):** Autonomous `ClaudeTranscriptAgent` with an explicit, secure `search_lenny_transcripts` tool. Strict tool boundaries prevent arbitrary shell or filesystem access.
- **PostgreSQL Session Persistence (Phase 3A):** Every conversation session, user prompt, assistant response, verified citation array, and dynamic artifact is persisted in PostgreSQL.
- **Local Diagnostics:** Real-time `/health` diagnostics monitor FastAPI, PostgreSQL, Ollama runtime, ChromaDB vector store, Anthropic configuration status, and Gemini configuration status.

---

## Architecture

```
┌──────────────────────────────────────────────┐                HTTP JSON
│           React + Vite (Port 3000)           │ ◄────────────────────────────────────────► ┌────────────────────────────────────────┐
│  • 3-Panel Executive UX                      │                                            │      FastAPI Backend (Port 8000)       │
│  • Dynamic Artifact Viewer                   │                                            │  • /health, /api/chat                  │
│  • Sandboxed HTML iframe (No script access)  │                                            │  • /api/conversations (CRUD)           │
│  • Mode Selector (Chat, Essay, HTML Artifact)│                                            │  • /api/skills/essay (Ship 30 for 30)  │
│  • Verifiable Citation Badges & Excerpts     │                                            │  • /api/artifacts (CRUD & Sandbox)     │
└──────────────────────────────────────────────┘                                            └───────┬───────────────┬────────────────┘
                                                                                                    │               │
                                                           Conversations, Messages, & Artifacts     │               │Semantic Search
                                                                                                    ▼               ▼
                                                                                 ┌─────────────────────┐ ┌───────────────────────────┐
                                                                                 │     PostgreSQL      │ │      ChromaDB Store       │
                                                                                 │  (lenny_growth_db)  │ │   (backend/data/chroma_db)│
                                                                                 │  • conversations    │ │  • 882 Chunks Indexed     │
                                                                                 │  • messages (JSON)  │ │  • Cosine Sim >= 0.35     │
                                                                                 │  • artifacts (table)│ └───────────────────────────┘
                                                                                 └─────────────────────┘
                                                                                                    ▲
                                                                                                    │
                                                  ┌─────────────────────────────────────────────────┴───────────────────────────────┐
                                                  ▼                                                                                 ▼
                                    ┌───────────────────────────┐                                                     ┌───────────────────────────┐
                                    │    Local LLM Provider     │                                                     │   Cloud Provider / Agent  │
                                    │      (OllamaProvider)     │                                                     │    (Anthropic & Claude    │
                                    │  • qwen2.5:3b (Offline)   │                                                     │       Agent SDK)          │
                                    │  • nomic-embed-text       │                                                     │  • claude-3-5-sonnet      │
                                    │  • Local Grounded Prompt  │                                                     │  • search_lenny_transcripts│
                                    └───────────────────────────┘                                                     └───────────────────────────┘
```

---

## 1. "Ship 30 for 30" Essay Skill

### How to Request
1. **Via UI Mode Pill:** Click the **"Ship 30 for 30 Essay"** mode chip above the prompt composer and type your topic (e.g., `"Founder-led sales and positioning playbooks"`).
2. **Via Chat Slash Command:** Start your prompt with `/essay <topic>` (e.g., `/essay How to price B2B SaaS products`).
3. **Via Empty State Button:** In the Artifact Viewer, click the **"Generate Ship 30 for 30 Essay"** action button.
4. **Via Dedicated API Endpoint:**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/skills/essay \
     -H "Content-Type: application/json" \
     -d '{"topic": "Product positioning frameworks", "conversation_id": "session-123"}'
   ```

### Requirements & Behavior
- **Length:** Synthesizes an essay of approximately 1,250 words.
- **Structure:** Atomic title, compelling opening hook, 3–5 logical narrative sections with H2/H3 headings, skimmable paragraphs with bold terms, and a practical **"Monday Morning Action Plan"** takeaway.
- **Strict Grounding:** Grounded solely in verified podcast transcript evidence from ChromaDB. Attributed to specific guests (e.g., April Dunford, Peter Kazanjy, Elena Verna).
- **Insufficient Evidence Handling:** If no relevant transcript evidence exists, refuses to invent advice and discloses the limitation:
  `"Based on the verified podcast transcripts currently indexed in the knowledge base, there is insufficient evidence to write a comprehensive 'Ship 30 for 30' essay on [topic]."`
- **Persistence:** Persisted simultaneously as an assistant chat message and as a dynamic Markdown artifact linked to the conversation session.

---

## 2. Dynamic Artifact Generation & Viewer

### Dynamic vs. Static Artifacts
- Static mock artifacts are replaced with dynamically generated artifacts saved in PostgreSQL.
- Ordinary chat responses do **not** become artifacts unless explicitly requested via `create_artifact: true` or `skill="essay"`.
- Supports explicit artifact types: `markdown` and `html`.

### Artifact Viewer Features
- **Executive Preview Tab:** Renders clean typography, headers, bold emphasis, blockquotes, and verified podcast citations.
- **Source Code Tab:** Shows raw Markdown or HTML with 1-click Copy and Download.
- **Empty State:** When a conversation has no artifact, shows an executive empty canvas with a direct button to generate a Ship 30 for 30 essay.
- **PostgreSQL Restoration:** Switching conversations seamlessly retrieves that session's active artifact and message history from PostgreSQL.

### Artifact Database Schema
The `artifacts` table includes:
- `id`: Unique identifier (e.g. `art-ced3f59797db`).
- `conversation_id`: Foreign key linked to `conversations.id`.
- `title`, `subtitle`, `badge`, `file_name`: Display metadata.
- `artifact_type`: `'markdown'` or `'html'`.
- `content`: Full text content (Markdown or sanitized HTML).
- `word_count`, `read_time`: Document metrics.
- `is_safe`: Boolean security flag.
- `security_warnings`: Array of neutralized threats (JSON).
- `citations`: Verified podcast citation references (JSON).
- `created_at`, `updated_at`: Timestamps.

---

## 3. Secure Sandboxed HTML Preview

### Security Rules
1. **Zero Main DOM Injection:** Model-generated HTML is **never** injected via `dangerouslySetInnerHTML` into the main application.
2. **Iframe Sandboxing:** Rendered strictly in a sandboxed `<iframe>`:
   ```html
   <iframe
     srcdoc="..."
     sandbox="allow-popups"
     title="HTML Artifact Preview"
   />
   ```
   - **`allow-scripts` is omitted:** Disables JavaScript execution inside the iframe.
   - **`allow-same-origin` is omitted:** Treats content as a unique opaque origin, preventing access to `document.cookie`, `localStorage`, `sessionStorage`, indexedDB, or parent window DOM.
3. **Backend & Frontend Sanitization:**
   - Strips `<script>` tags, `<object>`, `<embed>`, and `<iframe>` embeds.
   - Neutralizes inline event handlers (`onclick`, `onerror`, `onload`, `onmouseover`, etc.).
   - Disallows dangerous protocols like `javascript:`.
4. **Security Notice Banner:**
   - When unsafe markup is detected, `is_safe` is marked `false`.
   - The UI displays an amber warning banner:
     *"Security Notice: Untrusted Markup Neutralized. Model-generated HTML contained disallowed scripts or event handlers."*
   - Defaults to the source code inspection tab with an option to preview the sanitized markup.

---

## 4. Configuration & Environment Variables

Copy `.env.example` to `backend/.env` or the project root:

```ini
# Database Configuration (PostgreSQL)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/lenny_growth_db

# Ollama Local LLM & Embedding Settings
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_MODEL=qwen2.5:3b
EMBEDDING_MODEL=nomic-embed-text

# LLM Provider Configuration ('ollama', 'anthropic', or 'gemini')
LLM_PROVIDER=ollama

# Anthropic Cloud LLM Configuration (required when LLM_PROVIDER=anthropic)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Google Gemini Cloud LLM Configuration (required when LLM_PROVIDER=gemini)
# Obtain a free API key from https://aistudio.google.com/apikey (no billing required)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# API Server Settings
PORT=8000
HOST=127.0.0.1
```

> **Note on Provider Authentication:**
> - **Anthropic REST Provider (`LLM_PROVIDER=anthropic`):** Authenticates via standard `ANTHROPIC_API_KEY`.
> - **Google Gemini Provider (`LLM_PROVIDER=gemini`):** Authenticates via `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey). Free tier — no billing or payment method required.
> - **Claude Agent SDK (`claude-agent-sdk`, `use_agent=True`):** Integrates in-process SDK MCP tools and executes via the Claude Code runtime engine. Live un-mocked agent queries require an authenticated Claude Code session on the host machine (`claude login` / `/login`) in addition to `ANTHROPIC_API_KEY`. Without active runtime credentials, agent requests cleanly return `HTTP 401 Unauthorized`.

---

## 5. Setup & Local Run Instructions

### 1. Prerequisites
- **PostgreSQL** running on `localhost:5432` with database `lenny_growth_db`.
- **Ollama** installed with models: `ollama run qwen2.5:3b` and `ollama pull nomic-embed-text`.
- **Node.js** (v18+) and **Python** (3.11+).
- *(Optional for Live Claude Agent SDK execution)*: **Claude Code** installed and logged in (`claude login`).

### 2. Backend Setup
```powershell
# Open terminal in backend directory
cd backend

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run transcript ingestion (indexes podcast episodes into ChromaDB)
python -m rag.ingest --limit 10

# Start FastAPI server
python -m uvicorn main:app --reload --port 8000 --host 127.0.0.1
```

### 3. Frontend Setup
```powershell
# In project root
npm install
npm run dev
```
Visit [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Docker Compose Reproducible Startup

The repository includes a multi-container Docker Compose configuration (`docker-compose.yml`) enabling full-stack deployment:

```powershell
docker compose up --build
```

#### Services & Architecture:
- **`postgres` (Port 5432):** PostgreSQL 16 Alpine container storing session conversations, chat messages, and dynamic artifacts.
  - Health check: `pg_isready -U postgres -d lenny_growth_db` with interval 5s, timeout 3s, retries 5.
  - Volume: `postgres_data:/var/lib/postgresql/data` ensures data persistence across container rebuilds.
- **`backend` (Port 8000):** FastAPI application container connected to PostgreSQL and local/cloud LLMs.
  - Service readiness: Explicitly depends on `postgres` with `condition: service_healthy`.
  - ChromaDB Volume: Mounted specifically at `/app/data/chroma_db` (`chroma_data:/app/data/chroma_db`) with `CHROMA_DIR=/app/data/chroma_db`. This ensures vector persistence without masking raw source transcripts located at `/app/data/raw_transcripts/`.
  - Host Ollama Connectivity: Configured with `extra_hosts: ["host.docker.internal:host-gateway"]` and `OLLAMA_BASE_URL=http://host.docker.internal:11434`.
- **`frontend` (Port 3000):** Production React bundle served via Nginx with dedicated reverse proxy rules.
  - Depends on `backend` with `condition: service_started`.
  - **SSE Streaming Optimization:** Nginx routes `/api/chat/stream` with `proxy_buffering off;`, `proxy_cache off;`, `chunked_transfer_encoding on;`, and 600-second read/send timeouts to deliver instant token streaming without proxy buffering delays or gateway timeouts during long generation runs.
  - Standard REST API routes (`/api/`) are proxied with 120-second timeouts.

#### Fresh-Clone Startup & Knowledge Base Auto-Seeding:
- **Licensing & Clean Git History:** To respect upstream copyright and avoid committing 33+ MB of third-party podcast text, `backend/data/raw_transcripts/` is gitignored. Attribution and upstream repository details are tracked in `docs/TRANSCRIPTS.md`.
- **On-Demand Pinned Download:** On a fresh clone, `ensure_transcripts_available()` automatically retrieves and extracts the pinned upstream archive (`be8ab89a890a833cbba2c892178f823fff178c65`) into `backend/data/raw_transcripts/` before indexing.
- **Automatic Initialization:** On backend startup (`@app.on_event("startup")`), `auto_seed_knowledge_base()` inspects the ChromaDB vector store collection. If empty (`count == 0`), it automatically indexes high-value product, positioning, and growth episodes (April Dunford, Peter Kazanjy, Elena Verna, etc.) into ChromaDB embeddings using `nomic-embed-text`.
- **Graceful Deferral:** If the local Ollama daemon is offline or still downloading models during container boot, auto-seeding catches connection errors cleanly, logs an actionable notice, and lets FastAPI startup succeed without crashing.
- **On-Demand Ingestion:** Once Ollama is available, ingestion can be triggered at any time:
  ```bash
  # Via API endpoint (e.g. from container or curl)
  curl -X POST http://localhost:8000/api/rag/ingest -H "Content-Type: application/json" -d '{"limit": 15, "prioritize": true}'

  # Or directly via CLI in backend
  python -m rag.ingest --limit 15 --prioritize
  ```

---

## 6. Testing & Verification Results

### Automated Test Suite (120 Tests Passing)
Run the full test suite with `pytest`:
```powershell
$env:PYTHONPATH=".;.venv\Lib\site-packages"; python -m pytest tests/ -v
```

All **120 automated tests pass** with zero errors or regressions:
- **`test_startup_and_seed.py` (8 tests):** Validates raw transcript directory presence and parseability, auto-seed trigger when ChromaDB is empty, skip when already populated, graceful deferral when Ollama is unreachable, `/api/rag/ingest` endpoint behavior, gitignore exclusion verification, and mocked tarball archive extraction.
- **`test_streaming_and_latency.py` (19 tests):** Validates SSE token streaming, query embedding cache, tokens-per-second excluding TTFT, conversation history truncation, and streaming retrieval.
- **`test_timeouts.py` (6 tests):** Dedicated timeouts, artifact retry deduplication, message deduplication.
- **`test_essay_skill.py` (4 tests):** Headline extraction, 1,250-word calibration prompts, repetition penalty propagation, insufficient evidence disclosure, persistence.
- **`test_artifacts.py` (8 tests):** Safe HTML document wrapping, `<script>` removal, inline event handler neutralization (`onclick=`), `javascript:` URI neutralization, Markdown and HTML artifact APIs, non-artifact chat guarantee.
- **`test_providers.py` (8 tests):** Provider factory resolution (`ollama` vs `anthropic`), key validation, missing/placeholder key HTTP 400 error handling, health reporting, mocked Anthropic Claude generation, prevention of silent fallbacks.
- **`test_agent.py` (5 tests):** Claude Agent SDK integration, tool schema, execution against knowledge retriever, multi-turn synthesis loop.
- **`test_model_selection.py` (5 tests):** Dynamic model switching across `qwen2.5:1.5b` and `qwen2.5:3b`.
- **`test_database.py` (6 tests):** Deterministic secondary ordering, conversation CRUD, cascade message deletion, citation serialization.
- **`test_conversations_api.py` (6 tests):** Conversation REST endpoints.
- **`test_postgres_real.py` (1 test):** Live PostgreSQL integration.
- **`test_parser.py`, `test_chunker.py`, `test_retriever.py`, `test_api.py` (34 tests):** Frontmatter parsing, chunking, semantic retrieval, citations, health checks.

### Production Build Verification
```powershell
npm run build
```
Vite production build compiles cleanly: 1599 modules transformed in ~4.8s with zero warnings or errors.

---

## 7. Troubleshooting Guide

| Issue | Root Cause | Solution |
|---|---|---|
| **Ollama connection failed (`ConnectError`)** | Ollama is not running on localhost. | Start Ollama: `ollama run qwen2.5:3b`. Verify at `http://localhost:11434/api/tags`. |
| **Anthropic HTTP 400 Bad Request** | `ANTHROPIC_API_KEY` is missing or a placeholder. | Set your valid `sk-ant-...` key in `.env`, or switch to local Ollama with `LLM_PROVIDER=ollama`. |
| **Claude Agent HTTP 401 Unauthorized** | Claude Code runtime not logged in or invalid credentials. | Run `claude login` or ensure host environment has authenticated Claude Code credentials. |
| **PostgreSQL connection refused** | Database server is stopped or database is not created. | Run `psql -U postgres -c "CREATE DATABASE lenny_growth_db;"` and verify port 5432. |
| **Docker backend cannot reach host Ollama** | Container networking on Windows. | Ensure `OLLAMA_BASE_URL=http://host.docker.internal:11434` and `extra_hosts: ["host.docker.internal:host-gateway"]` in `docker-compose.yml`. |
| **Windows PowerShell venv script execution error** | Execution policy restriction. | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` before activating `.venv`. |

---

## 8. 2–3 Minute Camera-On YouTube Demo Script

Follow this structured script when recording your submission video:

### [0:00 – 0:30] Introduction & Local RAG Workstation
- **Camera:** Camera on, screen showing `http://localhost:3000`.
- **Script:** *"Hi, I'm presenting the Lenny Growth Assistant for the Oogway Labs Forward Deployed Engineer take-home. This is an executive strategy workstation that grounds AI generation in verified podcast transcripts from Lenny's Podcast. Notice the three-panel layout: session history on the left, grounded conversation in the middle, and the dynamic Artifact Viewer on the right. Notice in the header that our PostgreSQL database is online and we're currently running on our local offline Ollama model `qwen2.5:3b` with zero cloud egress."*

### [0:30 – 1:05] Grounded Retrieval & Verifiable Citations
- **Action:** Ask: *"According to April Dunford, what are the key steps for crafting a winning sales pitch?"*
- **Script:** *"When I submit this query, the FastAPI backend queries ChromaDB containing 882 indexed chunks. Notice the response: it directly cites April Dunford, provides the episode number, a direct quote excerpt, and a link to the original YouTube episode. Now let's ask an out-of-scope question about semiconductor manufacturing: notice that instead of hallucinating, the assistant immediately discloses that there is insufficient transcript evidence."*

### [1:05 – 1:45] "Ship 30 for 30" Essay Skill & Dynamic Artifacts
- **Action:** Select the `✨ Ship 30 for 30 Essay` mode chip and enter: *"Product positioning and competitive differentiation"*.
- **Script:** *"Now, let's trigger our dedicated 'Ship 30 for 30' essay skill. This generates an approximately 1,250-word structured executive essay with an atomic headline, opening hook, H2/H3 headers, and a practical Monday Morning Action Plan. Notice that the Artifact Viewer on the right opens dynamically with the generated Markdown playbook, tracking word count and read time. When I create a New Chat, the Artifact Viewer resets to an empty state with a quick-action essay generator, and switching back to our previous session instantly restores all messages and the active artifact from PostgreSQL."*

### [1:45 – 2:25] Secure Sandboxed HTML Preview & Fail-Safe Provider Switching
- **Action:** Select `🌐 HTML Artifact` and build an interactive calculator.
- **Script:** *"We also support interactive HTML artifacts. Notice that the HTML preview renders inside an isolated iframe with `sandbox="allow-popups"`—we strictly disable `allow-scripts` and `allow-same-origin`. Furthermore, our backend sanitizer strips `<script>` tags, inline event handlers, and `javascript:` URIs. If malicious markup is submitted, an amber security warning banner is displayed and we default to the source code inspection view. Finally, when I switch our provider to Anthropic Claude without an API key, notice that rather than silently falling back, it returns an immediate, actionable HTTP 400 error."*

### [2:25 – 2:45] Architecture, Tests & Closing
- **Action:** Show the terminal running `pytest` (55 passed) and `npm run build`.
- **Script:** *"Under the hood, we have 55 automated tests passing with zero regressions, complete multi-stage Docker Compose containerization, and clean PostgreSQL persistence. Thank you!"*

